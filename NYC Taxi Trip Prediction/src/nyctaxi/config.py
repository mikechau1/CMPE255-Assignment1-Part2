"""Typed access to config.yaml.

Every module reads its knobs from here rather than hard-coding constants, so
config.yaml stays the single place a reviewer has to look to see how the
pipeline was parameterised.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# repo root == three parents up from src/nyctaxi/config.py
ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config.yaml"


class Paths(BaseModel):
    data_raw: str
    data_interim: str
    data_processed: str
    data_geo: str
    models: str
    figures: str
    frontend_dist: str

    def resolve(self, key: str) -> Path:
        """Absolute path for a configured directory, created if missing."""
        p = ROOT / getattr(self, key)
        p.mkdir(parents=True, exist_ok=True)
        return p


class DataCfg(BaseModel):
    source: str = "auto"
    kaggle_competition: str
    tlc_months: list[str]
    tlc_base_url: str
    tlc_zone_shapefile_url: str
    tlc_zone_lookup_url: str


class BBox(BaseModel):
    min_lon: float
    max_lon: float
    min_lat: float
    max_lat: float


class CleanCfg(BaseModel):
    nyc_bbox: BBox
    min_duration_s: int
    max_duration_s: int
    max_speed_kmh: float
    min_speed_kmh: float
    max_haversine_km: float
    max_passengers: int


class FeatureCfg(BaseModel):
    n_clusters: int
    target_encode_folds: int
    target_encode_smoothing: float


class SplitCfg(BaseModel):
    strategy: str
    valid_frac: float


class ModelCfg(BaseModel):
    target: str
    quantiles: list[float]
    lightgbm: dict[str, Any]


class ApiCfg(BaseModel):
    osrm_url: str
    nominatim_url: str
    user_agent: str
    cache_size: int
    external_timeout_s: float


class Config(BaseModel):
    project_name: str
    random_seed: int
    paths: Paths
    data: DataCfg
    clean: CleanCfg
    features: FeatureCfg
    split: SplitCfg
    model: ModelCfg
    api: ApiCfg = Field(...)


@functools.lru_cache(maxsize=1)
def get_config(path: Path | None = None) -> Config:
    """Load and validate config.yaml (cached)."""
    with open(path or CONFIG_PATH, encoding="utf-8") as fh:
        return Config(**yaml.safe_load(fh))
