from __future__ import annotations

import math
import random
import time
from dataclasses import asdict
from pathlib import Path

import torch

from ..config import CHECKPOINT_DIR, DEFAULT_DATASET
from ..storage import Store
from .data import load_records, split_records
from .model import ModelConfig, NanoLlama
from .tokenizer import ByteTokenizer


def device_info():
    cuda = torch.cuda.is_available()
    return {"device": "cuda" if cuda else "cpu", "cuda": cuda, "gpu_name": torch.cuda.get_device_name(0) if cuda else "CPU", "vram_gb": round(torch.cuda.get_device_properties(0).total_memory / 2**30, 2) if cuda else 0}


def batches(records, tokenizer, config, batch_size, device):
    examples = []
    for record in records:
        ids, labels = tokenizer.encode_messages(record["messages"], config.max_seq_len + 1)
        ids += [tokenizer.PAD] * (config.max_seq_len + 1 - len(ids))
        labels += [-100] * (config.max_seq_len + 1 - len(labels))
        examples.append((ids[:-1], labels[1:]))
    if not examples:
        examples = [([tokenizer.BOS] * config.max_seq_len, [-100] * config.max_seq_len)]
    while True:
        random.shuffle(examples)
        for start in range(0, len(examples), batch_size):
            chunk = examples[start:start + batch_size]
            yield torch.tensor([item[0] for item in chunk], dtype=torch.long, device=device), torch.tensor([item[1] for item in chunk], dtype=torch.long, device=device)


@torch.no_grad()
def evaluate(model, records, tokenizer, config, batch_size, device):
    model.eval()
    loader = batches(records, tokenizer, config, batch_size, device)
    losses = []
    for _ in range(min(8, max(1, math.ceil(len(records) / batch_size)))):
        _, loss = model(*next(loader))
        losses.append(float(loss.item()))
    return sum(losses) / len(losses)


def run_trial(store: Store, experiment_id: str, trial_id: str, config_dict: dict, steps: int = 40):
    seed = int(config_dict.get("seed", 42))
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.cuda.reset_peak_memory_stats()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    records, report = load_records(Path(config_dict.get("dataset", DEFAULT_DATASET)))
    train_records, val_records = split_records(records)
    model_config = ModelConfig(vocab_size=262, max_seq_len=int(config_dict.get("max_seq_len", 256)), n_layer=int(config_dict.get("n_layer", 4)), n_head=int(config_dict.get("n_head", 4)), n_embd=int(config_dict.get("n_embd", 256)), dropout=float(config_dict.get("dropout", 0)))
    model = NanoLlama(model_config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=float(config_dict.get("learning_rate", 3e-4)), weight_decay=float(config_dict.get("weight_decay", 0.01)))
    tokenizer = ByteTokenizer()
    loader = batches(train_records, tokenizer, model_config, int(config_dict.get("batch_size", 2)), device)
    use_amp = device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    history, start = [], time.time()
    model.train()
    for step in range(1, steps + 1):
        inputs, targets = next(loader)
        with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=use_amp):
            _, loss = model(inputs, targets)
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        grad_norm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), float(config_dict.get("grad_clip", 1.0))).item())
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad(set_to_none=True)
        metric = {"step": step, "train_loss": float(loss.item()), "grad_norm": grad_norm, "learning_rate": optimizer.param_groups[0]["lr"], "tokens_per_sec": round(inputs.numel() / max(time.time() - start, 1e-6), 2)}
        if step == 1 or step % max(1, steps // 8) == 0 or step == steps:
            metric["validation_loss"] = evaluate(model, val_records, tokenizer, model_config, 1, device)
        if device.type == "cuda":
            metric["vram_gb"] = round(torch.cuda.max_memory_allocated() / 2**30, 3)
        history.append(metric)
        store.append_metric(experiment_id, {"trial_id": trial_id, **metric})
    val_loss = evaluate(model, val_records, tokenizer, model_config, 1, device)
    checkpoint = CHECKPOINT_DIR / f"{experiment_id}-{trial_id}.pt"
    torch.save({"model": model.state_dict(), "config": asdict(model_config), "training": config_dict, "report": report.__dict__, "validation_loss": val_loss}, checkpoint)
    metrics = {"validation_loss": val_loss, "perplexity": round(math.exp(min(val_loss, 20)), 3), "steps": steps, "checkpoint": str(checkpoint), "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 3) if device.type == "cuda" else 0, "device": str(device), "history": history}
    store.finish_trial(trial_id, "completed", metrics)
    return metrics


def default_config(dataset=str(DEFAULT_DATASET)):
    return {"dataset": dataset, "max_seq_len": 256, "n_layer": 4, "n_head": 4, "n_embd": 256, "learning_rate": 3e-4, "weight_decay": 0.01, "batch_size": 2, "grad_clip": 1.0, "seed": 42}


def mutate(config, index):
    candidate = dict(config)
    mutations = [("learning_rate", lambda x: x * 0.5 if index % 2 else x * 2), ("weight_decay", lambda x: 0.0 if x else 0.01), ("batch_size", lambda x: 1 if x > 1 else 2), ("dropout", lambda x: 0.05 if not x else 0.0)]
    key, fn = mutations[index % len(mutations)]
    candidate[key] = fn(candidate.get(key, 0.0))
    return candidate
