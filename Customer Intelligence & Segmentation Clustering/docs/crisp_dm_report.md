# CRISP-DM report

## 1. Business understanding

**Objective:** identify stable and interpretable customer personas that support targeted retail marketing decisions.

**Success criteria:** produce a reproducible segmentation, quantify its quality and stability, explain each segment in business language, and expose the evidence through an admin dashboard.

**Constraints:** the Kaggle dataset is small, cross-sectional, and has no ground-truth segments. The result is exploratory—not a causal or predictive claim about future behavior.

## 2. Data understanding

The expected schema contains customer identifier, gender, age, annual income, and spending score. The pipeline generates a quality report covering shape, types, missingness, duplicates, identifier duplication, numeric ranges, IQR outliers, and leakage flags.

## 3. Data preparation

CustomerID is excluded as an identifier. Numeric features are coerced safely, duplicates are removed, incomplete analytical rows are excluded, and gender is normalized. Behavior-focused and all-numeric feature sets are tested. Scaling is part of the experiment configuration.

## 4. Modeling

K-Means is the primary model. Gaussian Mixture and DBSCAN are challengers. Candidate configurations vary algorithm, cluster count, feature set, scaler, density parameters, and random seed.

## 5. Evaluation

Internal metrics include silhouette, Davies–Bouldin, Calinski–Harabasz, inertia where applicable, cluster balance, and repeated-fit stability. The composite score is intentionally multi-objective. Final selection should also consider persona separation, cluster size, and marketing actionability.

## 6. Deployment

The selected run is serialized as dashboard-ready JSON. FastAPI serves artifacts, and React/Vite provides overview, quality, segment, evaluation, experiment, and lineage views. The dashboard includes the source type and generated timestamp so demo fallback results cannot be mistaken for Kaggle results.

