from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

EXPECTED = ["CustomerID", "Gender", "Age", "Annual Income (k$)", "Spending Score (1-100)"]


def demo_data(seed: int = 42, n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    groups = rng.choice(4, n, p=[0.25, 0.25, 0.25, 0.25])
    centers = np.array([[28, 35, 78], [50, 35, 25], [28, 85, 75], [50, 85, 25]])
    values = centers[groups] + rng.normal(0, [5, 12, 10], size=(n, 3))
    return pd.DataFrame({
        "CustomerID": np.arange(1, n + 1),
        "Gender": rng.choice(["Male", "Female"], n, p=[0.44, 0.56]),
        "Age": np.clip(values[:, 0], 18, 80).round().astype(int),
        "Annual Income (k$)": np.clip(values[:, 1], 15, 150).round(1),
        "Spending Score (1-100)": np.clip(values[:, 2], 1, 99).round().astype(int),
    })


def load_data(path: Path) -> tuple[pd.DataFrame, bool, str]:
    if path.exists():
        df = pd.read_csv(path)
        missing = [column for column in EXPECTED if column not in df.columns]
        if missing:
            raise ValueError(f"Dataset is missing required columns: {missing}")
        return df, False, str(path)
    return demo_data(), True, "deterministic-demo-fallback"


def quality_report(df: pd.DataFrame, demo: bool) -> dict:
    missing = df.isna().sum().to_dict()
    numeric = df.select_dtypes(include="number")
    ranges = {
        column: {"min": float(numeric[column].min()), "max": float(numeric[column].max())}
        for column in numeric.columns
    }
    duplicate_rows = int(df.duplicated().sum())
    duplicate_ids = int(df["CustomerID"].duplicated().sum()) if "CustomerID" in df else 0
    outliers = {}
    for column in numeric.columns:
        q1, q3 = numeric[column].quantile([0.25, 0.75])
        iqr = q3 - q1
        outliers[column] = int(((numeric[column] < q1 - 1.5 * iqr) | (numeric[column] > q3 + 1.5 * iqr)).sum())
    return {
        "rows": int(len(df)), "columns": int(len(df.columns)), "column_names": list(df.columns),
        "dtypes": {k: str(v) for k, v in df.dtypes.items()}, "missing": missing,
        "duplicate_rows": duplicate_rows, "duplicate_ids": duplicate_ids,
        "outliers_iqr": outliers, "numeric_ranges": ranges,
        "source_type": "demo fallback" if demo else "Kaggle CSV",
        "leakage_flags": ["CustomerID excluded from modeling as an identifier"],
    }


def prepare_frame(df: pd.DataFrame, feature_set: str = "behavior") -> tuple[pd.DataFrame, list[str]]:
    frame = df.copy()
    frame.columns = [str(c).strip() for c in frame.columns]
    frame = frame.drop_duplicates().reset_index(drop=True)
    for col in ["Age", "Annual Income (k$)", "Spending Score (1-100)"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["Gender"] = frame["Gender"].astype("string").str.strip().str.title()
    frame = frame.dropna(subset=["Age", "Annual Income (k$)", "Spending Score (1-100)"])
    if feature_set == "all_numeric":
        cols = ["Age", "Annual Income (k$)", "Spending Score (1-100)"]
        return frame, cols
    if feature_set == "behavior_gender":
        frame["Gender_encoded"] = frame["Gender"].map({"Female": 0, "Male": 1}).fillna(0.5)
        cols = ["Annual Income (k$)", "Spending Score (1-100)", "Gender_encoded"]
        return frame, cols
    cols = ["Annual Income (k$)", "Spending Score (1-100)"]
    return frame, cols
