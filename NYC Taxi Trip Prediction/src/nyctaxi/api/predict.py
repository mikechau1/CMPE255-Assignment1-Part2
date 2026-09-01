"""Inference service.

Loads one model bundle at startup and answers prediction requests from it. The
same FeaturePipeline object that was fitted during training is replayed here,
so serving cannot drift from training.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from .. import registry
from ..clean import haversine_km
from ..fare import estimate_fare
from ..logging_utils import get_logger

log = get_logger(__name__)

# Readable names for the contribution panel. Anything unlisted falls back to a
# tidied version of the raw column name.
FEATURE_LABELS = {
    "haversine_km": "Straight-line distance",
    "manhattan_km": "Grid distance",
    "ns_km": "North-south leg",
    "ew_km": "East-west leg",
    "bearing": "Direction of travel",
    "bearing_sin": "Crosstown component",
    "bearing_cos": "Uptown/downtown component",
    "hour": "Hour of day",
    "weekday": "Day of week",
    "is_rush_hour": "Rush hour",
    "is_weekend": "Weekend",
    "is_holiday": "Public holiday",
    "tod_sin": "Time of day (cyclic)",
    "tod_cos": "Time of day (cyclic)",
    "passenger_count": "Passengers",
    "pickup_cluster": "Pickup neighbourhood",
    "dropoff_cluster": "Dropoff neighbourhood",
    "speed__pickup_cluster_x_hour": "Typical speed leaving there, this hour",
    "speed__dropoff_cluster_x_hour": "Typical speed arriving there, this hour",
    "speed__pickup_cluster_x_dropoff_cluster": "Typical speed on this route",
    "speed__hour_x_weekday": "Typical speed at this time of week",
}


def _label(name: str) -> str:
    return FEATURE_LABELS.get(name, name.replace("_", " ").capitalize())


class PredictionService:
    """Holds the loaded model and turns requests into estimates."""

    def __init__(self, version: str | None = None):
        bundle = registry.load(version)
        self.version: str = bundle["version"]
        self.pipeline = bundle["pipeline"]
        self.boosters = bundle["boosters"]
        self.metadata = bundle["metadata"]
        self.metrics = bundle["metrics"]
        self.zone_resolution: bool = bool(self.metadata.get("zone_resolution", False))
        log.info(
            "loaded model %s (source=%s, %s rows)",
            self.version,
            self.metadata.get("data_source"),
            f"{self.metadata.get('rows_clean', 0):,}",
        )

    # -- core ------------------------------------------------------------
    def _frame(
        self,
        pickups: list[tuple[float, float]],
        dropoffs: list[tuple[float, float]],
        departures: list[datetime],
        passengers: int,
    ) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "pickup_datetime": pd.to_datetime(departures),
                "pickup_lat": [p[0] for p in pickups],
                "pickup_lon": [p[1] for p in pickups],
                "dropoff_lat": [d[0] for d in dropoffs],
                "dropoff_lon": [d[1] for d in dropoffs],
                "passenger_count": passengers,
                "trip_duration_s": 0.0,  # unused at inference; keeps the schema whole
            }
        )

    def _predict_batch(self, df: pd.DataFrame) -> dict[str, np.ndarray]:
        """Run every booster over a prepared frame. Returns seconds."""
        feats = self.pipeline.transform(df)
        out: dict[str, np.ndarray] = {}
        for name, booster in self.boosters.items():
            preds = np.expm1(booster.predict(feats, num_iteration=booster.best_iteration))
            out[name] = np.clip(preds, 30.0, None)

        # Independently-trained quantiles can cross; sorting restores order.
        if {"q10", "q50", "q90"} <= out.keys():
            stacked = np.sort(np.vstack([out["q10"], out["q50"], out["q90"]]), axis=0)
            out["q10"], out["q50"], out["q90"] = stacked
        return out

    def predict(
        self,
        pickup: tuple[float, float],
        dropoff: tuple[float, float],
        departure: datetime | None = None,
        passengers: int = 1,
        road_distance_km: float | None = None,
    ) -> dict:
        departure = departure or datetime.now()
        df = self._frame([pickup], [dropoff], [departure], passengers)
        preds = self._predict_batch(df)

        point = float(preds["main"][0])
        p10 = float(preds.get("q10", preds["main"])[0])
        p90 = float(preds.get("q90", preds["main"])[0])
        p50 = float(preds.get("q50", preds["main"])[0])

        straight_km = float(
            haversine_km(
                np.array([pickup[0]]), np.array([pickup[1]]),
                np.array([dropoff[0]]), np.array([dropoff[1]]),
            )[0]
        )
        # Prefer the real road distance when the client supplies one; the
        # straight line understates a metered fare noticeably in Manhattan.
        if road_distance_km and road_distance_km > 0:
            distance_km, distance_source = road_distance_km, "osrm_route"
        else:
            distance_km, distance_source = straight_km * 1.35, "haversine_x1.35"

        fare = estimate_fare(distance_km, point, departure, pickup=pickup, dropoff=dropoff)

        return {
            "duration": {
                "p10_s": round(p10, 1),
                "p50_s": round(p50, 1),
                "p90_s": round(p90, 1),
                "point_s": round(point, 1),
                "eta": departure + timedelta(seconds=point),
            },
            "straight_line_km": round(straight_km, 3),
            "distance_km": round(distance_km, 3),
            "distance_source": distance_source,
            "fare": fare.to_dict(),
            "contributions": self._contributions(df),
            "model_version": self.version,
            "zone_resolution": self.zone_resolution,
        }

    def hourly_curve(
        self,
        pickup: tuple[float, float],
        dropoff: tuple[float, float],
        day: datetime | None = None,
        passengers: int = 1,
    ) -> dict:
        """Predict the same trip at each of the 24 hours of a day.

        Answers the question a rider actually has -- "should I leave now or
        wait?" -- in one batched call rather than 24 round trips.
        """
        day = (day or datetime.now()).replace(minute=0, second=0, microsecond=0)
        departures = [day.replace(hour=h) for h in range(24)]
        df = self._frame([pickup] * 24, [dropoff] * 24, departures, passengers)
        preds = self._predict_batch(df)

        points = [
            {
                "hour": h,
                "p10_s": round(float(preds.get("q10", preds["main"])[h]), 1),
                "p50_s": round(float(preds["main"][h]), 1),
                "p90_s": round(float(preds.get("q90", preds["main"])[h]), 1),
            }
            for h in range(24)
        ]
        return {
            "points": points,
            "best_hour": int(np.argmin(preds["main"])),
            "worst_hour": int(np.argmax(preds["main"])),
            "model_version": self.version,
        }

    # -- explanation -----------------------------------------------------
    def _contributions(self, df: pd.DataFrame, top_n: int = 7) -> list[dict]:
        """Per-prediction feature attributions from LightGBM SHAP values.

        `pred_contrib` returns exact tree SHAP values, so these sum to the
        prediction rather than being a global importance ranking reused as if
        it explained this trip. Values are in log-space, so we convert each
        contribution to the seconds it added or removed.
        """
        feats = self.pipeline.transform(df)
        booster = self.boosters["main"]
        contrib = booster.predict(feats, pred_contrib=True, num_iteration=booster.best_iteration)
        row = np.asarray(contrib)[0]
        names = list(booster.feature_name())
        base = float(row[-1])  # last column is the expected value

        running = base
        items = []
        for name, value in sorted(
            zip(names, row[:-1], strict=False), key=lambda kv: abs(kv[1]), reverse=True
        )[:top_n]:
            before = np.expm1(running)
            running_after = running + float(value)
            items.append(
                {
                    "feature": name,
                    "label": _label(name),
                    "contribution_s": round(float(np.expm1(running_after) - before), 1),
                }
            )
            running = running_after
        return items
