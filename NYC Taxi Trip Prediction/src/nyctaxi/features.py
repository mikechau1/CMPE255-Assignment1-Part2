"""Feature engineering, packaged as a fittable, serialisable pipeline.

The pipeline is stateful on purpose: KMeans centroids and the aggregate speed
maps are learned from training data and must be reproduced byte-identically at
inference time. Fitting and serving therefore go through the same object, which
is saved into the model artifact.

LEAKAGE, and how it is handled
------------------------------
The aggregate features encode average travel *speed*, which is derived from the
target. Computing them on the full training set and then training on the same
rows lets each row see its own target -- the model looks excellent in
validation and falls apart in production.

So: `fit_transform` computes the aggregates out-of-fold (each fold is encoded
using maps built from the *other* folds), while `transform` -- used for
validation, test and live inference -- applies maps built from all of training.
KMeans is likewise fit on training rows only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.cluster import MiniBatchKMeans
from sklearn.model_selection import KFold

from .clean import haversine_km
from .logging_utils import get_logger

log = get_logger(__name__)

# Aggregate keys: each is a tuple of columns whose combination gets a mean
# log-speed. Ordered coarse-to-fine; finer keys need the smoothing prior more.
AGGREGATE_KEYS: list[tuple[str, ...]] = [
    ("pickup_cluster", "hour"),
    ("dropoff_cluster", "hour"),
    ("pickup_cluster", "dropoff_cluster"),
    ("hour", "weekday"),
]

RUSH_HOURS = {7, 8, 9, 16, 17, 18, 19}


def bearing_deg(
    lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray
) -> np.ndarray:
    """Initial compass bearing from origin to destination, in degrees.

    Direction matters in Manhattan: crosstown is slower than uptown/downtown
    for the same straight-line distance, and the model can only learn that if
    it can see heading.
    """
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dlam = np.radians(lon2 - lon1)
    y = np.sin(dlam) * np.cos(p2)
    x = np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dlam)
    return (np.degrees(np.arctan2(y, x)) + 360.0) % 360.0


def manhattan_km(
    lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Distance split into its north-south and east-west legs.

    Taxis travel a street grid, not a straight line, so the sum of the two legs
    is usually closer to the driven distance than the great-circle distance is.
    """
    ns = haversine_km(lat1, lon1, lat2, lon1)
    ew = haversine_km(lat1, lon1, lat1, lon2)
    return ns, ew


def _us_holidays(index: pd.DatetimeIndex) -> np.ndarray:
    """Boolean flag for US federal holidays, via pandas' built-in calendar."""
    from pandas.tseries.holiday import USFederalHolidayCalendar

    if len(index) == 0:
        return np.zeros(0, dtype=bool)
    cal = USFederalHolidayCalendar()
    hol = cal.holidays(start=index.min().normalize(), end=index.max().normalize())
    return np.isin(index.normalize().values, hol.values)


def base_features(df: pd.DataFrame) -> pd.DataFrame:
    """Stateless features -- pure functions of one row's inputs.

    Everything here is computable at inference from the four coordinates, the
    departure time and the passenger count. Nothing needs the target.
    """
    plat = df["pickup_lat"].to_numpy(dtype=float)
    plon = df["pickup_lon"].to_numpy(dtype=float)
    dlat = df["dropoff_lat"].to_numpy(dtype=float)
    dlon = df["dropoff_lon"].to_numpy(dtype=float)
    ts = pd.DatetimeIndex(df["pickup_datetime"])

    ns, ew = manhattan_km(plat, plon, dlat, dlon)
    hav = haversine_km(plat, plon, dlat, dlon)
    minute_of_day = ts.hour * 60 + ts.minute

    out = pd.DataFrame(index=df.index)
    # geometry
    out["pickup_lat"] = plat
    out["pickup_lon"] = plon
    out["dropoff_lat"] = dlat
    out["dropoff_lon"] = dlon
    out["center_lat"] = (plat + dlat) / 2.0
    out["center_lon"] = (plon + dlon) / 2.0
    out["haversine_km"] = hav
    out["manhattan_km"] = ns + ew
    out["ns_km"] = ns
    out["ew_km"] = ew
    out["delta_lat"] = dlat - plat
    out["delta_lon"] = dlon - plon
    out["bearing"] = bearing_deg(plat, plon, dlat, dlon)
    # A crosstown-ness signal: |sin| peaks at due east/west.
    out["bearing_sin"] = np.sin(np.radians(out["bearing"]))
    out["bearing_cos"] = np.cos(np.radians(out["bearing"]))

    # time -- cyclic encodings so 23:59 sits next to 00:01
    out["hour"] = ts.hour.astype(np.int16)
    out["weekday"] = ts.dayofweek.astype(np.int16)
    out["month"] = ts.month.astype(np.int16)
    out["week_of_year"] = ts.isocalendar().week.to_numpy().astype(np.int16)
    out["minute_of_day"] = minute_of_day.astype(np.int16)
    out["tod_sin"] = np.sin(2 * np.pi * minute_of_day / 1440.0)
    out["tod_cos"] = np.cos(2 * np.pi * minute_of_day / 1440.0)
    out["dow_sin"] = np.sin(2 * np.pi * ts.dayofweek / 7.0)
    out["dow_cos"] = np.cos(2 * np.pi * ts.dayofweek / 7.0)
    out["is_weekend"] = (ts.dayofweek >= 5).astype(np.int8)
    out["is_rush_hour"] = ts.hour.isin(RUSH_HOURS).astype(np.int8)
    out["is_holiday"] = _us_holidays(ts).astype(np.int8)

    out["passenger_count"] = df["passenger_count"].to_numpy()
    return out


@dataclass
class FeaturePipeline:
    """Learns clusters + speed aggregates on train, replays them everywhere else."""

    n_clusters: int = 100
    n_folds: int = 5
    smoothing: float = 50.0
    seed: int = 42

    pickup_kmeans: MiniBatchKMeans | None = None
    dropoff_kmeans: MiniBatchKMeans | None = None
    # tuple(key columns) -> {key value -> mean log speed}, built from all of train
    aggregate_maps: dict[tuple[str, ...], dict] = field(default_factory=dict)
    global_log_speed: float = 0.0
    feature_names: list[str] = field(default_factory=list)

    # -- clustering -------------------------------------------------------
    def _fit_clusters(self, feats: pd.DataFrame) -> None:
        seed, k = self.seed, self.n_clusters
        self.pickup_kmeans = MiniBatchKMeans(
            n_clusters=k, random_state=seed, n_init=10, batch_size=4096
        ).fit(feats[["pickup_lat", "pickup_lon"]].to_numpy())
        self.dropoff_kmeans = MiniBatchKMeans(
            n_clusters=k, random_state=seed + 1, n_init=10, batch_size=4096
        ).fit(feats[["dropoff_lat", "dropoff_lon"]].to_numpy())
        log.info("fitted KMeans with %d clusters on pickup and dropoff coords", k)

    def _assign_clusters(self, feats: pd.DataFrame) -> pd.DataFrame:
        feats = feats.copy()
        feats["pickup_cluster"] = self.pickup_kmeans.predict(
            feats[["pickup_lat", "pickup_lon"]].to_numpy()
        ).astype(np.int16)
        feats["dropoff_cluster"] = self.dropoff_kmeans.predict(
            feats[["dropoff_lat", "dropoff_lon"]].to_numpy()
        ).astype(np.int16)
        return feats

    # -- target-derived aggregates ---------------------------------------
    @staticmethod
    def _log_speed(feats: pd.DataFrame, y_seconds: np.ndarray) -> np.ndarray:
        hours = np.clip(y_seconds, 1.0, None) / 3600.0
        return np.log1p(feats["haversine_km"].to_numpy() / hours)

    def _build_map(
        self, feats: pd.DataFrame, log_speed: np.ndarray, key: tuple[str, ...]
    ) -> dict:
        """Smoothed mean log-speed per key value.

        Smoothing pulls thin cells toward the global mean, so a cluster pair
        seen three times does not get a confident, noisy estimate.
        """
        tmp = pd.DataFrame({c: feats[c].to_numpy() for c in key})
        tmp["_ls"] = log_speed
        grp = tmp.groupby(list(key))["_ls"].agg(["sum", "count"])
        smoothed = (grp["sum"] + self.global_log_speed * self.smoothing) / (
            grp["count"] + self.smoothing
        )
        return smoothed.to_dict()

    def _apply_map(self, feats: pd.DataFrame, key: tuple[str, ...], mapping: dict) -> np.ndarray:
        if len(key) == 1:
            idx = feats[key[0]].to_numpy()
        else:
            idx = pd.MultiIndex.from_arrays([feats[c].to_numpy() for c in key])
        return (
            pd.Series(idx if len(key) == 1 else list(idx))
            .map(mapping)
            .fillna(self.global_log_speed)
            .to_numpy(dtype=float)
        )

    @staticmethod
    def _agg_col(key: tuple[str, ...]) -> str:
        return "speed__" + "_x_".join(key)

    # -- public API -------------------------------------------------------
    def fit_transform(self, df: pd.DataFrame, y_seconds: np.ndarray) -> pd.DataFrame:
        """Fit on training rows and return out-of-fold-encoded features."""
        feats = self._assign_clusters_after_fit(base_features(df))
        log_speed = self._log_speed(feats, y_seconds)
        self.global_log_speed = float(np.mean(log_speed))

        # Out-of-fold encoding: fold i is encoded from the other folds only.
        kf = KFold(n_splits=self.n_folds, shuffle=True, random_state=self.seed)
        oof = {self._agg_col(k): np.full(len(feats), np.nan) for k in AGGREGATE_KEYS}
        for tr_idx, va_idx in kf.split(feats):
            tr_feats = feats.iloc[tr_idx]
            tr_speed = log_speed[tr_idx]
            for key in AGGREGATE_KEYS:
                fold_map = self._build_map(tr_feats, tr_speed, key)
                oof[self._agg_col(key)][va_idx] = self._apply_map(
                    feats.iloc[va_idx], key, fold_map
                )
        for col, values in oof.items():
            feats[col] = values

        # Full-train maps, for validation/test/inference.
        for key in AGGREGATE_KEYS:
            self.aggregate_maps[key] = self._build_map(feats, log_speed, key)
        log.info(
            "fitted %d aggregate speed maps out-of-fold (%d folds)",
            len(AGGREGATE_KEYS),
            self.n_folds,
        )

        self.feature_names = list(feats.columns)
        return feats

    def _assign_clusters_after_fit(self, feats: pd.DataFrame) -> pd.DataFrame:
        self._fit_clusters(feats)
        return self._assign_clusters(feats)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Encode unseen rows using the maps learned during fit."""
        if self.pickup_kmeans is None:
            raise RuntimeError("FeaturePipeline.transform called before fit_transform")
        feats = self._assign_clusters(base_features(df))
        for key in AGGREGATE_KEYS:
            feats[self._agg_col(key)] = self._apply_map(feats, key, self.aggregate_maps[key])
        return feats[self.feature_names] if self.feature_names else feats


CATEGORICAL_FEATURES = ["pickup_cluster", "dropoff_cluster", "hour", "weekday", "month"]
