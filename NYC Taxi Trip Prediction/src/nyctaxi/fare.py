"""NYC yellow-taxi fare estimation from the published TLC rate card.

This is deliberately *not* learned. The rate card is a published, deterministic
schedule, so fitting a model to it would only add error and obscure where the
money goes. Predicted duration and distance go in, an itemised breakdown comes
out -- which also lets the UI show the rider exactly what they are paying for.

Rates: TLC standard metered fare (rates effective 2024-2025).
https://www.nyc.gov/site/tlc/passengers/taxi-fare.page

The meter mechanic worth understanding: the unit charge applies per 1/5 mile
when moving above 12 mph, and per 60 seconds when slower or stopped. Those two
rules meet exactly at 12 mph (0.2 miles/minute), so charging the *greater* of
distance-units and time-units reproduces the meter exactly rather than
approximating it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

KM_PER_MILE = 1.609344

INITIAL_CHARGE = 3.00        # drop charge
UNIT_CHARGE = 0.70           # per 1/5 mile above 12 mph, or per 60s below it
MILES_PER_UNIT = 0.2
MPH_CROSSOVER = 12.0         # where the distance and time rules coincide
MTA_TAX = 0.50
IMPROVEMENT_SURCHARGE = 1.00
RUSH_HOUR_SURCHARGE = 1.00   # weekdays 16:00-20:00, excluding holidays
OVERNIGHT_SURCHARGE = 0.50   # 20:00-06:00
CONGESTION_SURCHARGE = 2.50  # yellow cab trips touching Manhattan below 96th St
CRZ_FEE = 0.75              # NYS Congestion Relief Zone fee
JFK_FLAT_FARE = 70.00        # Manhattan <-> JFK, flat
JFK_RUSH_SURCHARGE = 5.00

# Approximate bounding boxes. Coarse on purpose: they decide surcharges worth a
# couple of dollars, and an exact boundary polygon would be false precision for
# an estimate whose duration term is itself modelled.
MANHATTAN_BELOW_96TH = {"min_lat": 40.700, "max_lat": 40.790, "min_lon": -74.021, "max_lon": -73.907}
JFK_BBOX = {"min_lat": 40.630, "max_lat": 40.665, "min_lon": -73.825, "max_lon": -73.740}


@dataclass
class FareBreakdown:
    """Itemised estimate. Every field is a dollar amount except the notes."""

    base_fare: float
    distance_time_charge: float
    rush_hour_surcharge: float
    overnight_surcharge: float
    congestion_surcharge: float
    crz_fee: float
    mta_tax: float
    improvement_surcharge: float
    total: float
    is_flat_fare: bool
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _in_bbox(lat: float, lon: float, box: dict) -> bool:
    return box["min_lat"] <= lat <= box["max_lat"] and box["min_lon"] <= lon <= box["max_lon"]


def _is_rush_hour(when: datetime) -> bool:
    """Weekdays 16:00-19:59. (Holidays are exempt; not modelled here.)"""
    return when.weekday() < 5 and 16 <= when.hour < 20


def _is_overnight(when: datetime) -> bool:
    return when.hour >= 20 or when.hour < 6


def estimate_fare(
    distance_km: float,
    duration_s: float,
    when: datetime,
    pickup: tuple[float, float] | None = None,
    dropoff: tuple[float, float] | None = None,
) -> FareBreakdown:
    """Estimate the metered fare for a trip.

    `pickup`/`dropoff` are (lat, lon) and only affect location-based
    surcharges; omit them and those are simply not applied. Tolls are excluded
    -- they depend on the route the driver picks, which we do not control.
    """
    notes: list[str] = []
    miles = max(distance_km, 0.0) / KM_PER_MILE
    minutes = max(duration_s, 0.0) / 60.0

    manhattan = any(
        p is not None and _in_bbox(p[0], p[1], MANHATTAN_BELOW_96TH) for p in (pickup, dropoff)
    )
    jfk = any(p is not None and _in_bbox(p[0], p[1], JFK_BBOX) for p in (pickup, dropoff))

    rush = _is_rush_hour(when)
    overnight = _is_overnight(when)

    # --- JFK <-> Manhattan is a flat fare, not a metered one ---
    if jfk and manhattan:
        base = JFK_FLAT_FARE
        meter = 0.0
        flat = True
        rush_charge = JFK_RUSH_SURCHARGE if rush else 0.0
        overnight_charge = 0.0  # not applied on the JFK flat fare
        notes.append("JFK <-> Manhattan flat fare applies; the meter is not used.")
        if rush:
            notes.append("Weekday 16:00-20:00 JFK surcharge added.")
    else:
        base = INITIAL_CHARGE
        # The meter charges per 1/5 mile above 12 mph and per minute below it.
        # Those rules coincide at 12 mph, so the greater of the two *is* the meter.
        distance_units = miles / MILES_PER_UNIT
        time_units = minutes
        units = max(distance_units, time_units)
        meter = units * UNIT_CHARGE
        flat = False
        rush_charge = RUSH_HOUR_SURCHARGE if rush else 0.0
        overnight_charge = OVERNIGHT_SURCHARGE if overnight else 0.0
        avg_mph = miles / (minutes / 60.0) if minutes > 0 else 0.0
        notes.append(
            f"Metered on {'time' if time_units > distance_units else 'distance'} "
            f"(average {avg_mph:.1f} mph vs the {MPH_CROSSOVER:g} mph crossover)."
        )
        if rush:
            notes.append("Weekday 16:00-20:00 rush-hour surcharge added.")
        if overnight:
            notes.append("Overnight (20:00-06:00) surcharge added.")

    congestion = CONGESTION_SURCHARGE if manhattan else 0.0
    crz = CRZ_FEE if manhattan else 0.0
    if manhattan:
        notes.append("Trip touches Manhattan below 96th St: congestion surcharge and CRZ fee.")

    total = (
        base
        + meter
        + rush_charge
        + overnight_charge
        + congestion
        + crz
        + MTA_TAX
        + IMPROVEMENT_SURCHARGE
    )
    notes.append("Excludes tolls, tip, and any airport access fees.")

    return FareBreakdown(
        base_fare=round(base, 2),
        distance_time_charge=round(meter, 2),
        rush_hour_surcharge=round(rush_charge, 2),
        overnight_surcharge=round(overnight_charge, 2),
        congestion_surcharge=round(congestion, 2),
        crz_fee=round(crz, 2),
        mta_tax=MTA_TAX,
        improvement_surcharge=IMPROVEMENT_SURCHARGE,
        total=round(total, 2),
        is_flat_fare=flat,
        notes=notes,
    )
