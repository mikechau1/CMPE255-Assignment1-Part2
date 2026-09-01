import pandas as pd

from basketlab.data import fixture_transactions, load_market_data, profile
from basketlab.mining import build_rules, frequent_itemsets
from basketlab.models import MiningConfig


def test_fixture_profile_is_sparse_and_nonempty():
    result = profile(fixture_transactions())
    assert result.transactions == 120
    assert result.unique_items >= 8
    assert 0 < result.sparsity < 1


def test_frequent_itemsets_respect_support():
    transactions = fixture_transactions()
    result = frequent_itemsets(transactions, MiningConfig(min_support=0.1, max_itemset_size=2))
    assert ("whole milk",) in result
    assert all(value >= 0.1 for value in result.values())


def test_rules_have_valid_metrics():
    rules = build_rules(fixture_transactions(), MiningConfig(min_support=0.05, min_confidence=0.2, min_lift=1.0))
    assert rules
    assert all(r.lift >= 1.0 and r.confidence >= 0.2 for r in rules)


def test_online_retail_loader_uses_observed_median_price(tmp_path):
    path = tmp_path / "online_retail.csv"
    pd.DataFrame([
        {"InvoiceNo": "1", "Description": "Blue Mug", "Quantity": 2, "UnitPrice": 3.0},
        {"InvoiceNo": "2", "Description": "Blue Mug", "Quantity": 1, "UnitPrice": 5.0},
        {"InvoiceNo": "C3", "Description": "Blue Mug", "Quantity": 1, "UnitPrice": 99.0},
        {"InvoiceNo": "2", "Description": "Plate", "Quantity": 1, "UnitPrice": 2.0},
    ]).to_csv(path, index=False)
    transactions, prices, details = load_market_data(path)
    assert len(transactions) == 2
    assert prices["blue mug"] == 4.0
    assert details["currency"] == "GBP"
