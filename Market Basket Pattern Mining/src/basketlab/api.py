from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .pipeline import run, write_result

app = FastAPI(title="BasketLab API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://127.0.0.1:4173"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT = Path(os.getenv("BASKETLAB_ARTIFACT", PROJECT_ROOT / "artifacts" / "demo.json"))


class ExperimentRequest(BaseModel):
    budget: int = Field(default=8, ge=1, le=50)


def artifact() -> dict[str, Any]:
    if not DEFAULT_ARTIFACT.exists():
        write_result(run(), DEFAULT_ARTIFACT)
    return json.loads(DEFAULT_ARTIFACT.read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "basketlab"}


@app.get("/api/summary")
def summary() -> dict[str, Any]:
    data = artifact()
    return {"profile": data["profile"], "best_config": data["best_config"], "best_score": data["best_score"], "metadata": data["metadata"]}


@app.get("/api/rules")
def rules(limit: int = 100, min_lift: float = 0.0) -> list[dict[str, Any]]:
    if limit < 1 or limit > 1000:
        raise HTTPException(400, "limit must be between 1 and 1000")
    return [r for r in artifact()["rules"] if r["lift"] >= min_lift][:limit]


@app.get("/api/trials")
def trials() -> list[dict[str, Any]]:
    return artifact()["trials"]


@app.get("/api/prices")
def prices() -> dict[str, Any]:
    data = artifact()
    return {"catalog": data.get("price_catalog", {}), "pricing": data.get("pricing", {"source": "unavailable"})}


@app.post("/api/experiments")
def create_experiment(request: ExperimentRequest) -> dict[str, Any]:
    result = run(budget=request.budget)
    write_result(result, DEFAULT_ARTIFACT)
    return {"profile": result["profile"], "best_config": result["best_config"], "best_score": result["best_score"], "metadata": result["metadata"]}
