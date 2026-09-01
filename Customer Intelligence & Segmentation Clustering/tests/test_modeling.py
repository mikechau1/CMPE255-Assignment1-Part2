import pandas as pd
from src.data import demo_data, quality_report, prepare_frame
from src.modeling import ExperimentConfig, fit_config, composite


def test_demo_data_is_schema_valid():
    df = demo_data()
    assert len(df) == 200
    assert list(df.columns) == ["CustomerID", "Gender", "Age", "Annual Income (k$)", "Spending Score (1-100)"]


def test_identifier_is_not_a_model_feature():
    frame, cols = prepare_frame(demo_data(), "behavior")
    assert "CustomerID" not in cols
    assert len(frame) == 200


def test_kmeans_produces_metrics_and_pca():
    result = fit_config(demo_data(), ExperimentConfig(n_clusters=4))
    assert len(result["labels"]) == 200
    assert len(result["pca"]) == 200
    assert -1 <= result["metrics"]["silhouette"] <= 1


def test_quality_report_flags_demo_source():
    report = quality_report(demo_data(), True)
    assert report["source_type"] == "demo fallback"
    assert report["duplicate_rows"] == 0

