# Model card

## Intended use

Exploratory customer persona discovery and marketing hypothesis generation for the Mall Customers dataset.

## Not intended for

Credit, eligibility, employment, pricing, legal, or other high-impact individual decisions. The dataset is small, synthetic-like in structure, and lacks temporal outcomes.

## Metrics

Internal clustering metrics and repeated-fit stability are reported. There is no ground-truth label, so external accuracy is not available.

## Limitations

Clusters depend on feature selection, scaling, random seed, and the geometry assumptions of each algorithm. Spending score is an assigned score rather than observed transaction history. Segment labels describe groups; they do not establish customer-level causality.

