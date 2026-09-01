/** Typed client for the FastAPI backend. Relative URLs work in dev (Vite
 *  proxies /api to :8000) and in production (FastAPI serves this bundle). */

import type {
  CurveResponse,
  GeocodeResult,
  HealthResponse,
  LatLon,
  ModelInfo,
  PredictResponse,
  ResidualsResponse,
  RouteResponse,
  ZoneTravelTime,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

export interface TripRequest {
  pickup: LatLon;
  dropoff: LatLon;
  departure?: string;
  passengers?: number;
  road_distance_km?: number | null;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),

  predict: (body: TripRequest) =>
    request<PredictResponse>("/api/predict", { method: "POST", body: JSON.stringify(body) }),

  curve: (body: TripRequest) =>
    request<CurveResponse>("/api/predict/curve", { method: "POST", body: JSON.stringify(body) }),

  route: (from: LatLon, to: LatLon) =>
    request<RouteResponse>(
      `/api/route?from_lat=${from.lat}&from_lon=${from.lon}&to_lat=${to.lat}&to_lon=${to.lon}`,
    ),

  geocode: (q: string) =>
    request<{ results: GeocodeResult[] }>(`/api/geocode?q=${encodeURIComponent(q)}`).then(
      (r) => r.results,
    ),

  model: () => request<ModelInfo>("/api/model"),

  residuals: () => request<ResidualsResponse>("/api/model/residuals"),

  zones: () => request<GeoJSON.FeatureCollection>("/api/zones"),

  zoneTravelTimes: (body: TripRequest) =>
    request<ZoneTravelTime>("/api/zones/travel-time", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
