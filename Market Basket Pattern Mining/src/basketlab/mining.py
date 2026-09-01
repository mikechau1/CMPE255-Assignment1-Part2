from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from math import inf

from .models import MiningConfig, RuleRecord


def _apriori(transactions: list[set[str]], config: MiningConfig) -> dict[tuple[str, ...], float]:
    n = len(transactions)
    if not n:
        return {}
    counts: Counter[tuple[str, ...]] = Counter()
    result: dict[tuple[str, ...], float] = {}
    current = {tuple([item]) for basket in transactions for item in basket}
    for size in range(1, config.max_itemset_size + 1):
        counts.clear()
        for basket in transactions:
            for candidate in combinations(sorted(basket), size):
                if set(candidate).issubset(basket):
                    counts[candidate] += 1
        level = {items: count / n for items, count in counts.items() if count / n >= config.min_support}
        result.update(level)
        if not level:
            break
        previous = set(level)
        current = {candidate for candidate in combinations(sorted({item for key in previous for item in key}), size + 1)
                   if all(tuple(sorted(subset)) in previous for subset in combinations(candidate, size))}
    return result


class _Node:
    def __init__(self, item: str | None = None, parent: "_Node | None" = None):
        self.item, self.count, self.parent = item, 0, parent
        self.children: dict[str, _Node] = {}
        self.link: _Node | None = None


def _fpgrowth(transactions: list[set[str]], config: MiningConfig) -> dict[tuple[str, ...], float]:
    minimum = max(1, int(config.min_support * len(transactions) + 0.999999))
    counts = Counter(item for basket in transactions for item in basket)
    frequent = {item: count for item, count in counts.items() if count >= minimum}
    if not frequent:
        return {}
    root = _Node()
    headers: dict[str, list[_Node]] = defaultdict(list)
    for basket in transactions:
        ordered = sorted((x for x in basket if x in frequent), key=lambda x: (-frequent[x], x))
        node = root
        for item in ordered:
            child = node.children.get(item)
            if child is None:
                child = _Node(item, node)
                node.children[item] = child
                headers[item].append(child)
            child.count += 1
            node = child
    result: dict[tuple[str, ...], float] = {tuple([item]): count / len(transactions) for item, count in frequent.items()}

    def grow(prefix: tuple[str, ...], local_headers: dict[str, list[_Node]]) -> None:
        for item in sorted(local_headers, key=lambda x: (sum(n.count for n in local_headers[x]), x)):
            pattern = tuple(sorted(prefix + (item,)))
            support = sum(n.count for n in local_headers[item]) / len(transactions)
            if support < config.min_support or len(pattern) > config.max_itemset_size:
                continue
            result[pattern] = support
            conditional: list[tuple[list[str], int]] = []
            for leaf in local_headers[item]:
                path, parent = [], leaf.parent
                while parent and parent.item:
                    path.append(parent.item)
                    parent = parent.parent
                if path:
                    conditional.append((path[::-1], leaf.count))
            conditional_counts = Counter(item2 for path, count in conditional for item2 in path for _ in range(count))
            allowed = {x for x, count in conditional_counts.items() if count >= minimum}
            if not allowed:
                continue
            child_root = _Node()
            child_headers: dict[str, list[_Node]] = defaultdict(list)
            for path, weight in conditional:
                node = child_root
                for item2 in sorted((x for x in path if x in allowed), key=lambda x: (-conditional_counts[x], x)):
                    child = node.children.get(item2)
                    if child is None:
                        child = _Node(item2, node)
                        node.children[item2] = child
                        child_headers[item2].append(child)
                    child.count += weight
                    node = child
            grow(prefix + (item,), child_headers)
    grow((), headers)
    return result


def frequent_itemsets(transactions: list[set[str]], config: MiningConfig) -> dict[tuple[str, ...], float]:
    if config.algorithm.lower() in {"fpgrowth", "fp-growth", "fp_growth"}:
        return _fpgrowth(transactions, config)
    return _apriori(transactions, config)


def build_rules(transactions: list[set[str]], config: MiningConfig) -> list[RuleRecord]:
    itemsets = frequent_itemsets(transactions, config)
    support = itemsets
    rules: list[RuleRecord] = []
    for itemset, itemset_support in itemsets.items():
        if len(itemset) < 2:
            continue
        for r in range(1, min(config.max_antecedent_size, len(itemset) - 1) + 1):
            for antecedent in combinations(itemset, r):
                consequent = tuple(x for x in itemset if x not in antecedent)
                a_support = support.get(tuple(sorted(antecedent)), 0.0)
                c_support = support.get(tuple(sorted(consequent)), 0.0)
                if not a_support or not c_support:
                    continue
                confidence = itemset_support / a_support
                lift = confidence / c_support
                if confidence < config.min_confidence or lift < config.min_lift:
                    continue
                conviction = (1 - c_support) / max(1 - confidence, 1e-12) if confidence < 1 else inf
                rules.append(RuleRecord(tuple(sorted(antecedent)), tuple(sorted(consequent)), itemset_support, confidence, lift, (0 if conviction == inf else conviction), itemset_support - a_support * c_support, a_support))
    return sorted(rules, key=lambda r: (r.lift, r.confidence, r.support), reverse=True)


def validate_rules(rules: list[RuleRecord], holdout: list[set[str]]) -> list[RuleRecord]:
    total = max(len(holdout), 1)
    for rule in rules:
        matching = [b for b in holdout if set(rule.antecedent).issubset(b)]
        hits = sum(bool(set(rule.consequent) & b) for b in matching)
        rule.validation_hit_rate = hits / max(len(matching), 1)
    return rules
