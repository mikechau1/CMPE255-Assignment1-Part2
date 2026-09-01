"""Canonical paths for the lab. Everything resolves off the project root."""
from __future__ import annotations
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS = ROOT / ".claude" / "skills"
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
ARTIFACTS = ROOT / "artifacts"
SITE_ARTIFACTS = ROOT / "site" / "public" / "artifacts"
PIPELINE = ROOT / "pipeline"

for _p in (RAW, INTERIM, PROCESSED, ARTIFACTS, SITE_ARTIFACTS):
    _p.mkdir(parents=True, exist_ok=True)
