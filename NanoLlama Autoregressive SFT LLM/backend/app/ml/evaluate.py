"""Small, deterministic generation evaluation helpers for the dashboard."""

from __future__ import annotations

from .data import load_records


def prompt_set(records):
    return [
        {"prompt": item["messages"][0]["content"], "reference": item["messages"][-1]["content"]}
        for item in records
        if item["messages"] and item["messages"][0]["role"] == "user"
    ]
