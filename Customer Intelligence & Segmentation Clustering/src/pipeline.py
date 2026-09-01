from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import platform
import time
import pandas as pd
from .config import ARTIFACT_DIR, DEFAULT_MAX_EXPERIMENTS, RAW_PATH, SEED
from .data import load_data, quality_report
from .modeling import ExperimentConfig, composite, fit_config, jsonable, profile, stability


def run(max_experiments: int = DEFAULT_MAX_EXPERIMENTS) -> dict:
    ARTIFACT_DIR.mkdir(exist_ok=True)
    df, demo, source = load_data(RAW_PATH)
    quality = quality_report(df, demo)
    candidate_groups = [
        list(ExperimentConfig(algorithm="kmeans", n_clusters=k, feature_set=features, scaler=scaler) for k in range(2, 8) for features in ["behavior", "all_numeric"] for scaler in ["standard", "robust"]),
        list(ExperimentConfig(algorithm="gmm", n_clusters=k, feature_set=features, scaler=scaler) for k in range(2, 8) for features in ["behavior", "all_numeric"] for scaler in ["standard", "robust"]),
        list(ExperimentConfig(algorithm="dbscan", feature_set="behavior", scaler="standard", eps=eps, min_samples=5) for eps in [0.35, 0.55, 0.8]),
    ]
    # Interleave algorithms so a small experiment budget still evaluates challengers.
    configs = [candidate for index in range(max(map(len, candidate_groups))) for group in candidate_groups if index < len(group) for candidate in [group[index]]][:max_experiments]
    history, best, best_score = [], None, -1.0
    for index, config in enumerate(configs, 1):
        started = time.perf_counter()
        try:
            result = fit_config(df, config)
            stable = stability(df, config, repeats=5)
            score = composite(result["metrics"], stable)
            accepted = score > best_score
            entry = {"run": index, "status": "accepted" if accepted else "rejected", "elapsed_seconds": round(time.perf_counter() - started, 4), "config": asdict(config), "metrics": {**result["metrics"], "stability": stable, "composite_score": score}}
            history.append(entry)
            if accepted:
                best, best_score = result, score
        except Exception as exc:
            history.append({"run": index, "status": "crash", "config": asdict(config), "error": repr(exc), "elapsed_seconds": round(time.perf_counter() - started, 4)})
    if best is None:
        raise RuntimeError("No valid clustering experiment completed")
    profiles = profile(best)
    payload = jsonable(best, profiles, best["metrics"].get("stability", 0), best_score)
    payload.update({"metadata": {"source": source, "demo_fallback": demo, "seed": SEED, "python": platform.python_version(), "generated_at": pd.Timestamp.utcnow().isoformat(), "experiment_count": len(history)}, "quality": quality, "experiments": history})
    (ARTIFACT_DIR / "dashboard.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (ARTIFACT_DIR / "quality_report.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    with (ARTIFACT_DIR / "results.tsv").open("w", encoding="utf-8") as f:
        f.write("run\tstatus\talgorithm\tn_clusters\tfeature_set\tscaler\tsilhouette\tdavies_bouldin\tstability\tcomposite_score\n")
        for entry in history:
            c, m = entry["config"], entry.get("metrics", {})
            f.write("\t".join(map(str, [entry["run"], entry["status"], c["algorithm"], c["n_clusters"], c["feature_set"], c["scaler"], m.get("silhouette", ""), m.get("davies_bouldin", ""), m.get("stability", ""), m.get("composite_score", "")])) + "\n")
    return payload


if __name__ == "__main__":
    result = run()
    print(json.dumps({"best_config": result["config"], "metrics": result["metrics"], "source": result["metadata"]["source"]}, indent=2))
