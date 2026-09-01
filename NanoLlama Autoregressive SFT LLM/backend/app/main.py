from __future__ import annotations

import asyncio
import json
from pathlib import Path

import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .config import DEFAULT_DATASET
from .ml.data import load_records
from .ml.model import ModelConfig, NanoLlama
from .ml.tokenizer import ByteTokenizer
from .ml.trainer import default_config, device_info, mutate, run_trial
from .storage import Store

app = FastAPI(title="NanoLlama Research API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
store = Store()
jobs: dict[str, asyncio.Task] = {}


class ExperimentRequest(BaseModel):
    name: str = "NanoLlama baseline"
    config: dict = Field(default_factory=default_config)
    steps: int = Field(default=40, ge=1, le=10000)


class AutoresearchRequest(BaseModel):
    name: str = "Autoresearch hill climb"
    trials: int = Field(default=4, ge=1, le=20)
    steps: int = Field(default=30, ge=1, le=10000)


def parsed(row):
    if not row:
        return None
    for key in ("config", "summary", "metrics"):
        if key in row and isinstance(row[key], str):
            try: row[key] = json.loads(row[key])
            except json.JSONDecodeError: pass
    return row


@app.get("/api/health")
def health(): return {"status": "ok", "service": "nanollama"}


@app.get("/api/system")
def system(): return {**device_info(), "torch_version": torch.__version__, "active_jobs": len([job for job in jobs.values() if not job.done()]), "crisp_dm_phase": "Modeling"}


@app.get("/api/datasets/inspect")
def inspect_dataset(path: str = str(DEFAULT_DATASET)):
    records, report = load_records(Path(path))
    return {"report": report.__dict__, "preview": records[:3]}


@app.get("/api/experiments")
def experiments(): return [parsed(row) for row in store.list_experiments()]


@app.post("/api/experiments")
async def create_experiment(request: ExperimentRequest):
    experiment_id = store.create_experiment(request.name, request.config)
    trial_id = store.create_trial(experiment_id, request.config)
    async def job():
        store.update_experiment(experiment_id, status="running")
        try:
            metrics = await asyncio.to_thread(run_trial, store, experiment_id, trial_id, request.config, request.steps)
            store.update_experiment(experiment_id, status="completed", summary=metrics)
        except Exception as exc:
            store.finish_trial(trial_id, "failed", {"error": str(exc)})
            store.update_experiment(experiment_id, status="failed", summary={"error": str(exc)})
    jobs[experiment_id] = asyncio.create_task(job())
    return {"id": experiment_id, "trial_id": trial_id, "status": "queued"}


@app.get("/api/experiments/{experiment_id}")
def experiment(experiment_id: str):
    row = parsed(store.get_experiment(experiment_id))
    if not row: raise HTTPException(404, "experiment not found")
    row["trials"] = [parsed(item) for item in store.list_trials(experiment_id)]
    row["metrics"] = store.metrics(experiment_id)
    return row


@app.post("/api/autoresearch")
async def autoresearch(request: AutoresearchRequest):
    config = default_config()
    experiment_id = store.create_experiment(request.name, config, phase="Modeling / Evaluation")
    async def job():
        best = None
        current = config
        store.update_experiment(experiment_id, status="running")
        for index in range(request.trials):
            trial_config = current if index == 0 else mutate(current, index)
            trial_id = store.create_trial(experiment_id, trial_config, best["trial_id"] if best else None)
            try:
                metrics = await asyncio.to_thread(run_trial, store, experiment_id, trial_id, trial_config, request.steps)
                if best is None or metrics["validation_loss"] < best["metrics"]["validation_loss"]:
                    best = {"trial_id": trial_id, "metrics": metrics}
                    current = trial_config
            except Exception as exc:
                store.finish_trial(trial_id, "failed", {"error": str(exc)})
        store.update_experiment(experiment_id, status="completed", summary=best or {"error": "no successful trials"})
    jobs[experiment_id] = asyncio.create_task(job())
    return {"id": experiment_id, "status": "queued", "trials": request.trials}


@app.get("/api/trials")
def trials(experiment_id: str | None = None): return [parsed(row) for row in store.list_trials(experiment_id)]


@app.get("/api/checkpoints")
def checkpoints():
    from .config import CHECKPOINT_DIR
    return [{"name": path.name, "path": str(path), "size_mb": round(path.stat().st_size / 2**20, 2)} for path in sorted(CHECKPOINT_DIR.glob("*.pt"), key=lambda p: p.stat().st_mtime, reverse=True)]


class ChatRequest(BaseModel):
    checkpoint: str | None = None
    messages: list[dict[str, str]]
    max_new_tokens: int = Field(default=120, ge=1, le=500)
    temperature: float = Field(default=0.8, gt=0, le=2)
    top_k: int = Field(default=40, ge=0, le=262)


def generate(request: ChatRequest):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_config = ModelConfig()
    model = NanoLlama(model_config).to(device)
    if request.checkpoint and Path(request.checkpoint).exists():
        payload = torch.load(request.checkpoint, map_location=device)
        model_config = ModelConfig(**payload["config"])
        model = NanoLlama(model_config).to(device)
        model.load_state_dict(payload["model"])
    tokenizer = ByteTokenizer()
    ids, _ = tokenizer.encode_messages(request.messages, model_config.max_seq_len)
    output = model.generate(torch.tensor([ids], dtype=torch.long, device=device), request.max_new_tokens, request.temperature, request.top_k)[0].tolist()
    return tokenizer.decode(output[len(ids):])


@app.post("/api/chat")
async def chat(request: ChatRequest): return {"response": await asyncio.to_thread(generate, request)}


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    response = await asyncio.to_thread(generate, request)
    async def events():
        for token in response.split(" "):
            yield f"data: {json.dumps(token + ' ')}\n\n"
            await asyncio.sleep(0.01)
        yield "data: [DONE]\n\n"
    return StreamingResponse(events(), media_type="text/event-stream")
