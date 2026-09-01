"""FastAPI application -- CRISP-DM phase 6, deployment.

One process serves both the JSON API and the built React bundle, so the whole
project deploys as a single artifact on a single port.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..config import ROOT, get_config
from ..logging_utils import get_logger
from .predict import PredictionService
from .routing import ExternalServices
from .schemas import CurveResponse, PredictRequest, PredictResponse

log = get_logger(__name__)

state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the model once at startup rather than per request."""
    cfg = get_config()
    state["services"] = ExternalServices()
    try:
        state["service"] = PredictionService()
    except FileNotFoundError as exc:
        # Serve anyway: /api/health should be able to *report* the problem.
        log.error("no model available: %s", exc)
        state["service"] = None
        state["model_error"] = str(exc)

    try:
        from ..data.zones import load_zones

        state["zones"] = load_zones()
    except Exception as exc:
        log.warning("zone geometry unavailable: %s", exc)
        state["zones"] = {"type": "FeatureCollection", "features": []}

    log.info("API ready -- %s", cfg.project_name)
    yield
    await state["services"].aclose()


app = FastAPI(
    title="NYC Taxi Trip Prediction",
    description="Trip duration, uncertainty band and metered fare for New York yellow cabs.",
    version="1.0.0",
    lifespan=lifespan,
)

# Permissive CORS so the Vite dev server on :5173 can call the API on :8000.
# In the shipped single-process deployment the frontend is same-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_service() -> PredictionService:
    svc = state.get("service")
    if svc is None:
        raise HTTPException(
            503,
            detail=state.get("model_error", "No trained model is loaded.")
            + " Train one with: python -m nyctaxi.train --sample-frac 0.05",
        )
    return svc


# --------------------------------------------------------------------------
# model + health
# --------------------------------------------------------------------------
@app.get("/api/health", tags=["meta"])
async def health() -> dict:
    svc = state.get("service")
    return {
        "status": "ok" if svc else "degraded",
        "model_loaded": svc is not None,
        "model_version": svc.version if svc else None,
        "data_source": svc.metadata.get("data_source") if svc else None,
        "zone_resolution": svc.zone_resolution if svc else None,
        "detail": None if svc else state.get("model_error"),
    }


@app.get("/api/model", tags=["meta"])
async def model_info() -> dict:
    """Everything the Model dashboard renders -- same numbers as the report."""
    svc = require_service()
    return {
        "version": svc.version,
        "metadata": svc.metadata,
        "metrics": svc.metrics,
        "available_versions": sorted(
            p.name for p in get_config().paths.resolve("models").iterdir() if p.is_dir()
        ),
    }


@app.get("/api/model/residuals", tags=["meta"])
async def residuals(limit: int = Query(3000, ge=100, le=20000)) -> dict:
    """A sample of validation predictions, for the residual scatter plot."""
    svc = require_service()
    path = get_config().paths.resolve("models") / svc.version / "validation_predictions.parquet"
    if not path.exists():
        raise HTTPException(404, "No validation predictions stored for this model version.")

    df = pd.read_parquet(path)
    if len(df) > limit:
        df = df.sample(limit, random_state=42)
    df = df.assign(residual_s=df["y_pred"] - df["y_true"])

    by_hour = (
        df.assign(abs_err=df["residual_s"].abs())
        .groupby("hour")
        .agg(mae_s=("abs_err", "mean"), n=("abs_err", "size"))
        .reset_index()
    )
    bins = [0, 1, 2, 5, 10, 20, 1000]
    labels = ["<1km", "1-2km", "2-5km", "5-10km", "10-20km", ">20km"]
    by_distance = (
        df.assign(
            abs_err=df["residual_s"].abs(),
            bucket=pd.cut(df["haversine_km"], bins=bins, labels=labels),
        )
        .groupby("bucket", observed=True)
        .agg(mae_s=("abs_err", "mean"), n=("abs_err", "size"))
        .reset_index()
    )
    return {
        "points": df[["y_true", "y_pred", "residual_s", "haversine_km", "hour"]]
        .round(2)
        .to_dict("records"),
        "by_hour": by_hour.round(2).to_dict("records"),
        "by_distance": by_distance.astype({"bucket": str}).round(2).to_dict("records"),
    }


# --------------------------------------------------------------------------
# prediction
# --------------------------------------------------------------------------
@app.post("/api/predict", response_model=PredictResponse, tags=["predict"])
async def predict(req: PredictRequest) -> dict:
    svc = require_service()
    return svc.predict(
        pickup=(req.pickup.lat, req.pickup.lon),
        dropoff=(req.dropoff.lat, req.dropoff.lon),
        departure=req.departure,
        passengers=req.passengers,
        road_distance_km=req.road_distance_km,
    )


@app.post("/api/predict/curve", response_model=CurveResponse, tags=["predict"])
async def predict_curve(req: PredictRequest) -> dict:
    """The same trip at all 24 departure hours -- 'leave now or wait?'."""
    svc = require_service()
    return svc.hourly_curve(
        pickup=(req.pickup.lat, req.pickup.lon),
        dropoff=(req.dropoff.lat, req.dropoff.lon),
        day=req.departure,
        passengers=req.passengers,
    )


# --------------------------------------------------------------------------
# geo helpers
# --------------------------------------------------------------------------
@app.get("/api/route", tags=["geo"])
async def route(
    from_lat: float, from_lon: float, to_lat: float, to_lon: float
) -> JSONResponse:
    """Driving route geometry. Display and fare input only -- not a feature."""
    result = await state["services"].route((from_lat, from_lon), (to_lat, to_lon))
    if result is None:
        # 200 with available=false: the UI degrades to a straight line, and a
        # rate-limited public router is an expected condition, not an error.
        return JSONResponse({"available": False, "reason": "Routing service unavailable."})
    return JSONResponse({"available": True, **result})


@app.get("/api/geocode", tags=["geo"])
async def geocode(q: str = Query(..., min_length=2), limit: int = Query(5, ge=1, le=10)) -> dict:
    return {"results": await state["services"].geocode(q, limit=limit)}


@app.get("/api/zones", tags=["geo"])
async def zones() -> dict:
    return state.get("zones", {"type": "FeatureCollection", "features": []})


@app.post("/api/zones/travel-time", tags=["geo"])
async def zone_travel_times(req: PredictRequest) -> dict:
    """Predicted duration from every taxi zone to one destination.

    Drives the Insights choropleth. Rather than showing a static historical
    average, it asks the deployed model the same question 263 times, so the map
    reflects the model actually serving predictions -- and recolours whenever
    the destination or the hour changes.
    """
    svc = require_service()
    features = state.get("zones", {}).get("features", [])
    if not features:
        raise HTTPException(503, "Zone geometry is not available.")

    dest = (req.dropoff.lat, req.dropoff.lon)
    departure = req.departure or datetime.now()
    origins = [
        (f["properties"]["centroid_lat"], f["properties"]["centroid_lon"]) for f in features
    ]
    df = svc._frame(origins, [dest] * len(origins), [departure] * len(origins), req.passengers)
    preds = svc._predict_batch(df)["main"]

    return {
        "destination": {"lat": dest[0], "lon": dest[1]},
        "departure": departure.isoformat(),
        "min_s": float(np.min(preds)),
        "max_s": float(np.max(preds)),
        "zones": [
            {
                "location_id": f["properties"]["location_id"],
                "zone": f["properties"]["zone"],
                "borough": f["properties"]["borough"],
                "duration_s": round(float(p), 1),
            }
            for f, p in zip(features, preds, strict=False)
        ],
    }


# --------------------------------------------------------------------------
# static frontend (mounted last so /api/* wins)
# --------------------------------------------------------------------------
def mount_frontend(application: FastAPI) -> None:
    dist = ROOT / get_config().paths.frontend_dist
    if not (dist / "index.html").exists():
        log.warning("frontend build not found at %s -- API only. Run: npm run build", dist)
        return

    application.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @application.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        """Serve built files, falling back to index.html for client routes."""
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


mount_frontend(app)
