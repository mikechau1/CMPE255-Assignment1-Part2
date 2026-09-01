from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class MiningConfig:
    algorithm: str = "fpgrowth"
    min_support: float = 0.02
    min_confidence: float = 0.20
    min_lift: float = 1.05
    max_itemset_size: int = 3
    max_antecedent_size: int = 2
    seed: int = 42

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DatasetProfile:
    transactions: int
    unique_items: int
    average_basket_size: float
    median_basket_size: float
    singleton_rate: float
    sparsity: float
    empty_rows: int
    duplicate_item_count: int


@dataclass
class RuleRecord:
    antecedent: tuple[str, ...]
    consequent: tuple[str, ...]
    support: float
    confidence: float
    lift: float
    conviction: float
    leverage: float
    coverage: float
    validation_hit_rate: float = 0.0
    redundant: bool = False

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["antecedent"] = list(self.antecedent)
        result["consequent"] = list(self.consequent)
        return result

