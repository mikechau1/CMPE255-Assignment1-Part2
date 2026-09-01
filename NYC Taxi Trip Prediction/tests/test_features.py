"""Feature engineering tests, including the leakage guard."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nyctaxi.clean import CleaningReport, clean, haversine_km
from nyctaxi.features import FeaturePipeline, base_features, bearing_deg, manhattan_km


def make_trips(n: int = 800, seed: int = 0) -> pd.DataFrame:
    """Synthetic but plausible Manhattan trips."""
    rng = np.random.default_rng(seed)
    plat = rng.uniform(40.70, 40.80, n)
    plon = rng.uniform(-74.01, -73.93, n)
    dlat = plat + rng.normal(0, 0.02, n)
    dlon = plon + rng.normal(0, 0.02, n)
    km = haversine_km(plat, plon, dlat, dlon)
    return pd.DataFrame(
        {
            "pickup_datetime": pd.date_range("2016-01-01", periods=n, freq="7min"),
            "pickup_lat": plat,
            "pickup_lon": plon,
            "dropoff_lat": dlat,
            "dropoff_lon": dlon,
            "passenger_count": rng.integers(1, 5, n),
            # ~18 km/h plus noise, floored so nothing violates the speed rule
            "trip_duration_s": np.clip(km / 18.0 * 3600.0 + rng.normal(0, 45, n), 60, None),
        }
    )


class TestDistance:
    def test_haversine_matches_known_distance(self):
        # Times Square -> JFK is about 21.4 km great-circle.
        d = haversine_km(
            np.array([40.7580]), np.array([-73.9855]), np.array([40.6413]), np.array([-73.7781])
        )[0]
        assert 20.5 < d < 22.5

    def test_haversine_is_zero_for_identical_points(self):
        d = haversine_km(np.array([40.75]), np.array([-73.98]), np.array([40.75]), np.array([-73.98]))
        assert d[0] == pytest.approx(0.0, abs=1e-9)

    def test_haversine_is_symmetric(self):
        a = haversine_km(np.array([40.75]), np.array([-73.98]), np.array([40.64]), np.array([-73.78]))
        b = haversine_km(np.array([40.64]), np.array([-73.78]), np.array([40.75]), np.array([-73.98]))
        assert a[0] == pytest.approx(b[0])

    def test_manhattan_legs_sum_to_at_least_straight_line(self):
        """The grid route can never be shorter than the crow-flies distance."""
        lat1, lon1 = np.array([40.75]), np.array([-74.00])
        lat2, lon2 = np.array([40.78]), np.array([-73.95])
        ns, ew = manhattan_km(lat1, lon1, lat2, lon2)
        straight = haversine_km(lat1, lon1, lat2, lon2)[0]
        assert ns[0] + ew[0] >= straight - 1e-9


class TestBearing:
    @pytest.mark.parametrize(
        "dlat,dlon,expected",
        [(0.05, 0.0, 0.0), (0.0, 0.05, 90.0), (-0.05, 0.0, 180.0), (0.0, -0.05, 270.0)],
    )
    def test_cardinal_directions(self, dlat, dlon, expected):
        b = bearing_deg(
            np.array([40.75]), np.array([-73.98]),
            np.array([40.75 + dlat]), np.array([-73.98 + dlon]),
        )[0]
        assert b == pytest.approx(expected, abs=1.0)


class TestBaseFeatures:
    def test_cyclic_time_encoding_wraps(self):
        """23:59 and 00:01 must be neighbours, not opposite ends of a range."""
        df = pd.DataFrame(
            {
                "pickup_datetime": pd.to_datetime(["2016-01-01 23:59", "2016-01-02 00:01"]),
                "pickup_lat": [40.75, 40.75],
                "pickup_lon": [-73.98, -73.98],
                "dropoff_lat": [40.76, 40.76],
                "dropoff_lon": [-73.97, -73.97],
                "passenger_count": [1, 1],
            }
        )
        f = base_features(df)
        distance = np.hypot(
            f["tod_sin"].iloc[0] - f["tod_sin"].iloc[1],
            f["tod_cos"].iloc[0] - f["tod_cos"].iloc[1],
        )
        assert distance < 0.02

    def test_weekend_and_rush_hour_flags(self):
        df = pd.DataFrame(
            {
                # 2016-01-02 is a Saturday; 2016-01-04 08:00 is a Monday rush hour
                "pickup_datetime": pd.to_datetime(["2016-01-02 12:00", "2016-01-04 08:00"]),
                "pickup_lat": [40.75, 40.75],
                "pickup_lon": [-73.98, -73.98],
                "dropoff_lat": [40.76, 40.76],
                "dropoff_lon": [-73.97, -73.97],
                "passenger_count": [1, 1],
            }
        )
        f = base_features(df)
        assert f["is_weekend"].tolist() == [1, 0]
        assert f["is_rush_hour"].tolist() == [0, 1]

    def test_no_nulls_produced(self):
        f = base_features(make_trips(200))
        assert not f.isna().any().any()


class TestPipelineLeakage:
    """The property that matters most: out-of-fold encoding must not leak."""

    def test_fit_transform_and_transform_agree_in_shape(self):
        df = make_trips(600)
        y = df["trip_duration_s"].to_numpy()
        p = FeaturePipeline(n_clusters=8, n_folds=3, seed=0)
        train = p.fit_transform(df, y)
        held = p.transform(make_trips(120, seed=9))
        assert list(train.columns) == list(held.columns)
        assert len(held) == 120

    def test_out_of_fold_encoding_differs_from_full_fit(self):
        """If OOF values equalled the full-data values, each row would be
        seeing its own target -- which is exactly the leak we are preventing."""
        df = make_trips(600)
        y = df["trip_duration_s"].to_numpy()
        p = FeaturePipeline(n_clusters=8, n_folds=3, seed=0)
        oof = p.fit_transform(df, y)
        full = p.transform(df)
        col = "speed__pickup_cluster_x_hour"
        assert not np.allclose(oof[col].to_numpy(), full[col].to_numpy())

    def test_transform_before_fit_raises(self):
        with pytest.raises(RuntimeError, match="before fit_transform"):
            FeaturePipeline().transform(make_trips(10))

    def test_unseen_category_falls_back_to_global_mean(self):
        """A cluster pair never seen in training must not produce NaN."""
        df = make_trips(400)
        p = FeaturePipeline(n_clusters=5, n_folds=3, seed=0)
        p.fit_transform(df, df["trip_duration_s"].to_numpy())
        out = p.transform(make_trips(40, seed=123))
        assert not out.isna().any().any()


class TestCleaning:
    def test_removes_out_of_bbox_and_reports_it(self):
        df = make_trips(100)
        df.loc[0, "pickup_lat"] = 51.5  # London
        cleaned, report = clean(df)
        assert len(cleaned) == 99
        assert isinstance(report, CleaningReport)
        bbox_step = next(s for s in report.steps if s.rule == "inside_nyc_bbox")
        assert bbox_step.removed == 1

    def test_removes_implausible_durations(self):
        df = make_trips(100)
        df.loc[1, "trip_duration_s"] = 5.0        # too short
        df.loc[2, "trip_duration_s"] = 50_000.0   # too long
        cleaned, report = clean(df)
        step = next(s for s in report.steps if s.rule == "plausible_duration")
        assert step.removed == 2
        assert len(cleaned) == 98

    def test_report_row_counts_are_consistent(self):
        df = make_trips(200)
        df.loc[0, "pickup_lat"] = 51.5
        _, report = clean(df)
        assert report.rows_in == 200
        assert report.steps[-1].remaining == report.rows_out
        assert 0 < report.pct_kept <= 100

    def test_markdown_report_renders(self):
        _, report = clean(make_trips(50))
        md = report.to_markdown()
        assert "Rows in:" in md and "inside_nyc_bbox" in md
