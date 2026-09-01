"""Fare calculator tests.

The rate card is deterministic, so these are exact-value assertions rather
than tolerance checks -- if a rate changes, a test should say so loudly.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from nyctaxi.fare import (
    CONGESTION_SURCHARGE,
    CRZ_FEE,
    IMPROVEMENT_SURCHARGE,
    INITIAL_CHARGE,
    JFK_FLAT_FARE,
    MTA_TAX,
    OVERNIGHT_SURCHARGE,
    RUSH_HOUR_SURCHARGE,
    UNIT_CHARGE,
    estimate_fare,
)

# A quiet Wednesday midday in Brooklyn: no time or location surcharges.
NEUTRAL_TIME = datetime(2016, 3, 2, 13, 0)
BROOKLYN = (40.678, -73.944)
MIDTOWN = (40.758, -73.985)
JFK = (40.6413, -73.7781)

FIXED_FEES = MTA_TAX + IMPROVEMENT_SURCHARGE


class TestMeterMechanic:
    def test_fast_trip_is_charged_on_distance(self):
        """Above 12 mph the distance rule dominates: 5 miles = 25 units."""
        f = estimate_fare(
            distance_km=5 * 1.609344, duration_s=15 * 60, when=NEUTRAL_TIME,
            pickup=BROOKLYN, dropoff=BROOKLYN,
        )
        assert f.distance_time_charge == pytest.approx(25 * UNIT_CHARGE, abs=0.01)
        assert f.total == pytest.approx(INITIAL_CHARGE + 25 * UNIT_CHARGE + FIXED_FEES, abs=0.01)

    def test_slow_trip_is_charged_on_time(self):
        """Below 12 mph the time rule dominates: 30 min stuck = 30 units."""
        f = estimate_fare(
            distance_km=1.0, duration_s=30 * 60, when=NEUTRAL_TIME,
            pickup=BROOKLYN, dropoff=BROOKLYN,
        )
        assert f.distance_time_charge == pytest.approx(30 * UNIT_CHARGE, abs=0.01)

    def test_rules_coincide_at_twelve_mph(self):
        """The crossover is exact: 12 mph is 0.2 miles per minute."""
        miles, minutes = 4.0, 20.0  # exactly 12 mph
        f = estimate_fare(miles * 1.609344, minutes * 60, NEUTRAL_TIME, BROOKLYN, BROOKLYN)
        assert f.distance_time_charge == pytest.approx(20 * UNIT_CHARGE, abs=0.02)

    def test_zero_distance_still_charges_the_drop(self):
        f = estimate_fare(0.0, 0.0, NEUTRAL_TIME, BROOKLYN, BROOKLYN)
        assert f.total == pytest.approx(INITIAL_CHARGE + FIXED_FEES, abs=0.01)


class TestSurcharges:
    def test_weekday_evening_adds_rush_hour(self):
        rush = estimate_fare(5.0, 900, datetime(2016, 3, 2, 17, 30), BROOKLYN, BROOKLYN)
        calm = estimate_fare(5.0, 900, NEUTRAL_TIME, BROOKLYN, BROOKLYN)
        assert rush.rush_hour_surcharge == RUSH_HOUR_SURCHARGE
        assert calm.rush_hour_surcharge == 0.0
        assert rush.total - calm.total == pytest.approx(RUSH_HOUR_SURCHARGE, abs=0.01)

    def test_weekend_evening_has_no_rush_hour(self):
        # 2016-03-05 is a Saturday.
        f = estimate_fare(5.0, 900, datetime(2016, 3, 5, 17, 30), BROOKLYN, BROOKLYN)
        assert f.rush_hour_surcharge == 0.0

    def test_late_night_adds_overnight(self):
        f = estimate_fare(5.0, 900, datetime(2016, 3, 2, 23, 0), BROOKLYN, BROOKLYN)
        assert f.overnight_surcharge == OVERNIGHT_SURCHARGE

    def test_manhattan_adds_congestion_and_crz(self):
        inside = estimate_fare(5.0, 900, NEUTRAL_TIME, MIDTOWN, MIDTOWN)
        outside = estimate_fare(5.0, 900, NEUTRAL_TIME, BROOKLYN, BROOKLYN)
        assert inside.congestion_surcharge == CONGESTION_SURCHARGE
        assert inside.crz_fee == CRZ_FEE
        assert outside.congestion_surcharge == 0.0
        assert inside.total - outside.total == pytest.approx(
            CONGESTION_SURCHARGE + CRZ_FEE, abs=0.01
        )

    def test_surcharges_apply_when_only_one_end_is_in_manhattan(self):
        f = estimate_fare(9.0, 1800, NEUTRAL_TIME, BROOKLYN, MIDTOWN)
        assert f.congestion_surcharge == CONGESTION_SURCHARGE


class TestJfkFlatFare:
    def test_manhattan_to_jfk_is_flat(self):
        f = estimate_fare(26.0, 45 * 60, NEUTRAL_TIME, MIDTOWN, JFK)
        assert f.is_flat_fare
        assert f.base_fare == JFK_FLAT_FARE
        assert f.distance_time_charge == 0.0

    def test_flat_fare_does_not_depend_on_traffic(self):
        quick = estimate_fare(26.0, 30 * 60, NEUTRAL_TIME, MIDTOWN, JFK)
        slow = estimate_fare(26.0, 90 * 60, NEUTRAL_TIME, MIDTOWN, JFK)
        assert quick.total == slow.total

    def test_jfk_to_brooklyn_is_metered_not_flat(self):
        f = estimate_fare(15.0, 25 * 60, NEUTRAL_TIME, JFK, BROOKLYN)
        assert not f.is_flat_fare
        assert f.distance_time_charge > 0


class TestOutputShape:
    def test_total_equals_sum_of_parts(self):
        f = estimate_fare(8.0, 1500, datetime(2016, 3, 2, 17, 30), MIDTOWN, BROOKLYN)
        parts = (
            f.base_fare + f.distance_time_charge + f.rush_hour_surcharge
            + f.overnight_surcharge + f.congestion_surcharge + f.crz_fee
            + f.mta_tax + f.improvement_surcharge
        )
        assert f.total == pytest.approx(parts, abs=0.02)

    def test_longer_trips_never_cost_less(self):
        fares = [
            estimate_fare(km, km / 20 * 3600, NEUTRAL_TIME, BROOKLYN, BROOKLYN).total
            for km in (1, 3, 6, 12, 25)
        ]
        assert fares == sorted(fares)

    def test_notes_and_dict_round_trip(self):
        f = estimate_fare(5.0, 900, NEUTRAL_TIME, MIDTOWN, BROOKLYN)
        assert f.notes and all(isinstance(n, str) for n in f.notes)
        assert f.to_dict()["total"] == f.total

    def test_missing_coordinates_skip_location_surcharges(self):
        f = estimate_fare(5.0, 900, NEUTRAL_TIME)
        assert f.congestion_surcharge == 0.0 and f.crz_fee == 0.0
