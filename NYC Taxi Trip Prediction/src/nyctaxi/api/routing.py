"""Server-side proxies for OSRM routing and Nominatim geocoding.

Why proxy instead of calling these from the browser:
  * Nominatim's usage policy requires an identifying User-Agent and rate
    limiting. A browser cannot set User-Agent, and every user's tab would be
    an independent uncached client.
  * Caching here means a repeated lookup costs nothing and we stay a polite
    consumer of two free public services.
  * It sidesteps CORS entirely.

Both are best-effort. If either service is slow or down, the caller gets None
and the UI falls back to a straight line -- a degraded map beats a broken one.

IMPORTANT: the route returned here is display and fare input only. It is never
a model feature. Calling OSRM once per row is infeasible at training time, so
using it at inference would create train/serve skew -- the model would depend
on a signal it never learned from.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache

import httpx

from ..config import get_config
from ..logging_utils import get_logger

log = get_logger(__name__)

# Nominatim asks for at most 1 request/second. One global lock plus a small
# delay keeps us inside that no matter how many browser tabs are open.
_nominatim_lock = asyncio.Lock()
_NOMINATIM_MIN_INTERVAL_S = 1.1


@lru_cache(maxsize=1024)
def _route_cache_key(coords: str) -> str:
    return coords


class ExternalServices:
    """Thin async client over OSRM + Nominatim, with in-process caching."""

    def __init__(self):
        cfg = get_config().api
        self.cfg = cfg
        self._client = httpx.AsyncClient(
            timeout=cfg.external_timeout_s,
            headers={"User-Agent": cfg.user_agent},
            follow_redirects=True,
        )
        self._route_cache: dict[str, dict | None] = {}
        self._geocode_cache: dict[str, list] = {}
        self._last_nominatim_call = 0.0

    async def aclose(self) -> None:
        await self._client.aclose()

    def _trim_cache(self, cache: dict) -> None:
        while len(cache) > self.cfg.cache_size:
            cache.pop(next(iter(cache)))

    async def route(
        self, pickup: tuple[float, float], dropoff: tuple[float, float]
    ) -> dict | None:
        """Driving route between two points, as GeoJSON geometry + totals."""
        # Round to ~11 m: a pin nudged by a metre should reuse the cached route.
        key = f"{pickup[0]:.4f},{pickup[1]:.4f};{dropoff[0]:.4f},{dropoff[1]:.4f}"
        if key in self._route_cache:
            return self._route_cache[key]

        url = (
            f"{self.cfg.osrm_url}/route/v1/driving/"
            f"{pickup[1]},{pickup[0]};{dropoff[1]},{dropoff[0]}"
        )
        try:
            r = await self._client.get(url, params={"overview": "full", "geometries": "geojson"})
            r.raise_for_status()
            data = r.json()
            if data.get("code") != "Ok" or not data.get("routes"):
                raise ValueError(f"OSRM returned {data.get('code')!r}")
            best = data["routes"][0]
            result = {
                "geometry": best["geometry"],
                "distance_km": round(best["distance"] / 1000.0, 3),
                "osrm_duration_s": round(best["duration"], 1),
            }
        except Exception as exc:
            log.warning("OSRM route failed (%s); caller falls back to straight line", exc)
            result = None

        self._route_cache[key] = result
        self._trim_cache(self._route_cache)
        return result

    async def geocode(self, query: str, limit: int = 5) -> list[dict]:
        """Address search, biased to the NYC viewbox."""
        key = f"{query.strip().lower()}|{limit}"
        if key in self._geocode_cache:
            return self._geocode_cache[key]
        if not query.strip():
            return []

        try:
            async with _nominatim_lock:
                loop = asyncio.get_event_loop()
                elapsed = loop.time() - self._last_nominatim_call
                if elapsed < _NOMINATIM_MIN_INTERVAL_S:
                    await asyncio.sleep(_NOMINATIM_MIN_INTERVAL_S - elapsed)
                r = await self._client.get(
                    f"{self.cfg.nominatim_url}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "limit": limit,
                        # bias hard to NYC -- "Broadway" should not return Nashville
                        "viewbox": "-74.30,40.95,-73.65,40.48",
                        "bounded": 1,
                        "addressdetails": 1,
                    },
                )
                self._last_nominatim_call = loop.time()
            r.raise_for_status()
            results = [
                {
                    "label": item.get("display_name", ""),
                    "short": (item.get("name") or item.get("display_name", "").split(",")[0]),
                    "lat": float(item["lat"]),
                    "lon": float(item["lon"]),
                }
                for item in r.json()
            ]
        except Exception as exc:
            log.warning("Nominatim geocode failed for %r (%s)", query, exc)
            results = []

        self._geocode_cache[key] = results
        self._trim_cache(self._geocode_cache)
        return results
