"""Request/response contracts for the API.

These are the seam between the model and the UI. Keeping them explicit (rather
than passing dicts around) means the frontend's TypeScript types have something
real to mirror, and bad input is rejected at the edge with a clear message.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# Generous bounds around the NYC metro area. Rejecting a request from London
# with a clear error beats returning a confident nonsense ETA.
LAT_MIN, LAT_MAX = 40.4, 41.1
LON_MIN, LON_MAX = -74.5, -73.5


class Point(BaseModel):
    lat: float = Field(..., ge=LAT_MIN, le=LAT_MAX, description="Latitude, NYC metro area")
    lon: float = Field(..., ge=LON_MIN, le=LON_MAX, description="Longitude, NYC metro area")


class PredictRequest(BaseModel):
    pickup: Point
    dropoff: Point
    departure: datetime | None = Field(None, description="Departure time; defaults to now.")
    passengers: int = Field(1, ge=1, le=6)
    # Road distance from the routing service, when the client has one. The
    # model never uses it as a feature (see routing.py) -- it is passed through
    # for the fare calculation and display only.
    road_distance_km: float | None = Field(None, ge=0, le=200)


class FeatureContribution(BaseModel):
    feature: str
    label: str
    contribution_s: float


class DurationEstimate(BaseModel):
    p10_s: float
    p50_s: float
    p90_s: float
    point_s: float
    eta: datetime


class PredictResponse(BaseModel):
    duration: DurationEstimate
    straight_line_km: float
    distance_km: float
    distance_source: str
    fare: dict
    contributions: list[FeatureContribution]
    model_version: str
    zone_resolution: bool


class CurvePoint(BaseModel):
    hour: int
    p10_s: float
    p50_s: float
    p90_s: float


class CurveResponse(BaseModel):
    """Duration across all 24 departure hours, for the same trip."""

    points: list[CurvePoint]
    best_hour: int
    worst_hour: int
    model_version: str
