"""CRISP-DM phase 4 -- modeling.

Runs an escalating ladder of models so the gain from each step is visible and
attributable, rather than jumping straight to a gradient booster and asserting
it is good:

  1. global median      -- what you get knowing nothing
  2. distance/speed     -- what you get from physics alone
  3. ridge regression   -- what a linear model extracts
  4. random forest      -- what non-linearity buys
  5. LightGBM           -- the production model
  6. LightGBM quantiles -- the P10/P50/P90 band

Usage:
    python -m nyctaxi.train --sample-frac 0.05     # fast wiring check
    python -m nyctaxi.train                        # full run
"""

from __future__ import annotations

import argparse
import json
import time

import lightgbm as lgb
import numpy as np
import pandas as pd

from . import registry
from .clean import clean
from .config import get_config
from .data.loader import load
from .features import CATEGORICAL_FEATURES, FeaturePipeline
from .logging_utils import get_logger
from .metrics import interval_coverage, score_all

log = get_logger(__name__)


def time_split(df: pd.DataFrame, valid_frac: float) -> tuple[np.ndarray, np.ndarray]:
    """Chronological split: the newest `valid_frac` of trips become validation.

    This is the primary split because it mirrors deployment -- the model always
    predicts trips that happen after everything it was trained on. A random
    split leaks future traffic conditions backwards and flatters the score.
    """
    order = np.argsort(df["pickup_datetime"].to_numpy())
    cut = int(len(df) * (1.0 - valid_frac))
    return order[:cut], order[cut:]


def random_split(df: pd.DataFrame, valid_frac: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(df))
    cut = int(len(df) * (1.0 - valid_frac))
    return idx[:cut], idx[cut:]


# --------------------------------------------------------------------------
# baselines -- each one answers "is the next model actually earning its keep?"
# --------------------------------------------------------------------------
def baseline_median(y_tr: np.ndarray, n_valid: int) -> np.ndarray:
    return np.full(n_valid, float(np.median(y_tr)))


def baseline_distance_speed(
    y_tr: np.ndarray, f_tr: pd.DataFrame, f_va: pd.DataFrame
) -> np.ndarray:
    """Distance divided by the average speed observed in training."""
    hours = np.clip(y_tr, 1, None) / 3600.0
    mean_speed = float(np.mean(f_tr["haversine_km"].to_numpy() / hours))
    mean_speed = max(mean_speed, 1e-3)
    return np.clip(f_va["haversine_km"].to_numpy() / mean_speed * 3600.0, 1.0, None)


def fit_ridge(f_tr, y_log_tr, f_va, numeric_cols):
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    model.fit(f_tr[numeric_cols].to_numpy(), y_log_tr)
    return np.expm1(model.predict(f_va[numeric_cols].to_numpy()))


def fit_random_forest(f_tr, y_log_tr, f_va, numeric_cols, seed):
    from sklearn.ensemble import RandomForestRegressor

    # Depth-capped and subsampled: this is a reference point on the ladder,
    # not a contender, and an uncapped forest on a million rows is minutes of
    # compute for a result we already expect LightGBM to beat.
    n = min(len(f_tr), 150_000)
    rs = np.random.default_rng(seed).choice(len(f_tr), n, replace=False)
    model = RandomForestRegressor(
        n_estimators=60, max_depth=18, min_samples_leaf=10, n_jobs=-1, random_state=seed
    )
    model.fit(f_tr[numeric_cols].to_numpy()[rs], y_log_tr[rs])
    return np.expm1(model.predict(f_va[numeric_cols].to_numpy()))


def fit_lightgbm(f_tr, y_log_tr, f_va, y_log_va, params, cat_features, objective=None, alpha=None):
    """Train one booster. Used for both the main model and each quantile."""
    p = dict(params)
    rounds = p.pop("num_boost_round", 2000)
    stop = p.pop("early_stopping_rounds", 100)
    if objective:
        p["objective"] = objective
        p["alpha"] = alpha
        p["metric"] = "quantile"

    dtrain = lgb.Dataset(f_tr, label=y_log_tr, categorical_feature=cat_features, free_raw_data=False)
    dvalid = lgb.Dataset(f_va, label=y_log_va, reference=dtrain, free_raw_data=False)
    return lgb.train(
        p,
        dtrain,
        num_boost_round=rounds,
        valid_sets=[dvalid],
        valid_names=["valid"],
        callbacks=[lgb.early_stopping(stop, verbose=False), lgb.log_evaluation(200)],
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Train the NYC taxi duration model.")
    ap.add_argument("--sample-frac", type=float, default=None, help="Subsample for a fast run.")
    ap.add_argument("--nrows", type=int, default=None, help="Cap rows read from source.")
    ap.add_argument("--source", default=None, choices=["auto", "kaggle", "tlc"])
    ap.add_argument("--skip-slow-baselines", action="store_true", help="Skip ridge + forest.")
    args = ap.parse_args()

    cfg = get_config()
    t0 = time.time()

    # -- phase 2: data ----------------------------------------------------
    result = load(source=args.source, nrows=args.nrows, sample_frac=args.sample_frac)
    df = result.df
    log.info("loaded %d rows from source=%s", len(df), result.source)

    # -- phase 3: preparation --------------------------------------------
    df, clean_report = clean(df)
    if len(df) < 1000:
        raise RuntimeError(f"Only {len(df)} rows survived cleaning; too few to train.")

    y = df[cfg.model.target].to_numpy(dtype=float)
    tr_idx, va_idx = time_split(df, cfg.split.valid_frac)
    df_tr, df_va = df.iloc[tr_idx], df.iloc[va_idx]
    y_tr, y_va = y[tr_idx], y[va_idx]
    log.info(
        "time split: train %d (%s..%s) | valid %d (%s..%s)",
        len(df_tr), df_tr["pickup_datetime"].min(), df_tr["pickup_datetime"].max(),
        len(df_va), df_va["pickup_datetime"].min(), df_va["pickup_datetime"].max(),
    )

    # Fit features on training rows only; validation is transformed, never fitted.
    pipeline = FeaturePipeline(
        n_clusters=cfg.features.n_clusters,
        n_folds=cfg.features.target_encode_folds,
        smoothing=cfg.features.target_encode_smoothing,
        seed=cfg.random_seed,
    )
    f_tr = pipeline.fit_transform(df_tr, y_tr)
    f_va = pipeline.transform(df_va)
    log.info("features: %d columns", f_tr.shape[1])

    y_log_tr, y_log_va = np.log1p(y_tr), np.log1p(y_va)
    numeric_cols = [c for c in f_tr.columns if c not in ("pickup_cluster", "dropoff_cluster")]

    # -- phase 4: the ladder ----------------------------------------------
    leaderboard: list[dict] = []

    def record(name: str, description: str, preds: np.ndarray, elapsed: float) -> None:
        scores = score_all(y_va, np.clip(preds, 1.0, None))
        leaderboard.append(
            {"model": name, "description": description, "train_seconds": round(elapsed, 1), **scores}
        )
        log.info("%-22s RMSLE=%.5f  MAE=%.0fs", name, scores["rmsle"], scores["mae_s"])

    t = time.time()
    record("median_baseline", "Predict the global median duration.",
           baseline_median(y_tr, len(y_va)), time.time() - t)

    t = time.time()
    record("distance_speed_baseline", "Straight-line distance / mean training speed.",
           baseline_distance_speed(y_tr, f_tr, f_va), time.time() - t)

    if not args.skip_slow_baselines:
        t = time.time()
        record("ridge", "L2 linear regression on standardised numeric features.",
               fit_ridge(f_tr, y_log_tr, f_va, numeric_cols), time.time() - t)

        t = time.time()
        record("random_forest", "Depth-capped forest on a 150k-row subsample.",
               fit_random_forest(f_tr, y_log_tr, f_va, numeric_cols, cfg.random_seed),
               time.time() - t)

    cat_features = [c for c in CATEGORICAL_FEATURES if c in f_tr.columns]
    t = time.time()
    booster = fit_lightgbm(f_tr, y_log_tr, f_va, y_log_va, cfg.model.lightgbm, cat_features)
    pred_main = np.expm1(booster.predict(f_va, num_iteration=booster.best_iteration))
    record("lightgbm", "Gradient-boosted trees on the full feature set.", pred_main, time.time() - t)

    # -- quantiles: the P10-P90 band --------------------------------------
    boosters = {"main": booster}
    quantile_preds: dict[str, np.ndarray] = {}
    for q in cfg.model.quantiles:
        tag = f"q{int(q * 100)}"
        t = time.time()
        qb = fit_lightgbm(
            f_tr, y_log_tr, f_va, y_log_va, cfg.model.lightgbm, cat_features,
            objective="quantile", alpha=q,
        )
        boosters[tag] = qb
        quantile_preds[tag] = np.clip(
            np.expm1(qb.predict(f_va, num_iteration=qb.best_iteration)), 1.0, None
        )
        log.info("trained quantile %s in %.1fs", tag, time.time() - t)

    # Quantile models are trained independently, so nothing forces P10 <= P90.
    # Sorting the three together guarantees a coherent interval.
    stacked = np.sort(np.vstack([quantile_preds[k] for k in ("q10", "q50", "q90")]), axis=0)
    quantile_preds["q10"], quantile_preds["q50"], quantile_preds["q90"] = stacked
    coverage = interval_coverage(y_va, quantile_preds["q10"], quantile_preds["q90"])
    log.info(
        "P10-P90 coverage %.2f%% (nominal 80%%), median width %.0fs",
        coverage["coverage_pct"], coverage["median_width_s"],
    )

    # -- optimism check: what a random split would have claimed ------------
    rtr, rva = random_split(df, cfg.split.valid_frac, cfg.random_seed)
    rp = FeaturePipeline(
        n_clusters=cfg.features.n_clusters, n_folds=cfg.features.target_encode_folds,
        smoothing=cfg.features.target_encode_smoothing, seed=cfg.random_seed,
    )
    rf_tr = rp.fit_transform(df.iloc[rtr], y[rtr])
    rf_va = rp.transform(df.iloc[rva])
    rb = fit_lightgbm(
        rf_tr, np.log1p(y[rtr]), rf_va, np.log1p(y[rva]), cfg.model.lightgbm, cat_features
    )
    random_scores = score_all(
        y[rva], np.clip(np.expm1(rb.predict(rf_va, num_iteration=rb.best_iteration)), 1.0, None)
    )
    log.info(
        "split comparison -- time %.5f vs random %.5f RMSLE",
        leaderboard[-1]["rmsle"], random_scores["rmsle"],
    )

    # -- persist -----------------------------------------------------------
    importance = sorted(
        (
            {"feature": f, "gain": float(g)}
            for f, g in zip(booster.feature_name(), booster.feature_importance("gain"), strict=False)
        ),
        key=lambda d: d["gain"],
        reverse=True,
    )
    best = min(leaderboard, key=lambda d: d["rmsle"])
    metrics = {
        "leaderboard": leaderboard,
        "best_model": best["model"],
        "production_model": "lightgbm",
        "validation": next(r for r in leaderboard if r["model"] == "lightgbm"),
        "interval_coverage": coverage,
        "split_comparison": {
            "time_split": next(r for r in leaderboard if r["model"] == "lightgbm"),
            "random_split": random_scores,
            "note": (
                "A random split scores better because it lets the model see traffic "
                "from the same days it predicts. The time split is the honest number."
            ),
        },
        "feature_importance": importance,
    }
    metadata = {
        "trained_at": pd.Timestamp.utcnow().isoformat(),
        "data_source": result.source,
        "source_notes": result.notes,
        "zone_resolution": result.is_zone_resolution,
        "rows_raw": clean_report.rows_in,
        "rows_clean": clean_report.rows_out,
        "rows_train": len(df_tr),
        "rows_valid": len(df_va),
        "train_period": [str(df_tr["pickup_datetime"].min()), str(df_tr["pickup_datetime"].max())],
        "valid_period": [str(df_va["pickup_datetime"].min()), str(df_va["pickup_datetime"].max())],
        "features": list(f_tr.columns),
        "categorical_features": cat_features,
        "n_clusters": cfg.features.n_clusters,
        "lightgbm_params": cfg.model.lightgbm,
        "best_iteration": int(booster.best_iteration or 0),
        "cleaning_report": clean_report.to_dict(),
        "sample_frac": args.sample_frac,
    }

    version = registry.new_version()
    registry.save(version, pipeline=pipeline, boosters=boosters, metadata=metadata, metrics=metrics)

    # Validation predictions feed the evaluation plots without a retrain.
    vdir = get_config().paths.resolve("models") / version
    pd.DataFrame(
        {
            "y_true": y_va,
            "y_pred": pred_main,
            "q10": quantile_preds["q10"],
            "q50": quantile_preds["q50"],
            "q90": quantile_preds["q90"],
            "hour": f_va["hour"].to_numpy(),
            "weekday": f_va["weekday"].to_numpy(),
            "haversine_km": f_va["haversine_km"].to_numpy(),
            "pickup_lat": f_va["pickup_lat"].to_numpy(),
            "pickup_lon": f_va["pickup_lon"].to_numpy(),
        }
    ).to_parquet(vdir / "validation_predictions.parquet", index=False)

    (get_config().paths.resolve("data_processed") / "cleaning_report.md").write_text(
        clean_report.to_markdown(), encoding="utf-8"
    )

    log.info("=" * 72)
    log.info("done in %.1fs | version %s | source %s", time.time() - t0, version, result.source)
    log.info("leaderboard (validation RMSLE, lower is better):")
    for row in sorted(leaderboard, key=lambda d: d["rmsle"]):
        log.info("   %-24s %.5f   MAE %6.0fs", row["model"], row["rmsle"], row["mae_s"])
    log.info("=" * 72)
    print(json.dumps({"version": version, "best": best["model"], "rmsle": best["rmsle"]}))


if __name__ == "__main__":
    main()
