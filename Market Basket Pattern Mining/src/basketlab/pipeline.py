from __future__ import annotations

import json
from pathlib import Path

from .autoresearch import hill_climb
from .data import fixture_price_catalog, fixture_transactions, load_market_data, profile
from .models import MiningConfig


def discover_retail_path() -> Path | None:
    root = Path(__file__).resolve().parents[2]
    candidates = [root / "data" / "raw" / name for name in ("online_retail.csv", "Online Retail.csv", "Online_Retail.csv")]
    return next((path for path in candidates if path.exists()), None)


def run(input_path: str | None = None, budget: int = 18) -> dict:
    source_path = Path(input_path) if input_path else discover_retail_path()
    if source_path:
        transactions, prices, retail = load_market_data(source_path)
        if len(transactions) > 12000:
            transactions = transactions[:12000]
        dataset_name = "Kaggle/UCI Online Retail"
        source = "https://www.kaggle.com/datasets/luisrenterialezano/retail-sales-dataset"
        pricing_source = "observed"
    else:
        transactions, prices = fixture_transactions(), fixture_price_catalog()
        retail = {"currency": "USD", "pricing_method": "demo_fixture"}
        dataset_name, source, pricing_source = "BasketLab demo fixture", "bundled", "demo"
    cut = max(1, int(len(transactions) * 0.8))
    train, holdout = transactions[:cut], transactions[cut:]
    result = hill_climb(train, holdout, MiningConfig(), budget)
    result["profile"] = profile(transactions).__dict__
    result["price_catalog"] = prices
    result["pricing"] = {**retail, "source": pricing_source, "catalog_items": len(prices)}
    result["metadata"] = {"dataset": dataset_name, "source": source, "split": "80/20 deterministic", "crisp_dm": True}
    return result


def write_result(result: dict, output: str | Path) -> None:
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(result, indent=2), encoding="utf-8")
