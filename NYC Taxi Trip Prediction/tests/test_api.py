"""API contract tests.

Tests that need a trained model skip cleanly when none exists, so a fresh
clone (and CI, which does not train) still runs a meaningful suite.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nyctaxi import registry
from nyctaxi.api.main import app

MODEL_AVAILABLE = registry.latest_version() is not None
needs_model = pytest.mark.skipif(MODEL_AVAILABLE is False, reason="no trained model available")

TIMES_SQUARE = {"lat": 40.7580, "lon": -73.9855}
JFK = {"lat": 40.6413, "lon": -73.7781}
BROOKLYN = {"lat": 40.678, "lon": -73.944}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def trip(**overrides) -> dict:
    body = {
        "pickup": TIMES_SQUARE,
        "dropoff": JFK,
        "departure": "2016-03-02T17:30:00",
        "passengers": 2,
    }
    body.update(overrides)
    return body


class TestHealth:
    def test_health_always_answers(self, client):
        """Health must work even with no model -- that is what it reports."""
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("ok", "degraded")
        assert body["model_loaded"] is MODEL_AVAILABLE


class TestValidation:
    """Bad input is rejected at the edge rather than producing a confident
    nonsense answer."""

    def test_coordinates_outside_nyc_are_rejected(self, client):
        r = client.post("/api/predict", json=trip(pickup={"lat": 51.5, "lon": -0.12}))
        assert r.status_code == 422

    def test_too_many_passengers_rejected(self, client):
        assert client.post("/api/predict", json=trip(passengers=9)).status_code == 422

    def test_zero_passengers_rejected(self, client):
        assert client.post("/api/predict", json=trip(passengers=0)).status_code == 422

    def test_missing_dropoff_rejected(self, client):
        assert client.post("/api/predict", json={"pickup": TIMES_SQUARE}).status_code == 422

    def test_short_geocode_query_rejected(self, client):
        assert client.get("/api/geocode?q=a").status_code == 422


@needs_model
class TestPredict:
    def test_returns_a_coherent_estimate(self, client):
        body = client.post("/api/predict", json=trip()).json()
        d = body["duration"]
        assert d["p10_s"] <= d["p50_s"] <= d["p90_s"], "quantiles must not cross"
        assert d["point_s"] > 0
        assert body["straight_line_km"] == pytest.approx(21.8, abs=1.5)
        assert body["fare"]["total"] > 0
        assert body["model_version"]

    def test_midtown_to_jfk_is_plausible(self, client):
        """A sanity floor and ceiling: this trip is never 5 minutes or 5 hours."""
        d = client.post("/api/predict", json=trip()).json()["duration"]
        assert 15 * 60 < d["point_s"] < 150 * 60

    def test_longer_trip_predicts_longer_duration(self, client):
        short = client.post("/api/predict", json=trip(dropoff=BROOKLYN)).json()
        long = client.post("/api/predict", json=trip()).json()
        assert long["duration"]["point_s"] > short["duration"]["point_s"]

    def test_rush_hour_is_slower_than_predawn(self, client):
        rush = client.post("/api/predict", json=trip(departure="2016-03-02T17:30:00")).json()
        quiet = client.post("/api/predict", json=trip(departure="2016-03-02T04:00:00")).json()
        assert rush["duration"]["point_s"] > quiet["duration"]["point_s"]

    def test_road_distance_is_used_for_fare_when_supplied(self, client):
        with_road = client.post("/api/predict", json=trip(road_distance_km=27.9)).json()
        assert with_road["distance_source"] == "osrm_route"
        assert with_road["distance_km"] == pytest.approx(27.9, abs=0.01)

    def test_contributions_are_returned_and_labelled(self, client):
        contribs = client.post("/api/predict", json=trip()).json()["contributions"]
        assert contribs
        assert all(c["label"] and "contribution_s" in c for c in contribs)

    def test_jfk_trip_uses_flat_fare(self, client):
        fare = client.post("/api/predict", json=trip()).json()["fare"]
        assert fare["is_flat_fare"] is True


@needs_model
class TestCurve:
    def test_returns_all_twenty_four_hours(self, client):
        body = client.post("/api/predict/curve", json=trip()).json()
        assert [p["hour"] for p in body["points"]] == list(range(24))
        assert 0 <= body["best_hour"] <= 23
        assert 0 <= body["worst_hour"] <= 23

    def test_best_hour_is_actually_the_fastest(self, client):
        body = client.post("/api/predict/curve", json=trip()).json()
        fastest = min(body["points"], key=lambda p: p["p50_s"])
        assert fastest["hour"] == body["best_hour"]

    def test_quantiles_never_cross_on_the_curve(self, client):
        body = client.post("/api/predict/curve", json=trip()).json()
        assert all(p["p10_s"] <= p["p50_s"] <= p["p90_s"] for p in body["points"])


@needs_model
class TestModelReport:
    def test_exposes_metrics_and_metadata(self, client):
        body = client.get("/api/model").json()
        assert body["metrics"]["leaderboard"]
        assert body["metrics"]["production_model"] == "lightgbm"
        assert body["metadata"]["data_source"] in ("kaggle", "tlc")

    def test_lightgbm_beats_every_baseline(self, client):
        """The ladder has to actually go somewhere."""
        board = client.get("/api/model").json()["metrics"]["leaderboard"]
        lgbm = next(r for r in board if r["model"] == "lightgbm")
        baselines = [r for r in board if r["model"] != "lightgbm"]
        assert all(lgbm["rmsle"] < b["rmsle"] for b in baselines)

    def test_residuals_endpoint_returns_slices(self, client):
        body = client.get("/api/model/residuals?limit=500").json()
        assert len(body["points"]) <= 500
        assert body["by_hour"] and body["by_distance"]


class TestZones:
    def test_zone_geojson_has_all_263_zones(self, client):
        body = client.get("/api/zones").json()
        assert body["type"] == "FeatureCollection"
        assert len(body["features"]) == 263
        props = body["features"][0]["properties"]
        assert {"location_id", "zone", "borough", "centroid_lat", "centroid_lon"} <= props.keys()

    @needs_model
    def test_travel_times_cover_every_zone(self, client):
        body = client.post("/api/zones/travel-time", json=trip(dropoff=TIMES_SQUARE)).json()
        assert len(body["zones"]) == 263
        assert body["min_s"] < body["max_s"]

    @needs_model
    def test_times_square_is_closest_to_itself(self, client):
        """A geographic sanity check on the whole prediction path."""
        body = client.post("/api/zones/travel-time", json=trip(dropoff=TIMES_SQUARE)).json()
        nearest = min(body["zones"], key=lambda z: z["duration_s"])
        assert nearest["borough"] == "Manhattan"
