"""Metric definitions and taxi-zone geometry."""

from __future__ import annotations

import numpy as np
import pytest

from nyctaxi.data.zones import point_in_ring, ring_area, ring_centroid
from nyctaxi.metrics import interval_coverage, mae, mape, r2, rmsle, score_all

# A unit square, counter-clockwise.
SQUARE = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


class TestMetrics:
    def test_perfect_prediction_scores_zero_error(self):
        y = np.array([100.0, 500.0, 2000.0])
        assert rmsle(y, y) == pytest.approx(0.0)
        assert mae(y, y) == pytest.approx(0.0)
        assert r2(y, y) == pytest.approx(1.0)

    def test_rmsle_penalises_ratio_not_absolute_error(self):
        """The reason RMSLE is the headline metric: a 5-minute miss on a short
        trip must score worse than the same miss on a long one."""
        short_miss = rmsle(np.array([360.0]), np.array([660.0]))     # 6 -> 11 min
        long_miss = rmsle(np.array([5400.0]), np.array([5700.0]))    # 90 -> 95 min
        assert short_miss > long_miss * 5

    def test_rmsle_is_symmetric_in_log_space(self):
        a = rmsle(np.array([100.0]), np.array([200.0]))
        b = rmsle(np.array([200.0]), np.array([100.0]))
        assert a == pytest.approx(b, rel=1e-6)

    def test_mape_ignores_zero_targets(self):
        assert np.isfinite(mape(np.array([0.0, 100.0]), np.array([50.0, 110.0])))

    def test_score_all_returns_the_full_metric_set(self):
        y = np.array([300.0, 600.0, 900.0])
        scores = score_all(y, y * 1.1)
        assert set(scores) == {"rmsle", "rmse_s", "mae_s", "mape_pct", "r2"}
        assert scores["mape_pct"] == pytest.approx(10.0, abs=0.01)


class TestIntervalCoverage:
    def test_full_coverage_when_band_contains_everything(self):
        y = np.array([100.0, 200.0, 300.0])
        cov = interval_coverage(y, y - 50, y + 50)
        assert cov["coverage_pct"] == 100.0
        assert cov["mean_width_s"] == pytest.approx(100.0)

    def test_zero_coverage_when_band_misses(self):
        y = np.array([100.0, 200.0])
        assert interval_coverage(y, y + 10, y + 20)["coverage_pct"] == 0.0

    def test_boundary_values_count_as_inside(self):
        y = np.array([100.0])
        assert interval_coverage(y, np.array([100.0]), np.array([100.0]))["coverage_pct"] == 100.0

    def test_nominal_is_eighty_percent(self):
        cov = interval_coverage(np.array([1.0]), np.array([0.0]), np.array([2.0]))
        assert cov["nominal_pct"] == 80.0


class TestPolygonHelpers:
    def test_unit_square_area(self):
        assert abs(ring_area(SQUARE)) == pytest.approx(1.0)

    def test_winding_order_flips_the_sign(self):
        assert ring_area(SQUARE) == pytest.approx(-ring_area(list(reversed(SQUARE))))

    def test_square_centroid_is_its_middle(self):
        cx, cy = ring_centroid(SQUARE)
        assert (cx, cy) == (pytest.approx(0.5), pytest.approx(0.5))

    def test_degenerate_ring_falls_back_to_vertex_mean(self):
        line = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
        cx, _ = ring_centroid(line)
        assert cx == pytest.approx(1.0)

    @pytest.mark.parametrize(
        "pt,inside",
        [((0.5, 0.5), True), ((0.01, 0.01), True), ((1.5, 0.5), False), ((-0.5, 0.5), False)],
    )
    def test_point_in_ring(self, pt, inside):
        assert point_in_ring(pt[0], pt[1], SQUARE) is inside

    def test_concave_polygon_excludes_the_notch(self):
        """An L-shape: the cut-out corner must read as outside."""
        l_shape = [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)]
        assert point_in_ring(0.5, 0.5, l_shape) is True
        assert point_in_ring(1.5, 1.5, l_shape) is False
