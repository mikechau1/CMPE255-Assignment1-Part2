# CRISP-DM phase 3 — Data preparation

## Cleaning, as an audit trail

Every rule in `src/nyctaxi/clean.py` records how many rows it removed. The
numbers below are from the shipped model (version `20260901-021505`) and are
regenerated on every training run into `models/<version>/metadata.json`, so the
report can never drift from what actually ran.

| Rule | Rationale | Removed | % |
|---|---|---:|---:|
| `no_nulls` | Coordinates, timestamp and target must all be present | 0 | 0.00% |
| `inside_nyc_bbox` | GPS noise puts some trips in the ocean or other states | 0 | 0.00% |
| `plausible_duration` | Keep 30s–3h; shorter are meter misfires, longer are forgotten meters | 9,017 | 0.44% |
| `plausible_passengers` | A yellow cab seats at most 6 | 2 | 0.00% |
| `plausible_distance` | Straight-line trips over 100 km leave the metro area | 0 | 0.00% |
| `plausible_speed` | Implied speed must be 1–100 km/h, or the record is self-inconsistent | 6,157 | 0.31% |

**2,029,865 → 2,014,689 rows (99.25% kept).**

The two zero-row rules are not dead code: they remove real rows on the Kaggle
path, where raw GPS is present. On the TLC path the coordinates are synthesised
from zone polygons and are inside the bounding box by construction. Keeping
them means the same pipeline is correct for both sources.

## Feature engineering

34 features, all computable at booking time. Grouped by what they capture:

### Geometry
`haversine_km`, `manhattan_km`, `ns_km`, `ew_km`, `delta_lat`, `delta_lon`,
`bearing`, `bearing_sin`, `bearing_cos`, the four raw coordinates, and the trip
centre point.

Two ideas earn their place here. **Manhattan distance** splits the trip into
north–south and east–west legs, because taxis drive a street grid rather than a
straight line, so the sum of the legs is usually closer to the driven distance.
**Bearing** exists because crosstown is slower than uptown/downtown for the
same distance — a fact the model can only learn if it can see heading.

### Time
`hour`, `weekday`, `month`, `week_of_year`, `minute_of_day`, `is_weekend`,
`is_rush_hour`, `is_holiday`, and cyclic `tod_sin`/`tod_cos`,
`dow_sin`/`dow_cos`.

The cyclic encodings matter: without them 23:59 and 00:01 are at opposite ends
of the range, when they are in fact one minute apart. There is a test for
exactly this (`test_cyclic_time_encoding_wraps`).

### Space
`pickup_cluster`, `dropoff_cluster` — MiniBatchKMeans with k=100 over pickup
and dropoff coordinates, passed to LightGBM as categoricals. These let the
model learn neighbourhood-level effects that raw lat-lon cannot express as a
split.

### Learned aggregates
`speed__pickup_cluster_x_hour`, `speed__dropoff_cluster_x_hour`,
`speed__pickup_cluster_x_dropoff_cluster`, `speed__hour_x_weekday` — smoothed
mean log-speed per key.

These are the most powerful features in the model (three appear in the top
seven by gain) and also the most dangerous.

## The leakage guard

Average speed is derived from the target. Computing those aggregates over the
full training set and then training on the same rows lets **each row see its
own target**. The model looks superb in validation and collapses in
production.

The pipeline prevents this structurally:

- `fit_transform` (training rows) computes the aggregates **out-of-fold**: each
  of 5 folds is encoded using maps built only from the other four.
- `transform` (validation, test, live inference) applies maps built from all of
  training.
- KMeans is fit on training rows only.
- Both the cluster centroids and the encoding maps are serialised into the
  model artifact, so inference reproduces training exactly.

Thin cells are smoothed toward the global mean (prior weight 50), so a cluster
pair seen three times does not get a confident, noisy estimate.

A test asserts the guard actually holds: `test_out_of_fold_encoding_differs_from_full_fit`
fails if the out-of-fold values ever equal the full-data values, which is
precisely the signature of the leak.

## Target and split

The target is `log1p(trip_duration_s)`, matching the RMSLE objective and
handling the strong right skew.

The split is **time-based**: the newest 20% of trips become validation. This
mirrors deployment, where the model always predicts trips occurring after
everything it was trained on. A random split is also scored purely to quantify
how much optimism it would have added — see phase 5.

→ Next: [Modeling](04-modeling.md)
