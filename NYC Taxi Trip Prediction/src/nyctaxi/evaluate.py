"""CRISP-DM phase 5 -- evaluation.

Reads a saved model version and produces the static artifacts the written
report needs: figures under docs/figures and a rendered markdown summary. The
browser dashboard reads the same metrics.json, so the two can never disagree.

Usage:
    python -m nyctaxi.evaluate                # latest version
    python -m nyctaxi.evaluate --version ...  # a specific one
"""

from __future__ import annotations

import argparse
import json

import matplotlib

matplotlib.use("Agg")  # headless: this runs in CI and over SSH
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import registry
from .config import get_config
from .logging_utils import get_logger
from .metrics import interval_coverage, score_all

log = get_logger(__name__)

INK = "#14171c"
ACCENT = "#e5a000"
GOOD = "#128a5b"
WARN = "#c2410c"


def _style(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=11, weight="600", color=INK, loc="left", pad=10)
    ax.set_xlabel(xlabel, fontsize=9, color="#5c636e")
    ax.set_ylabel(ylabel, fontsize=9, color="#5c636e")
    ax.tick_params(labelsize=8, colors="#5c636e")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#d8dbe0")
    ax.grid(alpha=0.18, linewidth=0.7)
    ax.set_axisbelow(True)


def figure_predicted_vs_actual(df: pd.DataFrame, out) -> None:
    fig, ax = plt.subplots(figsize=(5.4, 5.0), dpi=150)
    lim = float(np.percentile(df["y_true"], 99.5)) / 60.0
    ax.scatter(df["y_true"] / 60, df["y_pred"] / 60, s=4, alpha=0.14, color=ACCENT, linewidths=0)
    ax.plot([0, lim], [0, lim], color=INK, lw=1, ls="--", label="perfect prediction")
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.legend(fontsize=8, frameon=False)
    _style(ax, "Predicted vs actual duration", "Actual (minutes)", "Predicted (minutes)")
    fig.tight_layout()
    fig.savefig(out / "predicted_vs_actual.png", bbox_inches="tight")
    plt.close(fig)


def figure_residuals(df: pd.DataFrame, out) -> None:
    resid = (df["y_pred"] - df["y_true"]) / 60.0
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), dpi=150)

    axes[0].scatter(df["y_pred"] / 60, resid, s=4, alpha=0.14, color=ACCENT, linewidths=0)
    axes[0].axhline(0, color=INK, lw=1, ls="--")
    axes[0].set_ylim(np.percentile(resid, 0.5), np.percentile(resid, 99.5))
    _style(axes[0], "Residuals vs predicted", "Predicted (minutes)", "Error (minutes)")

    clipped = resid[(resid > np.percentile(resid, 0.5)) & (resid < np.percentile(resid, 99.5))]
    axes[1].hist(clipped, bins=70, color=ACCENT, alpha=0.85, edgecolor="none")
    axes[1].axvline(0, color=INK, lw=1, ls="--")
    _style(axes[1], "Residual distribution", "Error (minutes)", "Trips")

    fig.tight_layout()
    fig.savefig(out / "residuals.png", bbox_inches="tight")
    plt.close(fig)


def figure_error_slices(df: pd.DataFrame, out) -> None:
    df = df.assign(abs_err=(df["y_pred"] - df["y_true"]).abs() / 60.0)
    by_hour = df.groupby("hour")["abs_err"].mean()
    buckets = pd.cut(
        df["haversine_km"],
        [0, 1, 2, 5, 10, 20, 1000],
        labels=["<1", "1-2", "2-5", "5-10", "10-20", ">20"],
    )
    by_dist = df.groupby(buckets, observed=True)["abs_err"].mean()

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.6), dpi=150)
    axes[0].bar(by_hour.index, by_hour.to_numpy(), color=ACCENT, width=0.75)
    _style(axes[0], "Mean absolute error by hour", "Departure hour", "MAE (minutes)")
    axes[1].bar(range(len(by_dist)), by_dist.to_numpy(), color=GOOD, width=0.65)
    axes[1].set_xticks(range(len(by_dist)))
    axes[1].set_xticklabels(by_dist.index.astype(str))
    _style(axes[1], "Mean absolute error by trip length", "Straight-line distance (km)", "MAE (minutes)")
    fig.tight_layout()
    fig.savefig(out / "error_slices.png", bbox_inches="tight")
    plt.close(fig)


def figure_leaderboard(metrics: dict, out) -> None:
    rows = sorted(metrics["leaderboard"], key=lambda r: r["rmsle"], reverse=True)
    names = [r["model"].replace("_", " ") for r in rows]
    values = [r["rmsle"] for r in rows]
    colors = [ACCENT if r["model"] == metrics["production_model"] else "#c9ccd2" for r in rows]

    fig, ax = plt.subplots(figsize=(7.2, 0.55 * len(rows) + 1.4), dpi=150)
    bars = ax.barh(names, values, color=colors, height=0.62)
    for bar, v in zip(bars, values, strict=True):
        ax.text(v + max(values) * 0.012, bar.get_y() + bar.get_height() / 2, f"{v:.4f}",
                va="center", fontsize=8, color="#5c636e")
    ax.set_xlim(0, max(values) * 1.15)
    _style(ax, "Validation RMSLE by model (lower is better)", "RMSLE", "")
    fig.tight_layout()
    fig.savefig(out / "leaderboard.png", bbox_inches="tight")
    plt.close(fig)


def figure_interval_calibration(df: pd.DataFrame, out) -> None:
    """Coverage overall and by trip length -- where the band is trustworthy."""
    inside = (df["y_true"] >= df["q10"]) & (df["y_true"] <= df["q90"])
    buckets = pd.cut(
        df["haversine_km"],
        [0, 1, 2, 5, 10, 20, 1000],
        labels=["<1", "1-2", "2-5", "5-10", "10-20", ">20"],
    )
    by_dist = inside.groupby(buckets, observed=True).mean() * 100

    fig, ax = plt.subplots(figsize=(6.4, 3.6), dpi=150)
    colors = [GOOD if abs(v - 80) <= 5 else WARN for v in by_dist]
    ax.bar(range(len(by_dist)), by_dist.to_numpy(), color=colors, width=0.62)
    ax.axhline(80, color=INK, lw=1.2, ls="--", label="80% nominal")
    ax.set_xticks(range(len(by_dist)))
    ax.set_xticklabels(by_dist.index.astype(str))
    ax.set_ylim(0, 105)
    ax.legend(fontsize=8, frameon=False)
    _style(ax, "P10-P90 interval coverage by trip length", "Straight-line distance (km)", "Coverage (%)")
    fig.tight_layout()
    fig.savefig(out / "interval_coverage.png", bbox_inches="tight")
    plt.close(fig)


def figure_importance(metrics: dict, out) -> None:
    top = metrics["feature_importance"][:15][::-1]
    fig, ax = plt.subplots(figsize=(7.2, 0.36 * len(top) + 1.2), dpi=150)
    ax.barh([f["feature"] for f in top], [f["gain"] for f in top], color=ACCENT, height=0.68)
    _style(ax, "Feature importance (LightGBM split gain)", "Gain", "")
    fig.tight_layout()
    fig.savefig(out / "feature_importance.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate a trained model version.")
    ap.add_argument("--version", default=None)
    args = ap.parse_args()

    cfg = get_config()
    bundle = registry.load(args.version)
    version = bundle["version"]
    metrics = bundle["metrics"]
    metadata = bundle["metadata"]

    pred_path = cfg.paths.resolve("models") / version / "validation_predictions.parquet"
    if not pred_path.exists():
        raise FileNotFoundError(
            f"{pred_path} is missing. Retrain so evaluation has predictions to score."
        )
    df = pd.read_parquet(pred_path)
    figures = cfg.paths.resolve("figures")

    log.info("rendering figures for version %s (%d validation rows)", version, len(df))
    figure_predicted_vs_actual(df, figures)
    figure_residuals(df, figures)
    figure_error_slices(df, figures)
    figure_leaderboard(metrics, figures)
    figure_interval_calibration(df, figures)
    figure_importance(metrics, figures)

    overall = score_all(df["y_true"].to_numpy(), df["y_pred"].to_numpy())
    coverage = interval_coverage(
        df["y_true"].to_numpy(), df["q10"].to_numpy(), df["q90"].to_numpy()
    )
    gap = abs(coverage["coverage_pct"] - 80.0)
    verdict = (
        "within 5 points of nominal, so the band can be read at face value"
        if gap <= 5
        else (
            "narrower than nominal, so treat it as optimistic"
            if coverage["coverage_pct"] < 80
            else "wider than nominal -- conservative rather than misleading"
        )
    )

    ladder = "\n".join(
        f"| {r['model'].replace('_', ' ')} | {r['description']} | {r['rmsle']:.4f} | "
        f"{r['mae_s'] / 60:.1f} min | {r['r2']:.3f} |"
        for r in sorted(metrics["leaderboard"], key=lambda r: r["rmsle"])
    )

    report = f"""# CRISP-DM phase 5 -- Evaluation

**Model version `{version}`** · trained {metadata["trained_at"][:19]} · commit `{metadata["git_sha"]}`
· data source **{metadata["data_source"]}** · {metadata["rows_clean"]:,} clean rows
({metadata["rows_train"]:,} train / {metadata["rows_valid"]:,} validation).

## Headline results

| Metric | Value | Reading |
|---|---:|---|
| RMSLE | **{overall["rmsle"]:.4f}** | Competition metric. Scores proportional error, so a 5-minute miss counts far more on a 6-minute hop than on a 90-minute airport run. |
| MAE | **{overall["mae_s"] / 60:.1f} min** | Typical miss in wall-clock terms. |
| RMSE | {overall["rmse_s"] / 60:.1f} min | Punishes the large misses. |
| MAPE | {overall["mape_pct"]:.1f}% | Relative error. |
| R² | {overall["r2"]:.3f} | Variance explained on raw seconds. |

## Model ladder

Each rung exists so the next one has to earn its place.

| Model | What it does | RMSLE | MAE | R² |
|---|---|---:|---:|---:|
{ladder}

![Leaderboard](figures/leaderboard.png)

## Does the model predict well?

![Predicted vs actual](figures/predicted_vs_actual.png)

![Residuals](figures/residuals.png)

Residuals should sit around zero with no trend against the prediction. A fan
opening to the right would mean the model is systematically worse on long
trips beyond what RMSLE already accounts for.

## Where does it fail?

![Error slices](figures/error_slices.png)

Error is reported by departure hour and by trip length, because an average
hides exactly the cases a rider cares about -- rush hour and airport runs.

## Is the confidence band honest?

Coverage is **{coverage["coverage_pct"]:.2f}%** against a nominal 80%, with a median band
width of {coverage["median_width_s"] / 60:.1f} minutes. That is {verdict}.

![Interval coverage](figures/interval_coverage.png)

This is the test that keeps the P10-P90 interval from being decorative. A band
that covers far less than 80% is overconfident; one that covers far more is
uselessly wide.

## What the model leans on

![Feature importance](figures/feature_importance.png)

## Time split vs random split

| Split | RMSLE |
|---|---:|
| Time-based (reported) | {metrics["split_comparison"]["time_split"]["rmsle"]:.4f} |
| Random | {metrics["split_comparison"]["random_split"]["rmsle"]:.4f} |

{metrics["split_comparison"]["note"]}

---
*Generated by `python -m nyctaxi.evaluate`. Figures and numbers come from the
same model artifact the API serves.*
"""

    out_path = get_config().paths.resolve("figures").parent / "05-evaluation.md"
    out_path.write_text(report, encoding="utf-8")
    log.info("wrote %s", out_path)
    print(json.dumps({"version": version, "rmsle": overall["rmsle"], **coverage}, indent=2))


if __name__ == "__main__":
    main()
