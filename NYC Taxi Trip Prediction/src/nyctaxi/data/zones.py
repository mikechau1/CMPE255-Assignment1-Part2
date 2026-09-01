"""NYC taxi-zone geometry.

No public WGS84 GeoJSON of the 263 TLC taxi zones exists (every candidate URL
checked returns 404), so we build one: download the TLC shapefile, reproject it
from EPSG:2263 (NAD83 / New York Long Island, US survey feet) to EPSG:4326,
and cache the result.

The output is used twice:
  * the TLC fallback loader, to turn LocationIDs into plausible coordinates;
  * the frontend, as the zone-choropleth layer.

Polygon maths (area, centroid, point-in-polygon) is done by hand rather than
pulling in shapely -- it is a few dozen lines and keeps the dependency set thin.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import requests

from ..config import get_config
from ..logging_utils import get_logger

log = get_logger(__name__)

Ring = list[tuple[float, float]]

# Used when a LocationID has no usable polygon (LocationID 264/265 are the
# "Unknown" zones and ship with empty geometry).
FALLBACK_POINT = (-73.97, 40.75)


# --------------------------------------------------------------------------
# planar polygon helpers (operate on lon/lat after reprojection)
# --------------------------------------------------------------------------
def ring_area(ring: Ring) -> float:
    """Signed shoelace area. The sign encodes winding order."""
    if len(ring) < 3:
        return 0.0
    pts = np.asarray(ring, dtype=float)
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def ring_centroid(ring: Ring) -> tuple[float, float]:
    """Area-weighted centroid; falls back to the vertex mean for slivers."""
    a = ring_area(ring)
    pts = np.asarray(ring, dtype=float)
    if abs(a) < 1e-12:
        return float(pts[:, 0].mean()), float(pts[:, 1].mean())
    x, y = pts[:, 0], pts[:, 1]
    xn, yn = np.roll(x, -1), np.roll(y, -1)
    cross = x * yn - xn * y
    cx = float(np.dot(x + xn, cross) / (6.0 * a))
    cy = float(np.dot(y + yn, cross) / (6.0 * a))
    return cx, cy


def point_in_ring(lon: float, lat: float, ring: Ring) -> bool:
    """Ray-casting point-in-polygon test."""
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            x_cross = x1 + (lat - y1) / (y2 - y1) * (x2 - x1)
            if lon < x_cross:
                inside = not inside
    return inside


# --------------------------------------------------------------------------
# build / cache
# --------------------------------------------------------------------------
def download_file(url: str, dest: Path) -> Path:
    """Stream a URL to disk, skipping the work if already cached."""
    if dest.exists() and dest.stat().st_size > 0:
        log.info("cached      %s", dest.name)
        return dest
    log.info("downloading %s", url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=180) as r:
        r.raise_for_status()
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
    tmp.replace(dest)
    log.info("saved       %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
    return dest


def build_zone_geojson(force: bool = False) -> Path:
    """Produce data/geo/taxi_zones.geojson in WGS84. Idempotent."""
    cfg = get_config()
    geo_dir = cfg.paths.resolve("data_geo")
    out = geo_dir / "taxi_zones.geojson"
    if out.exists() and not force:
        return out

    import shapefile  # pyshp
    from pyproj import Transformer

    raw = cfg.paths.resolve("data_raw")
    zip_path = download_file(cfg.data.tlc_zone_shapefile_url, raw / "taxi_zones.zip")
    extract_dir = raw / "taxi_zones"
    extract_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)

    shp = next(extract_dir.rglob("*.shp"))
    reader = shapefile.Reader(str(shp))
    fields = [f[0] for f in reader.fields[1:]]
    # TLC ships the zones in NY State Plane feet; the map needs lon/lat.
    transformer = Transformer.from_crs("EPSG:2263", "EPSG:4326", always_xy=True)

    features = []
    for sr in reader.shapeRecords():
        rec = dict(zip(fields, sr.record, strict=False))
        shape = sr.shape
        if not shape.points:
            continue

        # split the flat point list into rings using the shapefile part index
        parts = list(shape.parts) + [len(shape.points)]
        rings: list[Ring] = []
        for i in range(len(parts) - 1):
            seg = shape.points[parts[i] : parts[i + 1]]
            if len(seg) < 4:
                continue
            xs, ys = transformer.transform([p[0] for p in seg], [p[1] for p in seg])
            rings.append([(float(a), float(b)) for a, b in zip(xs, ys, strict=False)])
        if not rings:
            continue

        # largest ring by |area| is the outer boundary we use for centroid/jitter
        rings.sort(key=lambda r: abs(ring_area(r)), reverse=True)
        clon, clat = ring_centroid(rings[0])

        features.append(
            {
                "type": "Feature",
                "id": int(rec.get("LocationID", 0)),
                "properties": {
                    "location_id": int(rec.get("LocationID", 0)),
                    "zone": rec.get("zone", ""),
                    "borough": rec.get("borough", ""),
                    "centroid_lon": clon,
                    "centroid_lat": clat,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[list(p) for p in rings[0]]],
                },
            }
        )

    out.write_text(json.dumps({"type": "FeatureCollection", "features": features}), "utf-8")
    log.info("built %s with %d zones", out.name, len(features))
    return out


def load_zones() -> dict:
    """Zone FeatureCollection, building it on first use."""
    return json.loads(build_zone_geojson().read_text(encoding="utf-8"))


def zone_centroids() -> dict[int, tuple[float, float]]:
    """LocationID -> (lon, lat)."""
    return {
        f["properties"]["location_id"]: (
            f["properties"]["centroid_lon"],
            f["properties"]["centroid_lat"],
        )
        for f in load_zones()["features"]
    }


def zone_rings() -> dict[int, Ring]:
    """LocationID -> outer ring, for in-polygon sampling."""
    return {
        f["properties"]["location_id"]: [tuple(p) for p in f["geometry"]["coordinates"][0]]
        for f in load_zones()["features"]
    }


def zone_metadata() -> dict[int, dict]:
    """LocationID -> {zone, borough}, for error slices and map tooltips."""
    return {
        f["properties"]["location_id"]: {
            "zone": f["properties"]["zone"],
            "borough": f["properties"]["borough"],
        }
        for f in load_zones()["features"]
    }


def sample_points_in_zones(
    location_ids: np.ndarray, seed: int = 42
) -> tuple[np.ndarray, np.ndarray]:
    """Scatter one point inside each row's zone polygon.

    The TLC fallback only knows which of 263 zones a trip started in. Putting
    every trip on its zone centroid would collapse the data onto 263 dots and
    make the distance features degenerate, so we sample inside the polygon
    instead (rejection sampling against the ring bbox, centroid as a fallback).
    Seeded, so a rerun reproduces the same dataset.
    """
    rings = zone_rings()
    centroids = zone_centroids()
    rng = np.random.default_rng(seed)

    # Pre-sample a pool per distinct zone and deal them out round-robin. Far
    # cheaper than rejection-sampling per row when rows number in the millions.
    unique_ids, inverse = np.unique(location_ids, return_inverse=True)
    per_zone = int(np.ceil(len(location_ids) / max(len(unique_ids), 1)))
    pool_size = int(np.clip(per_zone, 64, 4096))
    pools: dict[int, np.ndarray] = {}

    for raw_id in unique_ids:
        lid = int(raw_id)
        ring = rings.get(lid)
        if not ring:
            pools[lid] = np.array([centroids.get(lid, FALLBACK_POINT)])
            continue

        arr = np.asarray(ring)
        lon_lo, lon_hi = arr[:, 0].min(), arr[:, 0].max()
        lat_lo, lat_hi = arr[:, 1].min(), arr[:, 1].max()
        pts: list[tuple[float, float]] = []
        # Bounded attempts: concave zones (the airports especially) reject a lot.
        for _ in range(40):
            if len(pts) >= pool_size:
                break
            cand_lon = rng.uniform(lon_lo, lon_hi, pool_size)
            cand_lat = rng.uniform(lat_lo, lat_hi, pool_size)
            for lo, la in zip(cand_lon, cand_lat, strict=False):
                if point_in_ring(lo, la, ring):
                    pts.append((float(lo), float(la)))
                    if len(pts) >= pool_size:
                        break
        pools[lid] = np.asarray(pts if pts else [centroids.get(lid, FALLBACK_POINT)])

    # Deal the pools out zone-by-zone rather than row-by-row: a Python loop
    # over millions of rows dominates the whole load, a loop over 263 zones
    # with vectorised assignment inside is negligible.
    lons = np.empty(len(location_ids), dtype=float)
    lats = np.empty(len(location_ids), dtype=float)
    for uidx, raw_id in enumerate(unique_ids):
        rows = np.flatnonzero(inverse == uidx)
        pool = pools[int(raw_id)]
        picked = pool[np.arange(len(rows)) % len(pool)]
        lons[rows] = picked[:, 0]
        lats[rows] = picked[:, 1]
    return lons, lats
