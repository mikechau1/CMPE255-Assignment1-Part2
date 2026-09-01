"""Versioned model artifacts.

A trained model is only useful if you can tell which data and code produced it,
so every run writes a self-describing directory and repoints `latest`. The API
resolves `latest` at startup; the Model dashboard renders the same metadata.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib

from .config import get_config
from .logging_utils import get_logger

log = get_logger(__name__)

LATEST_POINTER = "latest.json"


def git_sha() -> str:
    """Short commit hash, or 'unknown' outside a repo."""
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


def new_version() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def save(
    version: str,
    *,
    pipeline: Any,
    boosters: dict[str, Any],
    metadata: dict,
    metrics: dict,
) -> Path:
    """Write one model version and repoint `latest` at it."""
    root = get_config().paths.resolve("models")
    vdir = root / version
    vdir.mkdir(parents=True, exist_ok=True)

    joblib.dump(pipeline, vdir / "feature_pipeline.joblib")
    for name, booster in boosters.items():
        booster.save_model(str(vdir / f"model_{name}.txt"))

    metadata = {**metadata, "version": version, "git_sha": git_sha()}
    (vdir / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str), "utf-8")
    (vdir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str), "utf-8")
    (root / LATEST_POINTER).write_text(json.dumps({"version": version}, indent=2), "utf-8")

    log.info("saved model version %s -> %s", version, vdir)
    return vdir


def latest_version() -> str | None:
    root = get_config().paths.resolve("models")
    pointer = root / LATEST_POINTER
    if not pointer.exists():
        return None
    return json.loads(pointer.read_text(encoding="utf-8")).get("version")


def load(version: str | None = None) -> dict:
    """Load a saved model bundle. Defaults to `latest`."""
    import lightgbm as lgb

    root = get_config().paths.resolve("models")
    version = version or latest_version()
    if not version:
        raise FileNotFoundError(
            "No trained model found. Run: python -m nyctaxi.train --sample-frac 0.05"
        )
    vdir = root / version
    if not vdir.exists():
        raise FileNotFoundError(f"Model version {version} not found in {root}")

    boosters = {
        p.stem.removeprefix("model_"): lgb.Booster(model_file=str(p))
        for p in sorted(vdir.glob("model_*.txt"))
    }
    return {
        "version": version,
        "pipeline": joblib.load(vdir / "feature_pipeline.joblib"),
        "boosters": boosters,
        "metadata": json.loads((vdir / "metadata.json").read_text(encoding="utf-8")),
        "metrics": json.loads((vdir / "metrics.json").read_text(encoding="utf-8")),
    }
