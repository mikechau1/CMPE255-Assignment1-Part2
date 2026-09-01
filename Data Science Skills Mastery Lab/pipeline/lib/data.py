"""Cached loaders for the five dataset tracks.

Every loader reads only from `data/`, is deterministic, and reports the row
counts the artifacts quote, so the numbers on the website can be traced back to
a specific file with a digest in `data/raw/manifest.json`.
"""
from __future__ import annotations
import functools, gzip, json
import numpy as np
import pandas as pd

from .paths import RAW, INTERIM, PROCESSED


# --------------------------------------------------------------------------- T1
@functools.lru_cache(maxsize=1)
def telco_raw() -> pd.DataFrame:
    """Telco Customer Churn, exactly as downloaded (TotalCharges still text)."""
    return pd.read_csv(RAW / "Telco-Customer-Churn.csv")


def telco_typed() -> pd.DataFrame:
    """Telco with the one known type bug fixed -- used by phases 2+."""
    df = telco_raw().copy()
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"].replace(" ", np.nan), errors="coerce")
    df["Churn_flag"] = (df["Churn"] == "Yes").astype(int)
    return df


# --------------------------------------------------------------------------- T2
@functools.lru_cache(maxsize=1)
def retail_raw() -> pd.DataFrame:
    df = pd.read_csv(INTERIM / "online_retail.csv", parse_dates=["InvoiceDate"],
                     dtype={"InvoiceNo": "string", "StockCode": "string", "Description": "string",
                            "Country": "string"})
    return df


def retail_clean() -> pd.DataFrame:
    """Transactions only: real customers, positive quantity and price, no cancellations."""
    df = retail_raw().copy()
    df["is_cancellation"] = df["InvoiceNo"].str.startswith("C").fillna(False)
    df = df[(~df["is_cancellation"]) & df["CustomerID"].notna() &
            (df["Quantity"] > 0) & (df["UnitPrice"] > 0)].copy()
    df["CustomerID"] = df["CustomerID"].astype("int64")
    df["Revenue"] = df["Quantity"] * df["UnitPrice"]
    df["InvoiceMonth"] = df["InvoiceDate"].dt.to_period("M").dt.to_timestamp()
    return df


# --------------------------------------------------------------------------- T3
@functools.lru_cache(maxsize=1)
def titanic() -> pd.DataFrame:
    return pd.read_csv(RAW / "titanic.csv")


# --------------------------------------------------------------------------- T1b
def creditcard(sample: int | None = None, seed: int = 20255255) -> pd.DataFrame | None:
    """Credit Card Fraud. Returns None if the OpenML mirror was unavailable."""
    p = RAW / "creditcard.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    if "Class" in df.columns:
        df["Class"] = pd.to_numeric(df["Class"].astype(str).str.strip("'\""), errors="coerce").astype(int)
    if sample and len(df) > sample:
        frauds = df[df["Class"] == 1]
        legit = df[df["Class"] == 0].sample(sample - len(frauds), random_state=seed)
        df = pd.concat([frauds, legit]).sample(frac=1, random_state=seed).reset_index(drop=True)
    return df


# --------------------------------------------------------------------------- T4
def _idx_images(path) -> np.ndarray:
    with gzip.open(path, "rb") as f:
        buf = f.read()
    n, r, c = int.from_bytes(buf[4:8], "big"), int.from_bytes(buf[8:12], "big"), int.from_bytes(buf[12:16], "big")
    return np.frombuffer(buf, np.uint8, offset=16).reshape(n, r, c)


def _idx_labels(path) -> np.ndarray:
    with gzip.open(path, "rb") as f:
        buf = f.read()
    return np.frombuffer(buf, np.uint8, offset=8)


FASHION_CLASSES = ["T-shirt/top", "Trouser", "Pullover", "Dress", "Coat",
                   "Sandal", "Shirt", "Sneaker", "Bag", "Ankle boot"]


def fashion_mnist(n_train: int = 12000, n_test: int = 3000, seed: int = 20255255):
    """Subsampled Fashion-MNIST -- small enough that a CPU CNN finishes in minutes."""
    rng = np.random.default_rng(seed)
    xtr, ytr = _idx_images(RAW / "train-images-idx3-ubyte.gz"), _idx_labels(RAW / "train-labels-idx1-ubyte.gz")
    xte, yte = _idx_images(RAW / "t10k-images-idx3-ubyte.gz"), _idx_labels(RAW / "t10k-labels-idx1-ubyte.gz")
    itr = rng.choice(len(xtr), size=min(n_train, len(xtr)), replace=False)
    ite = rng.choice(len(xte), size=min(n_test, len(xte)), replace=False)
    return xtr[itr], ytr[itr], xte[ite], yte[ite]


# --------------------------------------------------------------------------- shared splits
SPLIT_SEED = 20255255
TEST_SIZE = 0.20


def churn_split():
    """The one train/test split every supervised phase reuses (stratified, seeded)."""
    from sklearn.model_selection import train_test_split
    df = telco_typed()
    y = df["Churn_flag"]
    X = df.drop(columns=["Churn", "Churn_flag"])
    return train_test_split(X, y, test_size=TEST_SIZE, random_state=SPLIT_SEED, stratify=y)


def manifest() -> dict:
    return json.loads((RAW / "manifest.json").read_text(encoding="utf-8"))


def save_processed(name: str, df: pd.DataFrame) -> None:
    df.to_parquet(PROCESSED / f"{name}.parquet", index=False)


def load_processed(name: str) -> pd.DataFrame:
    return pd.read_parquet(PROCESSED / f"{name}.parquet")
