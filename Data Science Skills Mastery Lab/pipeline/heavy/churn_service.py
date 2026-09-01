"""FastAPI scoring service for the churn model (CRISP-DM phase 6).

Loaded by uvicorn in heavy/serve_api.py. Kept deliberately small: load the
artifact once at import, validate the request shape, return a score plus the
threshold decision and the model version the caller was served by.
"""
from __future__ import annotations
import hashlib, os, pathlib, sys, time
from typing import Literal

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from lib.paths import ARTIFACTS

MODEL_PATH = ARTIFACTS / "churn_model.joblib"
THRESHOLD = float(os.environ.get("CHURN_THRESHOLD", "0.20"))

# Loaded once at import, not per request.
MODEL = joblib.load(MODEL_PATH)
MODEL_SHA = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()[:12]
FEATURES = list(MODEL.feature_names_in_) if hasattr(MODEL, "feature_names_in_") else None

app = FastAPI(title="Telco churn scoring", version="1.0.0")


class Customer(BaseModel):
    """Only the fields the pipeline actually consumes; unknown keys are rejected."""
    model_config = {"extra": "forbid"}

    gender: str
    SeniorCitizen: int
    Partner: str
    Dependents: str
    tenure: int = Field(ge=0)
    PhoneService: str
    MultipleLines: str
    InternetService: str
    OnlineSecurity: str
    OnlineBackup: str
    DeviceProtection: str
    TechSupport: str
    StreamingTV: str
    StreamingMovies: str
    Contract: str
    PaperlessBilling: str
    PaymentMethod: str
    MonthlyCharges: float = Field(ge=0)
    TotalCharges: float = Field(ge=0)
    n_services: int
    tenure_band: str
    avg_charge_per_month: float
    charge_drift: float
    charge_per_service: float
    is_new: int
    auto_pay: int
    segment_te: float


class Prediction(BaseModel):
    churn_probability: float
    decision: Literal["contact", "hold"]
    threshold: float
    model_sha: str
    latency_ms: float


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_sha": MODEL_SHA, "threshold": THRESHOLD,
            "n_features": len(FEATURES) if FEATURES else None}


@app.post("/predict", response_model=Prediction)
def predict(customer: Customer) -> Prediction:
    t0 = time.perf_counter()
    df = pd.DataFrame([customer.model_dump()])
    try:
        p = float(MODEL.predict_proba(df)[:, 1][0])
    except Exception as exc:                       # bad shape reaches the client as 422, not a 500 trace
        raise HTTPException(status_code=422, detail=f"scoring failed: {exc}") from exc
    return Prediction(churn_probability=round(p, 6),
                      decision="contact" if p >= THRESHOLD else "hold",
                      threshold=THRESHOLD, model_sha=MODEL_SHA,
                      latency_ms=round((time.perf_counter() - t0) * 1000, 3))


@app.post("/predict/batch")
def predict_batch(customers: list[Customer]) -> dict:
    """Batching exists because per-row HTTP calls waste most of the time in overhead."""
    t0 = time.perf_counter()
    df = pd.DataFrame([c.model_dump() for c in customers])
    p = MODEL.predict_proba(df)[:, 1]
    return {"n": len(customers),
            "scores": [round(float(v), 6) for v in p],
            "contact": [bool(v >= THRESHOLD) for v in p],
            "model_sha": MODEL_SHA,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 3)}
