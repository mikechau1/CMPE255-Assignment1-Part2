"""Source selection and the canonical schema.

Everything downstream -- cleaning, features, model, API, UI -- depends only on
CANONICAL_COLUMNS, never on which source produced them. That is what lets the
project build end-to-end with or without Kaggle credentials.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..config import get_config
from ..logging_utils import get_logger
from . import kaggle_source, tlc_source

log = get_logger(__name__)

CANONICAL_COLUMNS = [
    "pickup_datetime",
    "pickup_lat",
    "pickup_lon",
    "dropoff_lat",
    "dropoff_lon",
    "passenger_count",
    "trip_duration_s",
]


@dataclass
class LoadResult:
    """The data plus provenance.

    Provenance is stamped into model metadata and surfaced in the UI, so a
    reader always knows whether they are looking at address-resolution or
    zone-resolution predictions.
    """

    df: pd.DataFrame
    source: str
    notes: list[str] = field(default_factory=list)

    @property
    def is_zone_resolution(self) -> bool:
        return self.source == "tlc"


def resolve_source(requested: str | None = None) -> str:
    """Decide which source to use: explicit config wins, else availability."""
    cfg = get_config()
    requested = requested or cfg.data.source
    if requested in ("kaggle", "tlc"):
        return requested
    if requested != "auto":
        raise ValueError(f"unknown data source {requested!r}; expected auto|kaggle|tlc")
    if kaggle_source.credentials_available():
        return "kaggle"
    log.warning(
        "No Kaggle credentials found -- falling back to TLC public parquet. "
        "Coordinates will be zone-resolution, not true trip endpoints."
    )
    return "tlc"


def load(
    source: str | None = None, nrows: int | None = None, sample_frac: float | None = None
) -> LoadResult:
    """Load trips in the canonical schema from whichever source is available."""
    cfg = get_config()
    chosen = resolve_source(source)
    log.info("data source: %s", chosen)

    subsampled = False
    if chosen == "kaggle":
        df = kaggle_source.load_raw(nrows=nrows)
        notes = ["True pickup/dropoff coordinates from the Kaggle competition files."]
    else:
        # TLC subsamples internally, before the expensive coordinate scatter.
        df = tlc_source.load_raw(nrows=nrows, seed=cfg.random_seed, sample_frac=sample_frac)
        subsampled = sample_frac is not None and 0 < sample_frac < 1
        notes = [
            "TLC publishes zone IDs, not coordinates; endpoints are sampled "
            "inside the zone polygon. Predictions are zone-resolution.",
            f"Months used: {', '.join(cfg.data.tlc_months)}.",
        ]

    if sample_frac is not None and 0 < sample_frac < 1:
        if not subsampled:
            before = len(df)
            df = df.sample(frac=sample_frac, random_state=cfg.random_seed)
            log.info("sampled %d -> %d rows (frac=%.3f)", before, len(df), sample_frac)
        notes.append(f"Subsampled to {sample_frac:.0%} of available rows.")

    df = df[CANONICAL_COLUMNS].sort_values("pickup_datetime").reset_index(drop=True)
    return LoadResult(df=df, source=chosen, notes=notes)
