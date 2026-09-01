from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .tokenizer import ByteTokenizer


@dataclass
class DatasetReport:
    path: str
    records: int
    valid_records: int
    invalid_records: int
    duplicate_records: int
    train_records: int
    validation_records: int
    total_tokens: int
    mean_tokens: float
    p95_tokens: int
    max_tokens: int
    roles: dict[str, int]
    fingerprint: str
    warnings: list[str]


def normalize_record(raw: dict[str, Any]) -> dict[str, Any]:
    if "messages" in raw:
        messages = raw["messages"]
    elif "prompt" in raw and "completion" in raw:
        messages = [{"role": "user", "content": str(raw["prompt"])}, {"role": "assistant", "content": str(raw["completion"])}]
    else:
        raise ValueError("expected messages or prompt/completion")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")
    cleaned = []
    for message in messages:
        if message.get("role") not in {"system", "user", "assistant"}:
            raise ValueError("role must be system, user, or assistant")
        content = str(message.get("content", "")).strip()
        if not content:
            raise ValueError("message content cannot be empty")
        cleaned.append({"role": message["role"], "content": content})
    if not any(message["role"] == "assistant" for message in cleaned):
        raise ValueError("conversation needs an assistant message")
    return {"messages": cleaned}


def load_records(path: Path) -> tuple[list[dict[str, Any]], DatasetReport]:
    valid, invalid, duplicates, seen, roles, lengths = [], 0, 0, set(), {}, []
    raw_bytes = path.read_bytes() if path.exists() else b""
    tokenizer = ByteTokenizer()
    for line in raw_bytes.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            record = normalize_record(json.loads(line))
            key = json.dumps(record, sort_keys=True)
            digest = hashlib.sha256(key.encode()).hexdigest()
            if digest in seen:
                duplicates += 1
                continue
            seen.add(digest)
            valid.append(record)
            for message in record["messages"]:
                roles[message["role"]] = roles.get(message["role"], 0) + 1
            ids, _ = tokenizer.encode_messages(record["messages"], 4096)
            lengths.append(len(ids))
        except (ValueError, json.JSONDecodeError, TypeError):
            invalid += 1
    valid.sort(key=lambda item: hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest())
    split = max(1, int(len(valid) * 0.9)) if valid else 0
    fingerprint = hashlib.sha256(raw_bytes).hexdigest()[:16]
    warnings = []
    if invalid:
        warnings.append(f"{invalid} malformed records were ignored")
    if duplicates:
        warnings.append(f"{duplicates} duplicate records were removed")
    if not valid:
        warnings.append("No valid records found")
    sorted_lengths = sorted(lengths)
    p95 = sorted_lengths[min(len(sorted_lengths) - 1, int(len(sorted_lengths) * 0.95))] if sorted_lengths else 0
    report = DatasetReport(str(path), len(valid) + invalid + duplicates, len(valid), invalid, duplicates, split, len(valid) - split, sum(lengths), sum(lengths) / len(lengths) if lengths else 0, p95, max(lengths, default=0), roles, fingerprint, warnings)
    return valid, report


def split_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    split = max(1, int(len(records) * 0.9)) if records else 0
    return records[:split], records[split:]
