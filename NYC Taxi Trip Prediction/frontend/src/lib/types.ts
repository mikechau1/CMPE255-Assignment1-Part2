/** Mirrors src/nyctaxi/api/schemas.py. Keep the two in step. */

export interface LatLon {
  lat: number;
  lon: number;
}

export interface DurationEstimate {
  p10_s: number;
  p50_s: number;
  p90_s: number;
  point_s: number;
  eta: string;
}

export interface FareBreakdown {
  base_fare: number;
  distance_time_charge: number;
  rush_hour_surcharge: number;
  overnight_surcharge: number;
  congestion_surcharge: number;
  crz_fee: number;
  mta_tax: number;
  improvement_surcharge: number;
  total: number;
  is_flat_fare: boolean;
  notes: string[];
}

export interface Contribution {
  feature: string;
  label: string;
  contribution_s: number;
}

export interface PredictResponse {
  duration: DurationEstimate;
  straight_line_km: number;
  distance_km: number;
  distance_source: string;
  fare: FareBreakdown;
  contributions: Contribution[];
  model_version: string;
  zone_resolution: boolean;
}

export interface CurvePoint {
  hour: number;
  p10_s: number;
  p50_s: number;
  p90_s: number;
}

export interface CurveResponse {
  points: CurvePoint[];
  best_hour: number;
  worst_hour: number;
  model_version: string;
}

export interface RouteResponse {
  available: boolean;
  geometry?: { type: "LineString"; coordinates: [number, number][] };
  distance_km?: number;
  osrm_duration_s?: number;
  reason?: string;
}

export interface GeocodeResult {
  label: string;
  short: string;
  lat: number;
  lon: number;
}

export interface LeaderboardRow {
  model: string;
  description: string;
  train_seconds: number;
  rmsle: number;
  rmse_s: number;
  mae_s: number;
  mape_pct: number;
  r2: number;
}

export interface ModelInfo {
  version: string;
  metadata: {
    trained_at: string;
    data_source: string;
    source_notes: string[];
    zone_resolution: boolean;
    rows_raw: number;
    rows_clean: number;
    rows_train: number;
    rows_valid: number;
    train_period: [string, string];
    valid_period: [string, string];
    features: string[];
    n_clusters: number;
    best_iteration: number;
    git_sha: string;
    cleaning_report: {
      rows_in: number;
      rows_out: number;
      pct_kept: number;
      steps: {
        rule: string;
        rationale: string;
        removed: number;
        pct_removed: number;
        remaining: number;
      }[];
    };
  };
  metrics: {
    leaderboard: LeaderboardRow[];
    best_model: string;
    production_model: string;
    validation: LeaderboardRow;
    interval_coverage: {
      coverage_pct: number;
      nominal_pct: number;
      mean_width_s: number;
      median_width_s: number;
    };
    split_comparison: {
      time_split: LeaderboardRow;
      random_split: Omit<LeaderboardRow, "model" | "description" | "train_seconds">;
      note: string;
    };
    feature_importance: { feature: string; gain: number }[];
  };
  available_versions: string[];
}

export interface ResidualsResponse {
  points: {
    y_true: number;
    y_pred: number;
    residual_s: number;
    haversine_km: number;
    hour: number;
  }[];
  by_hour: { hour: number; mae_s: number; n: number }[];
  by_distance: { bucket: string; mae_s: number; n: number }[];
}

export interface ZoneTravelTime {
  destination: LatLon;
  departure: string;
  min_s: number;
  max_s: number;
  zones: { location_id: number; zone: string; borough: string; duration_s: number }[];
}

export interface HealthResponse {
  status: string;
  model_loaded: boolean;
  model_version: string | null;
  data_source: string | null;
  zone_resolution: boolean | null;
  detail: string | null;
}
