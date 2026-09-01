from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import product
import json
import time
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score


@dataclass(frozen=True)
class ExperimentConfig:
    algorithm: str = "kmeans"
    n_clusters: int = 5
    feature_set: str = "behavior"
    scaler: str = "standard"
    random_state: int = 42
    eps: float = 0.7
    min_samples: int = 5


def scaler_for(name: str):
    return {"standard": StandardScaler(), "minmax": MinMaxScaler(), "robust": RobustScaler()}[name]


def fit_config(df: pd.DataFrame, config: ExperimentConfig) -> dict:
    from .data import prepare_frame
    frame, cols = prepare_frame(df, config.feature_set)
    X = scaler_for(config.scaler).fit_transform(frame[cols])
    if config.algorithm == "gmm":
        model = GaussianMixture(n_components=config.n_clusters, random_state=config.random_state, n_init=5)
        labels = model.fit_predict(X)
        inertia = None
    elif config.algorithm == "dbscan":
        model = DBSCAN(eps=config.eps, min_samples=config.min_samples)
        labels = model.fit_predict(X)
        inertia = None
    else:
        model = KMeans(n_clusters=config.n_clusters, random_state=config.random_state, n_init=20)
        labels = model.fit_predict(X)
        inertia = float(model.inertia_)
    unique = sorted(set(labels))
    valid = len([x for x in unique if x != -1]) >= 2 and len(set(labels)) >= 2
    if -1 in unique:
        valid_mask = labels != -1
        score_X, score_labels = X[valid_mask], labels[valid_mask]
    else:
        score_X, score_labels = X, labels
    if valid and len(set(score_labels)) >= 2:
        sil = float(silhouette_score(score_X, score_labels))
        db = float(davies_bouldin_score(score_X, score_labels))
        ch = float(calinski_harabasz_score(score_X, score_labels))
    else:
        sil, db, ch = -1.0, 999.0, 0.0
    counts = pd.Series(labels).value_counts().sort_index()
    sizes = [int(v) for k, v in counts.items() if k != -1]
    balance = float(min(sizes) / max(sizes)) if sizes else 0.0
    pca = PCA(n_components=2, random_state=config.random_state)
    coords = pca.fit_transform(X)
    result = {
        "config": asdict(config), "rows": int(len(frame)), "features": cols,
        "labels": labels.tolist(), "customer_ids": frame["CustomerID"].tolist(),
        "pca": [{"x": float(x), "y": float(y), "cluster": int(label), "customer_id": int(cid)} for (x, y), label, cid in zip(coords, labels, frame["CustomerID"])],
        "metrics": {"silhouette": sil, "davies_bouldin": db, "calinski_harabasz": ch, "inertia": inertia, "balance": balance, "cluster_count": len(sizes), "noise_count": int((labels == -1).sum())},
        "cluster_sizes": {str(int(k)): int(v) for k, v in counts.items()},
        "model": model, "frame": frame, "X": X,
    }
    return result


def stability(df: pd.DataFrame, config: ExperimentConfig, repeats: int = 8) -> float:
    scores = []
    for i in range(repeats):
        cfg = ExperimentConfig(**{**asdict(config), "random_state": 100 + i})
        result = fit_config(df, cfg)
        scores.append(result["metrics"]["silhouette"])
    mean = np.mean(scores)
    return float(max(0.0, min(1.0, 1.0 - np.std(scores) / max(abs(mean), 0.1))) if scores else 0.0)


def composite(metrics: dict, stable: float) -> float:
    sil = max(0.0, min(1.0, (metrics["silhouette"] + 1) / 2))
    db = 1.0 / (1.0 + max(0.0, metrics["davies_bouldin"]))
    ch = min(1.0, np.log1p(max(0.0, metrics["calinski_harabasz"])) / 10)
    return float(0.42 * sil + 0.18 * db + 0.15 * ch + 0.18 * stable + 0.07 * metrics["balance"])


def profile(result: dict) -> list[dict]:
    frame, labels = result["frame"].copy(), result["labels"]
    frame["cluster"] = labels
    features = ["Age", "Annual Income (k$)", "Spending Score (1-100)"]
    overall = frame[features].mean()
    output = []
    for cluster, part in frame.groupby("cluster"):
        if cluster == -1:
            continue
        means = part[features].mean()
        z = ((means - overall) / frame[features].std(ddof=0).replace(0, 1)).to_dict()
        spend = means["Spending Score (1-100)"]
        income = means["Annual Income (k$)"]
        if spend >= overall["Spending Score (1-100)"] and income >= overall["Annual Income (k$)"]:
            persona = "Premium enthusiasts"
            action = "Protect with loyalty benefits, early access, and premium bundles."
        elif spend >= overall["Spending Score (1-100)"]:
            persona = "High-potential explorers"
            action = "Use personalized discovery offers and cross-sell journeys."
        elif income >= overall["Annual Income (k$)"]:
            persona = "Conservative affluents"
            action = "Test value framing, convenience, and high-consideration products."
        else:
            persona = "Value-focused regulars"
            action = "Use targeted promotions, bundles, and frequency incentives."
        output.append({"cluster": int(cluster), "persona": persona, "action": action, "size": int(len(part)), "share": float(len(part) / len(frame)), "means": {k: float(v) for k, v in means.items()}, "z_scores": {k: float(v) for k, v in z.items()}})
    return output


def jsonable(result: dict, profiles: list[dict], stable: float, score: float) -> dict:
    return {"config": result["config"], "features": result["features"], "pca": result["pca"], "metrics": {**result["metrics"], "stability": stable, "composite_score": score}, "cluster_sizes": result["cluster_sizes"], "profiles": profiles}

