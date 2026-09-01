# BasketLab Dashboard Specification

**Purpose:** This dashboard answers which products are meaningfully associated in grocery baskets for analysts and retail decision-makers who need to prioritize cross-sell, bundle, and placement opportunities.

**Primary audience:** Retail analysts and data scientists. **Secondary audience:** managers reviewing experiment outcomes. **Usage:** ad-hoc and weekly research review. **Owner:** project analytics team. **Sensitive data:** none.

## Information hierarchy

Hero metrics: transaction count, item count, average basket size, accepted rules, and best lift. Supporting sections show basket distributions, item popularity, rule diagnostics, and autoresearch trials. Detailed rules are searchable and filterable.

## Pages

1. Overview: KPI cards, basket profile, top rules, and experiment status.
2. Rules: sortable rule table with support, confidence, lift, conviction, leverage, coverage, and validation hit rate.
3. Autoresearch: trial leaderboard, accepted-path view, current configuration, and runtime/quality trade-off.
4. Methodology: CRISP-DM status, data lineage, assumptions, and paper-to-metric mapping.
5. Network & Cart: directed item-association graph with lift/confidence encodings, node zoom/drag/selection, cart construction, and explainable next-item recommendations.

## Interactivity

Global filters are minimum lift and result count. Users can search rules, inspect antecedent/consequent details, download JSON, and drill from a rule to its source experiment. The UI is responsive, keyboard navigable, and uses blue/orange contrasts for accessible comparison.

Network interactions include click or Enter to add an item, drag to reposition nodes, wheel or controls to zoom, and reset to restore the deterministic layout. Recommendations appear only when all items in a rule antecedent are present in the cart; each suggestion exposes its lift and confidence.

## Metric definitions

| Metric | Definition |
|---|---|
| Support | Fraction of transactions containing the itemset |
| Confidence | Support of antecedent and consequent divided by antecedent support |
| Lift | Confidence divided by consequent support |
| Conviction | Directional implication strength based on consequent absence |
| Coverage | Antecedent support |
| Hit rate | Holdout baskets containing the consequent among baskets containing the antecedent |
