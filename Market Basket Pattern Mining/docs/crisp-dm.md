# CRISP-DM Project Report

## Business understanding

BasketLab identifies reliable co-purchase patterns for cross-sell, bundle design, and product placement. The primary users are retail analysts and data scientists. The output supports prioritization; it does not establish causal effects.

## Data understanding

The deployment dataset is the Kaggle CSV mirror of UCI Online Retail, with invoice, product description, quantity, timestamp, unit price, customer, and country fields. The original Groceries fixture remains available for tests and offline demonstrations.

## Data preparation

Items are normalized to lowercase, whitespace is collapsed, and duplicate products inside a basket are represented once. Cancellations, returns, missing descriptions, and non-positive prices are removed. Median positive observed unit price per item supplies a robust GBP cart price. The pipeline uses a deterministic 80/20 transaction split for validation.

## Modeling

Apriori-style frequent-itemset enumeration is the interpretable baseline. FP-Growth is represented by the same mining interface so runtime and output quality can be compared. Rules use support, confidence, lift, conviction, leverage, and coverage.

## Evaluation

Evaluation combines support and lift with holdout hit rate, coverage, rule-count complexity, and runtime. The autoresearch loop performs bounded one-parameter mutations and keeps a full trial ledger.

## Deployment

FastAPI serves versioned JSON artifacts. The React dashboard visualizes the profile, rule table, network-ready rule data, and autoresearch leaderboard. Artifacts contain dataset provenance and configuration for reproducibility.

## Limitations

Association does not imply causation. The lack of price, quantity, temporal, and customer-level data prevents causal promotion analysis, trend analysis, margin optimization, and personalized recommendations.
