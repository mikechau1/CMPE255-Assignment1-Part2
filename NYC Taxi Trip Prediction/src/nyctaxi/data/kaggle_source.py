"""Kaggle `nyc-taxi-trip-duration` source (the preferred path).

This is the only NYC taxi dataset that still carries true pickup/dropoff
coordinates -- TLC re-encoded all of its historical files to zone IDs -- so it
is what makes drop-a-pin-anywhere prediction meaningful.

Requires credentials. See `credentials_available()` for what counts.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pandas as pd

from ..config import get_config
from ..logging_utils import get_logger

log = get_logger(__name__)


def credentials_available() -> bool:
    """True when the Kaggle API can authenticate.

    Either ~/.kaggle/kaggle.json exists, or KAGGLE_USERNAME + KAGGLE_KEY are
    exported. This is what decides the auto source in loader.py.
    """
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return True
    return (Path.home() / ".kaggle" / "kaggle.json").exists()


def download(force: bool = False) -> Path:
    """Fetch and unzip the competition train file. Returns the CSV path."""
    cfg = get_config()
    raw = cfg.paths.resolve("data_raw") / "kaggle"
    raw.mkdir(parents=True, exist_ok=True)
    csv_path = raw / "train.csv"
    if csv_path.exists() and not force:
        log.info("cached      %s", csv_path.name)
        return csv_path

    if not credentials_available():
        raise RuntimeError(
            "Kaggle credentials not found. Create a token at "
            "kaggle.com > Settings > API > Create New Token, accept the rules "
            "for the nyc-taxi-trip-duration competition, and save kaggle.json "
            "to ~/.kaggle/."
        )

    # Imported lazily: the kaggle package authenticates at import time, which
    # would make the whole module unimportable without credentials.
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    log.info("downloading kaggle competition %s", cfg.data.kaggle_competition)
    api.competition_download_files(cfg.data.kaggle_competition, path=str(raw), quiet=False)

    for zpath in raw.glob("*.zip"):
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(raw)
    # the competition ships train.zip -> train.csv, sometimes nested
    if not csv_path.exists():
        found = list(raw.rglob("train.csv"))
        if not found:
            raise RuntimeError(f"train.csv not found after extracting into {raw}")
        csv_path = found[0]
    return csv_path


def load_raw(nrows: int | None = None) -> pd.DataFrame:
    """Read the competition CSV into the canonical schema.

    Kaggle columns map straight across -- this is the lossless path.
    """
    path = download()
    df = pd.read_csv(
        path,
        nrows=nrows,
        parse_dates=["pickup_datetime"],
        usecols=[
            "pickup_datetime",
            "pickup_latitude",
            "pickup_longitude",
            "dropoff_latitude",
            "dropoff_longitude",
            "passenger_count",
            "trip_duration",
        ],
    )
    out = pd.DataFrame(
        {
            "pickup_datetime": df["pickup_datetime"],
            "pickup_lat": df["pickup_latitude"].astype("float32"),
            "pickup_lon": df["pickup_longitude"].astype("float32"),
            "dropoff_lat": df["dropoff_latitude"].astype("float32"),
            "dropoff_lon": df["dropoff_longitude"].astype("float32"),
            "passenger_count": df["passenger_count"].astype("int16"),
            "trip_duration_s": df["trip_duration"].astype("float32"),
        }
    )
    log.info("kaggle source: %d rows", len(out))
    return out
