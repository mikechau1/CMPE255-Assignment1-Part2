from __future__ import annotations

from pathlib import Path
import hashlib
import re
from typing import Any

import pandas as pd

from .models import DatasetProfile


def normalize_item(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def load_transactions(path: str | Path) -> list[set[str]]:
    transactions, _, _ = load_market_data(path)
    return transactions


def load_market_data(path: str | Path) -> tuple[list[set[str]], dict[str, float], dict[str, Any]]:
    frame = pd.read_csv(path)
    columns = {str(column).strip().lower(): column for column in frame.columns}
    retail_columns = {"invoiceno", "description", "quantity", "unitprice"}
    if retail_columns.issubset(columns):
        invoice = columns["invoiceno"]
        description = columns["description"]
        quantity = columns["quantity"]
        unit_price = columns["unitprice"]
        cleaned = frame[[invoice, description, quantity, unit_price]].copy()
        cleaned[quantity] = pd.to_numeric(cleaned[quantity], errors="coerce")
        cleaned[unit_price] = pd.to_numeric(cleaned[unit_price], errors="coerce")
        cleaned = cleaned.dropna(subset=[invoice, description, quantity, unit_price])
        cleaned = cleaned[(cleaned[quantity] > 0) & (cleaned[unit_price] > 0)]
        cleaned = cleaned[~cleaned[invoice].astype(str).str.upper().str.startswith("C")]
        cleaned[description] = cleaned[description].map(normalize_item)
        cleaned = cleaned[cleaned[description] != ""]
        baskets = cleaned.groupby(invoice)[description].agg(lambda values: set(values)).tolist()
        prices = cleaned.groupby(description)[unit_price].median().round(2).to_dict()
        return baskets, {str(item): float(price) for item, price in prices.items()}, {
            "raw_rows": int(len(frame)), "clean_rows": int(len(cleaned)),
            "currency": "GBP", "pricing_method": "median_observed_unit_price",
            "gross_line_value": float((cleaned[quantity] * cleaned[unit_price]).sum()),
        }
    if "itemDescription" in frame.columns:
        grouped = frame.groupby(frame.columns[0])["itemDescription"].apply(list)
        return [set(normalize_item(x) for x in row if str(x).strip()) for row in grouped], {}, {"pricing_method": "unavailable"}
    if "Items" in frame.columns:
        values = frame["Items"].fillna("").astype(str).str.split(",")
    else:
        values = frame.apply(lambda row: row.dropna().tolist(), axis=1)
    return [set(normalize_item(x) for x in row if str(x).strip()) for row in values], {}, {"pricing_method": "unavailable"}


def profile(transactions: list[set[str]], raw_rows: int | None = None) -> DatasetProfile:
    sizes = [len(x) for x in transactions]
    items = set().union(*transactions) if transactions else set()
    total_cells = len(transactions) * max(len(items), 1)
    return DatasetProfile(
        transactions=len(transactions), unique_items=len(items),
        average_basket_size=sum(sizes) / max(len(sizes), 1),
        median_basket_size=float(pd.Series(sizes).median()) if sizes else 0.0,
        singleton_rate=sum(s == 1 for s in sizes) / max(len(sizes), 1),
        sparsity=1 - sum(sizes) / max(total_cells, 1),
        empty_rows=(raw_rows or len(transactions)) - len(transactions),
        duplicate_item_count=0,
    )


def fixture_transactions() -> list[set[str]]:
    seed = [
        {"whole milk", "yogurt", "tropical fruit"},
        {"whole milk", "other vegetables", "rolls/buns"},
        {"yogurt", "tropical fruit", "coffee"},
        {"whole milk", "other vegetables", "yogurt"},
        {"rolls/buns", "sausage", "whole milk"},
        {"other vegetables", "root vegetables", "whole milk"},
        {"tropical fruit", "yogurt", "whole milk"},
        {"whole milk", "soda"},
        {"rolls/buns", "other vegetables"},
        {"yogurt", "coffee"},
    ]
    return seed * 12


def fixture_price_catalog() -> dict[str, float]:
    return {"whole milk": 2.49, "yogurt": 1.19, "tropical fruit": 3.29, "other vegetables": 2.79,
            "rolls/buns": 2.19, "coffee": 6.49, "sausage": 4.99, "root vegetables": 2.39, "soda": 1.79}


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
