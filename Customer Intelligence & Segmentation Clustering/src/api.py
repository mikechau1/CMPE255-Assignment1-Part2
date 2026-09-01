from __future__ import annotations
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .config import ARTIFACT_DIR

app = FastAPI(title="Customer Intelligence Segmentation API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])


def artifact() -> dict:
    path = ARTIFACT_DIR / "dashboard.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifacts not found. Run: python -m src.pipeline")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/health")
def health():
    return {"status": "ok", "artifacts_ready": (ARTIFACT_DIR / "dashboard.json").exists()}


@app.get("/api/dashboard")
def dashboard():
    return artifact()


@app.get("/api/quality")
def quality():
    return artifact()["quality"]


@app.get("/api/experiments")
def experiments():
    return artifact()["experiments"]

