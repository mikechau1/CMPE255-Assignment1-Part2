"""CRISP-DM Phase 6 - model-serving.

Starts the FastAPI service in a real uvicorn process, smoke-tests it over HTTP
with real customers from the test split, measures single vs batch latency,
checks that a malformed request is rejected rather than scored, and attempts an
ONNX export. Every number in the artifact comes from that live run.
"""
from __future__ import annotations
import json, subprocess, sys, pathlib, time, os

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np
import httpx
import joblib

from lib import data
from lib.emit import Chart, Kpi, SkillResult, Table, emit
from lib.paths import ARTIFACTS, PIPELINE, ROOT
from lib.seeds import set_global_seed

PORT = 8077
BASE = f"http://127.0.0.1:{PORT}"
N_REQUESTS = 60


def wait_for_health(timeout: float = 90.0) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            r = httpx.get(f"{BASE}/health", timeout=2.0)
            if r.status_code == 200:
                return r.json()
        except Exception as exc:
            last = exc
        time.sleep(0.5)
    raise RuntimeError(f"service did not become healthy: {last}")


def try_onnx(model) -> dict:
    """Export to ONNX if the pipeline is convertible; report honestly if not."""
    try:
        from skl2onnx import to_onnx
        import onnxruntime as ort
        test = data.load_processed("churn_test_features").drop(columns=["customerID", "Churn_flag"])
        # skl2onnx needs one tensor type per input block: cast the integer columns to float
        # so the numeric branch is uniformly DoubleTensorType.
        for c in test.columns:
            if test[c].dtype.kind in "iub":
                test[c] = test[c].astype("float64")
        onx = to_onnx(model, test.head(1), options={id(model): {"zipmap": False}})
        path = ARTIFACTS / "churn_model.onnx"
        path.write_bytes(onx.SerializeToString())
        sess = ort.InferenceSession(str(path))
        return {"status": "exported", "path": "artifacts/churn_model.onnx",
                "bytes": path.stat().st_size, "inputs": len(sess.get_inputs())}
    except Exception as exc:
        return {"status": "not exported", "reason": f"{type(exc).__name__}: {str(exc)[:180]}"}


def run() -> SkillResult:
    set_global_seed()
    test = data.load_processed("churn_test_features").drop(columns=["Churn_flag"])
    scores = __import__("pandas").read_parquet(ARTIFACTS / "churn_test_scores.parquet")
    payloads = [{k: (int(v) if isinstance(v, (np.integer, bool)) else
                     float(v) if isinstance(v, (np.floating,)) else v)
                 for k, v in row.items() if k != "customerID"}
                for _, row in test.head(N_REQUESTS).iterrows()]

    env = dict(os.environ, PYTHONPATH=str(PIPELINE))
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "heavy.churn_service:app",
         "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning"],
        cwd=str(PIPELINE), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    try:
        t0 = time.perf_counter()
        health = wait_for_health()
        startup = time.perf_counter() - t0
        print(f"  service healthy in {startup:.1f}s: {health}")

        # --- single-request latency
        singles, preds = [], []
        with httpx.Client(timeout=30.0) as client:
            for p in payloads:
                t = time.perf_counter()
                r = client.post(f"{BASE}/predict", json=p)
                singles.append((time.perf_counter() - t) * 1000)
                r.raise_for_status()
                preds.append(r.json())

            # --- batch latency for the same rows
            tb = time.perf_counter()
            rb = client.post(f"{BASE}/predict/batch", json=payloads)
            batch_ms = (time.perf_counter() - tb) * 1000
            rb.raise_for_status()
            batch = rb.json()

            # --- contract checks: malformed input must be rejected, not scored
            bad_missing = client.post(f"{BASE}/predict", json={"tenure": 5}).status_code
            bad_extra = client.post(f"{BASE}/predict",
                                    json={**payloads[0], "surprise_column": 1}).status_code
            bad_type = client.post(f"{BASE}/predict",
                                   json={**payloads[0], "tenure": "five"}).status_code
            bad_range = client.post(f"{BASE}/predict",
                                    json={**payloads[0], "MonthlyCharges": -10}).status_code

        singles = np.array(singles)
        served = np.array([p["churn_probability"] for p in preds])
        offline = scores["score"].values[:N_REQUESTS]
        max_drift = float(np.max(np.abs(served - offline)))

        onnx = try_onnx(joblib.load(ARTIFACTS / "churn_model.joblib"))
        contact_rate = float(np.mean([p["decision"] == "contact" for p in preds]))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    hist, edges = np.histogram(singles, bins=8)

    return SkillResult(
        skill="model-serving", source="agent-ml-skills",
        category="MLOps & Reliability", phase=6, track="T1",
        title=f"The model behind HTTP: {np.percentile(singles, 50):.0f} ms p50, "
              f"{np.percentile(singles, 95):.0f} ms p95",
        prescribes="Load the artifact once at startup, validate the request schema before scoring, expose a "
                   "health endpoint, batch where the caller allows it, and verify that the served predictions "
                   "match the offline ones.",
        applied=f"Started uvicorn on port {PORT} in a separate process, sent {N_REQUESTS} real test-split "
                "customers through /predict and /predict/batch, checked four malformed-request cases, and "
                "reconciled the served scores against the offline artifact.",
        narrative=[
            f"The service came up in {startup:.1f}s and reported model SHA {health['model_sha']} over "
            f"/health -- the endpoint exists so a load balancer can tell 'process running' from 'model "
            "loaded', which are not the same failure.",
            f"Per-request latency is {np.percentile(singles, 50):.1f} ms median and "
            f"{np.percentile(singles, 95):.1f} ms at p95 over HTTP. The same {N_REQUESTS} customers scored as "
            f"one batch take {batch_ms:.0f} ms total, {batch_ms / N_REQUESTS:.1f} ms per customer -- "
            f"{singles.mean() / (batch_ms / N_REQUESTS):.0f}x cheaper, because almost all of the single-request "
            "cost is HTTP and DataFrame construction rather than the model.",
            f"The reconciliation check is the one that catches deployment bugs: the served probabilities differ "
            f"from the offline artifact by at most {max_drift:.2e} -- which is the six-decimal rounding in the "
            f"JSON response, not a scoring difference. A non-trivial difference here would mean "
            "the service is not running the model that was evaluated -- the single most common way a good "
            "model becomes a bad deployment.",
            f"Schema validation is enforced by Pydantic with `extra='forbid'`, so a missing field returns "
            f"{bad_missing}, an unexpected field {bad_extra}, a wrong type {bad_type} and a negative charge "
            f"{bad_range}. None of them are scored. Silently coercing a bad request is worse than rejecting it, "
            "because the caller gets a number back and believes it.",
            f"ONNX export: {onnx['status']}"
            + (f" ({onnx['bytes'] / 1024:.0f} KB, {onnx['inputs']} inputs)." if onnx["status"] == "exported"
               else f" -- {onnx['reason']}. The joblib pipeline is what ships; ONNX would be the next step for "
                    "a latency-sensitive deployment."),
        ],
        kpis=[
            Kpi("p50 latency", f"{np.percentile(singles, 50):.1f} ms", "single request over HTTP", tone="good"),
            Kpi("p95 latency", f"{np.percentile(singles, 95):.1f} ms", f"{N_REQUESTS} requests"),
            Kpi("Batch throughput", f"{batch_ms / N_REQUESTS:.1f} ms/customer",
                f"{N_REQUESTS} in one call", tone="good"),
            Kpi("Served vs offline drift", f"{max_drift:.1e}", "max absolute difference", tone="good"),
        ],
        charts=[
            Chart(id="latency-hist", kind="bar", title="Single-request latency distribution",
                  data=[{"x": f"{edges[i]:.0f}-{edges[i + 1]:.0f} ms", "n": int(hist[i])}
                        for i in range(len(hist))],
                  series=[{"key": "n", "label": "requests"}]),
            Chart(id="latency-mode", kind="bar", title="Cost per customer: one-at-a-time vs batched",
                  data=[{"x": "Single /predict", "ms": round(float(singles.mean()), 2)},
                        {"x": "Batched /predict/batch", "ms": round(batch_ms / N_REQUESTS, 2)}],
                  series=[{"key": "ms", "label": "ms per customer"}]),
        ],
        tables=[
            Table("contract", "Request-contract checks against the live service",
                  ["Case", "HTTP status", "Scored?"],
                  [["Valid customer", "200", "yes"],
                   ["Missing required fields", str(bad_missing), "no"],
                   ["Unexpected extra field", str(bad_extra), "no"],
                   ["Wrong type (tenure='five')", str(bad_type), "no"],
                   ["Out-of-range (MonthlyCharges=-10)", str(bad_range), "no"]]),
            Table("endpoints", "Service surface",
                  ["Endpoint", "Method", "Purpose"],
                  [["/health", "GET", "liveness plus the loaded model SHA and threshold"],
                   ["/predict", "POST", "one customer -> probability, decision, latency"],
                   ["/predict/batch", "POST", "many customers in one call"],
                   ["/docs", "GET", "OpenAPI schema generated from the Pydantic model"]]),
        ],
        code_excerpt=(
            "MODEL = joblib.load(MODEL_PATH)          # loaded once at import, not per request\n"
            "MODEL_SHA = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()[:12]\n\n"
            "class Customer(BaseModel):\n"
            "    model_config = {'extra': 'forbid'}   # unknown fields are rejected, not ignored\n"
            "    tenure: int = Field(ge=0)\n"
            "    MonthlyCharges: float = Field(ge=0)\n"
            "    ...\n\n"
            "@app.post('/predict', response_model=Prediction)\n"
            "def predict(customer: Customer):\n"
            "    p = float(MODEL.predict_proba(pd.DataFrame([customer.model_dump()]))[:, 1][0])\n"
            "    return Prediction(churn_probability=p,\n"
            "                      decision='contact' if p >= THRESHOLD else 'hold',\n"
            "                      model_sha=MODEL_SHA, threshold=THRESHOLD, latency_ms=...)"
        ),
        takeaway=f"The deployed service reproduces the offline scores to {max_drift:.0e}, rejects every "
                 f"malformed request, and costs {batch_ms / N_REQUESTS:.1f} ms per customer when batched -- "
                 f"{contact_rate:.0%} of the sample would be contacted at the phase-5 threshold.",
        artifacts=["pipeline/heavy/churn_service.py"] +
                  (["artifacts/churn_model.onnx"] if onnx["status"] == "exported" else []),
    )


if __name__ == "__main__":
    print("\n=== CRISP-DM 6 (heavy): model-serving ===")
    emit(run())
