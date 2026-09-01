"""NYC TLC public parquet source (the no-credentials fallback).

Fidelity note, stated plainly because it matters for how the model behaves:
TLC re-encoded its historical trip files to `PULocationID`/`DOLocationID`. I
confirmed this by reading the parquet footer of yellow_tripdata_2016-01
directly -- the schema has no latitude/longitude columns at all. So this source
cannot give true trip endpoints. It gives the zone, and we sample a point
inside that zone polygon (see zones.sample_points_in_zones).

Consequence: a model trained on this source learns zone-to-zone travel time.
It still answers the map's question, but at roughly zone resolution rather than
address resolution. Supply Kaggle credentials to get the real thing.
"""

from __future__ import annotations

import pandas as pd

from ..config import get_config
from ..logging_utils import get_logger
from .zones import download_file, sample_points_in_zones

log = get_logger(__name__)


def download_months(months: list[str] | None = None) -> list:
    """Fetch the configured monthly yellow-taxi parquet files."""
    cfg = get_config()
    months = months or cfg.data.tlc_months
    raw = cfg.paths.resolve("data_raw") / "tlc"
    raw.mkdir(parents=True, exist_ok=True)
    paths = []
    for m in months:
        name = f"yellow_tripdata_{m}.parquet"
        paths.append(download_file(f"{cfg.data.tlc_base_url}/{name}", raw / name))
    return paths


def load_raw(
    nrows: int | None = None, seed: int = 42, sample_frac: float | None = None
) -> pd.DataFrame:
    """Read TLC parquet into the canonical schema.

    Duration is derived from the pickup/dropoff timestamps (TLC has no
    duration column), and coordinates are sampled inside the zone polygons.

    `sample_frac` is applied *here*, before coordinate sampling, because
    scattering points is the expensive step: subsampling afterwards would
    place millions of points only to discard them.
    """
    frames = []
    remaining = nrows
    for path in download_months():
        df = pd.read_parquet(
            path,
            columns=[
                "tpep_pickup_datetime",
                "tpep_dropoff_datetime",
                "passenger_count",
                "PULocationID",
                "DOLocationID",
            ],
        )
        if remaining is not None:
            df = df.head(remaining)
            remaining -= len(df)
        frames.append(df)
        if remaining is not None and remaining <= 0:
            break

    df = pd.concat(frames, ignore_index=True)
    log.info("tlc source: %d raw rows across %d file(s)", len(df), len(frames))

    if sample_frac is not None and 0 < sample_frac < 1:
        before = len(df)
        df = df.sample(frac=sample_frac, random_state=seed).reset_index(drop=True)
        log.info("subsampled %d -> %d rows before coordinate sampling", before, len(df))

    pickup = pd.to_datetime(df["tpep_pickup_datetime"])
    dropoff = pd.to_datetime(df["tpep_dropoff_datetime"])
    duration = (dropoff - pickup).dt.total_seconds()

    # Drop rows whose zone is unmapped before sampling, so the sampler never
    # sees an id it has no polygon for.
    valid = (
        df["PULocationID"].between(1, 263)
        & df["DOLocationID"].between(1, 263)
        & duration.notna()
    )
    df, pickup, duration = df[valid], pickup[valid], duration[valid]

    log.info("sampling coordinates inside zone polygons for %d rows", len(df))
    plon, plat = sample_points_in_zones(df["PULocationID"].to_numpy(), seed=seed)
    dlon, dlat = sample_points_in_zones(df["DOLocationID"].to_numpy(), seed=seed + 1)

    out = pd.DataFrame(
        {
            "pickup_datetime": pickup.reset_index(drop=True),
            "pickup_lat": plat.astype("float32"),
            "pickup_lon": plon.astype("float32"),
            "dropoff_lat": dlat.astype("float32"),
            "dropoff_lon": dlon.astype("float32"),
            "passenger_count": df["passenger_count"]
            .fillna(1)
            .astype("int16")
            .reset_index(drop=True),
            "trip_duration_s": duration.to_numpy().astype("float32"),
        }
    )
    log.info("tlc source: %d rows in canonical schema", len(out))
    return out
