# CRISP-DM phase 2 — Data understanding

## Two candidate sources, and the difference that matters

| | Kaggle `nyc-taxi-trip-duration` | NYC TLC public parquet |
|---|---|---|
| Coordinates | **True pickup/dropoff lat-lon** | Zone IDs only (263 polygons) |
| Target | `trip_duration` column | Derived from timestamps |
| Access | Requires an API token + accepting competition rules | Open HTTPS, no credentials |
| Period | 2016 H1, ~1.46M trips | 2009–present, ~10M trips/month |
| Extras | — | Fare, tip, tolls, payment type |

### The finding that shaped the architecture

TLC's historical files **no longer contain coordinates**. This is not an
assumption — I read the parquet footer of `yellow_tripdata_2016-01.parquet`
directly, and the schema contains `PULocationID` and `DOLocationID` with no
latitude or longitude columns anywhere. TLC re-encoded its entire back
catalogue to zone IDs when it migrated to parquet.

So the free-pin-drop map this project is built around depends on the Kaggle
files. Since those need credentials that may not be present, the pipeline
supports both behind one schema.

## The canonical schema

Both sources normalise to exactly this, and nothing downstream knows which
source it came from:

```
pickup_datetime, pickup_lat, pickup_lon,
dropoff_lat, dropoff_lon, passenger_count, trip_duration_s
```

- **Kaggle** maps straight across — lossless.
- **TLC** derives duration from the pickup/dropoff timestamps, and resolves
  each zone ID to a point *sampled inside that zone polygon* rather than its
  centroid. Centroids would collapse two million trips onto 263 dots and make
  every distance feature degenerate.

Since no public WGS84 GeoJSON of the taxi zones exists (five candidate sources
all 404), the polygons are built from TLC's own shapefile: reprojected from
EPSG:2263 (NAD83 / New York Long Island, US survey feet) to EPSG:4326 in
`src/nyctaxi/data/zones.py`. The reprojection was verified against known
landmarks — JFK, LaGuardia and Midtown Center centroids all land within ~0.01°
of their true positions.

> **Fidelity limit of the fallback, stated plainly.** A model trained on TLC
> data learns *zone-to-zone* travel time. It answers the map's question at
> roughly neighbourhood resolution, not address resolution. The UI and the
> model report both say so when this path was used. Supplying Kaggle
> credentials and retraining switches to true coordinates with no code change.

## Profile of the data actually used

The shipped model was trained on the **TLC** path (no Kaggle credentials
present), sampling 6% of January–March 2016.

| | |
|---|---|
| Rows loaded | 2,029,865 |
| Rows after cleaning | 2,014,689 (99.25% kept) |
| Training period | 2016-01-01 → 2016-03-14 |
| Validation period | 2016-03-14 → 2016-03-31 |
| Engineered features | 34 |

## Data quality findings

Working through the raw data surfaced four recurring problems, each of which
became a cleaning rule in phase 3:

1. **Meter misfires.** A tail of trips lasting a handful of seconds — the meter
   started and stopped almost immediately. Not real trips.
2. **Forgotten meters.** A thinner tail running for many hours, which are
   billing artifacts rather than journeys.
3. **Impossible speeds.** Records whose implied straight-line speed is far
   above anything achievable in New York traffic, meaning the timestamps and
   the endpoints disagree.
4. **GPS noise.** On the coordinate-bearing Kaggle path, a small number of
   points fall in the Atlantic or in other states.

Together these account for **0.75%** of rows. Small, but they sit in exactly
the tails that a squared-error objective is most sensitive to.

## What the data says about the problem

- **Duration is strongly right-skewed**, which is why the model is trained on
  `log1p(duration)` and scored with RMSLE.
- **Hour of day dominates.** The same route varies by more than a factor of two
  between 4am and 5pm — the single most useful signal after distance.
- **Distance is necessary but far from sufficient.** The distance-÷-mean-speed
  baseline scores 0.637 RMSLE against LightGBM's 0.392, so roughly the same
  again is available from time and place.
- **Direction matters.** Crosstown Manhattan traffic is materially slower than
  uptown/downtown for the same straight-line distance, which is why bearing is
  an engineered feature.

→ Next: [Data preparation](03-data-preparation.md)
