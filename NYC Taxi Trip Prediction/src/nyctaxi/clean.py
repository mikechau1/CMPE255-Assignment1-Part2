"""CRISP-DM phase 3 -- data preparation.

Each rule records how many rows it removed. The report is written to
docs/03-data-preparation.md, so the cleaning story is an audit trail rather
than an assertion.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import get_config
from .logging_utils import get_logger

log = get_logger(__name__)


@dataclass
class CleaningStep:
    rule: str
    rationale: str
    removed: int
    remaining: int

    @property
    def pct_removed(self) -> float:
        total = self.removed + self.remaining
        return 100.0 * self.removed / total if total else 0.0


@dataclass
class CleaningReport:
    steps: list[CleaningStep]
    rows_in: int
    rows_out: int

    @property
    def pct_kept(self) -> float:
        return 100.0 * self.rows_out / self.rows_in if self.rows_in else 0.0

    def to_markdown(self) -> str:
        lines = [
            f"Rows in: **{self.rows_in:,}** -> rows out: **{self.rows_out:,}** "
            f"({self.pct_kept:.2f}% kept)",
            "",
            "| Rule | Rationale | Rows removed | % | Remaining |",
            "|---|---|---:|---:|---:|",
        ]
        for s in self.steps:
            lines.append(
                f"| `{s.rule}` | {s.rationale} | {s.removed:,} | "
                f"{s.pct_removed:.2f}% | {s.remaining:,} |"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "pct_kept": round(self.pct_kept, 3),
            "steps": [
                {
                    "rule": s.rule,
                    "rationale": s.rationale,
                    "removed": s.removed,
                    "pct_removed": round(s.pct_removed, 4),
                    "remaining": s.remaining,
                }
                for s in self.steps
            ],
        }


def haversine_km(
    lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray
) -> np.ndarray:
    """Great-circle distance in km. Vectorised; used by cleaning and features."""
    r = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlam / 2.0) ** 2
    return 2.0 * r * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    """Apply the configured quality rules, recording the effect of each."""
    cfg = get_config().clean
    bbox = cfg.nyc_bbox
    rows_in = len(df)
    steps: list[CleaningStep] = []

    def apply(mask: pd.Series, rule: str, rationale: str) -> pd.DataFrame:
        nonlocal df
        keep = mask.fillna(False)
        removed = int((~keep).sum())
        df = df[keep]
        steps.append(CleaningStep(rule, rationale, removed, len(df)))
        log.info("clean %-28s removed %8d -> %9d left", rule, removed, len(df))
        return df

    coord_cols = ["pickup_lat", "pickup_lon", "dropoff_lat", "dropoff_lon"]
    apply(
        df[coord_cols + ["pickup_datetime", "trip_duration_s"]].notna().all(axis=1),
        "no_nulls",
        "Coordinates, timestamp and target must all be present.",
    )
    apply(
        df["pickup_lat"].between(bbox.min_lat, bbox.max_lat)
        & df["dropoff_lat"].between(bbox.min_lat, bbox.max_lat)
        & df["pickup_lon"].between(bbox.min_lon, bbox.max_lon)
        & df["dropoff_lon"].between(bbox.min_lon, bbox.max_lon),
        "inside_nyc_bbox",
        "GPS noise puts some trips in the ocean or other states.",
    )
    apply(
        df["trip_duration_s"].between(cfg.min_duration_s, cfg.max_duration_s),
        "plausible_duration",
        f"Keep {cfg.min_duration_s}s-{cfg.max_duration_s}s; shorter are meter "
        "misfires, longer are forgotten meters.",
    )
    apply(
        df["passenger_count"].between(0, cfg.max_passengers),
        "plausible_passengers",
        f"A yellow cab seats at most {cfg.max_passengers}.",
    )

    dist = haversine_km(
        df["pickup_lat"].to_numpy(),
        df["pickup_lon"].to_numpy(),
        df["dropoff_lat"].to_numpy(),
        df["dropoff_lon"].to_numpy(),
    )
    df = df.assign(_haversine_km=dist)
    apply(
        df["_haversine_km"] <= cfg.max_haversine_km,
        "plausible_distance",
        f"Straight-line trips over {cfg.max_haversine_km:g} km leave the metro area.",
    )

    speed = df["_haversine_km"] / (df["trip_duration_s"] / 3600.0)
    df = df.assign(_speed_kmh=speed)
    apply(
        df["_speed_kmh"].between(cfg.min_speed_kmh, cfg.max_speed_kmh),
        "plausible_speed",
        f"Implied straight-line speed must be {cfg.min_speed_kmh:g}-"
        f"{cfg.max_speed_kmh:g} km/h; outside that the record is inconsistent.",
    )

    df = df.drop(columns=["_haversine_km", "_speed_kmh"]).reset_index(drop=True)
    report = CleaningReport(steps=steps, rows_in=rows_in, rows_out=len(df))
    log.info("cleaning kept %.2f%% of rows (%d -> %d)", report.pct_kept, rows_in, len(df))
    return df, report
