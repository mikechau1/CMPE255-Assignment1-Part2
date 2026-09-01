from __future__ import annotations

from dataclasses import asdict
from time import perf_counter
from typing import Any

from .mining import build_rules, validate_rules
from .models import MiningConfig


def score(rules: list, runtime: float) -> float:
    if not rules:
        return 0.0
    quality = sum(r.validation_hit_rate for r in rules) / len(rules)
    lift = min(sum(r.lift for r in rules) / len(rules) / 4, 1)
    coverage = min(sum(r.coverage for r in rules) / len(rules) * 4, 1)
    complexity_penalty = min(len(rules) / 1000, 0.25)
    return 0.45 * quality + 0.30 * lift + 0.25 * coverage - complexity_penalty - min(runtime / 60, 0.1)


def hill_climb(transactions: list[set[str]], holdout: list[set[str]], start: MiningConfig, budget: int = 18) -> dict[str, Any]:
    current = start
    trials = []
    best_score = -1.0
    directions = [("min_support", 0.005), ("min_confidence", 0.05), ("min_lift", 0.05), ("max_itemset_size", 1)]
    for index in range(budget):
        field, delta = directions[index % len(directions)]
        value = getattr(current, field)
        candidate_value = value + delta if index % 2 == 0 else value - delta
        if field == "max_itemset_size":
            candidate_value = max(2, min(4, int(candidate_value)))
        else:
            candidate_value = max(0.005, min(0.95, round(candidate_value, 4)))
        candidate = MiningConfig(**{**asdict(current), field: candidate_value})
        started = perf_counter()
        rules = validate_rules(build_rules(transactions, candidate), holdout)
        runtime = perf_counter() - started
        value_score = score(rules, runtime)
        accepted = value_score > best_score
        if accepted:
            best_score, current = value_score, candidate
        trials.append({"trial": index + 1, "config": candidate.to_dict(), "score": value_score, "rule_count": len(rules), "runtime_seconds": runtime, "accepted": accepted})
    final_rules = validate_rules(build_rules(transactions, current), holdout)
    return {"best_config": current.to_dict(), "best_score": best_score, "trials": trials, "rules": [r.to_dict() for r in final_rules]}

