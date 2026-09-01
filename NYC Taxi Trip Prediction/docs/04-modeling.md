# CRISP-DM phase 4 — Modeling

## An escalating ladder, not a single model

Reporting one gradient-booster score proves nothing: it gives no evidence that
the complexity bought anything. So the pipeline trains five models of
increasing capability on identical features and splits, and each rung has to
justify the next.

| # | Model | What it knows | RMSLE | MAE | R² |
|---|---|---|---:|---:|---:|
| 1 | Global median | Nothing but the target distribution | 0.7289 | 429s | −0.088 |
| 2 | Distance ÷ mean speed | Pure physics | 0.6371 | 349s | 0.200 |
| 3 | Ridge regression | Linear effects of every numeric feature | 0.4994 | 306s | −0.010 |
| 4 | Random forest | Non-linearity and interactions | 0.4130 | 210s | 0.745 |
| 5 | **LightGBM** | The above, plus categoricals and learned aggregates | **0.3920** | **197s** | **0.776** |

![Leaderboard](figures/leaderboard.png)

Reading the ladder:

- **Median → distance** (0.729 → 0.637): geometry is worth a lot, as expected.
- **Distance → ridge** (0.637 → 0.499): time-of-day and direction carry real
  signal even under a purely linear model.
- **Ridge → forest** (0.499 → 0.413): the biggest single jump. The relationship
  is strongly non-linear — rush hour is not a linear function of the clock.
- **Forest → LightGBM** (0.413 → 0.392): a smaller but real gain, from
  categorical cluster handling and the out-of-fold speed aggregates.

The final model roughly **halves** the RMSLE of the physics baseline and cuts
typical error from over 7 minutes to about 3¼.

### An aside worth noticing: ridge has a negative R²

Ridge scores a respectable 0.4994 RMSLE yet an R² of −0.010 — nominally worse
than predicting the mean. That is not a bug, it is the two metrics measuring
different things.

Ridge is fit on `log1p(duration)` and its predictions are exponentiated back.
That makes it competitive on *proportional* error, which is what RMSLE scores.
But R² is computed on raw seconds, where the long right tail dominates the
variance, and a linear model cannot bend to fit that tail — so it explains
essentially none of the raw-seconds variance while still getting the typical
trip roughly right in ratio terms.

This is a concrete demonstration of why the metric choice in phase 1 matters.
Had R² been the headline, ridge would look worthless and the physics baseline
(R² 0.200) would appear to beat it — the opposite of what RMSLE and MAE both
say.

## The production model

LightGBM, trained on `log1p(duration)` with early stopping on the time-based
validation split.

```yaml
objective: regression      num_leaves: 128
metric: rmse               min_data_in_leaf: 50
learning_rate: 0.05        feature_fraction: 0.85
lambda_l2: 1.0             bagging_fraction: 0.85 (freq 1)
num_boost_round: 3000      early_stopping_rounds: 100
```

Early stopping selected **1,881 rounds**. Categorical features
(`pickup_cluster`, `dropoff_cluster`, `hour`, `weekday`, `month`) are declared
to LightGBM rather than one-hot encoded, so it can split on arbitrary subsets
of 100 clusters instead of learning 100 separate binary splits.

## What it leans on

Top features by split gain:

1. `haversine_km` — straight-line distance
2. `manhattan_km` — grid distance
3. `speed__hour_x_weekday` — typical speed at this time of week
4. `speed__pickup_cluster_x_dropoff_cluster` — typical speed on this route
5. `pickup_cluster`
6. `dropoff_cluster`
7. `speed__dropoff_cluster_x_hour`
8. `ew_km` — east-west leg

![Feature importance](figures/feature_importance.png)

Distance leads, which is the sanity check you want. But three of the top seven
are the learned speed aggregates, and two more are the spatial clusters —
confirming that *where and when* carries about as much information as *how
far*. The east-west leg outranking the north-south leg is the crosstown effect
showing up on its own.

## The uncertainty band

Three additional LightGBM models are trained with the quantile objective at
α = 0.1, 0.5 and 0.9, giving a P10–P90 interval rather than a bare point
estimate.

Two details make the band usable rather than decorative:

**Crossing is prevented.** The three quantile models are trained
independently, so nothing in the objective forces P10 ≤ P50 ≤ P90. Predictions
are sorted before being returned, in both training and serving.

**Coverage is measured, not assumed.** A nominal-80% band that actually
contains the truth 50% of the time is worse than no band at all. Measured
coverage is **77.42%** — 2.6 points below nominal, comfortably inside the
5-point tolerance, so it can be read at face value. See phase 5.

## Model artifacts

Each run writes a self-describing, versioned directory:

```
models/<timestamp>/
├── model_main.txt                    # production booster
├── model_q10.txt / q50 / q90         # quantile boosters
├── feature_pipeline.joblib           # KMeans + encoding maps
├── metadata.json                     # source, rows, split dates, params, git SHA
├── metrics.json                      # leaderboard, coverage, importance
└── validation_predictions.parquet    # feeds evaluation without a retrain
```

`models/latest.json` points at the current version; the API resolves it at
startup. Because the browser dashboard and the written report both read
`metrics.json`, they cannot disagree.

→ Next: [Evaluation](05-evaluation.md) *(generated by `python -m nyctaxi.evaluate`)*
