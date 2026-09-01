# Data dictionary

| Field | Type | Meaning | Modeling treatment |
|---|---|---|---|
| CustomerID | integer | Unique customer identifier | Excluded; identifier only |
| Gender | category | Reported customer gender | Normalized; optional encoded challenger feature |
| Age | numeric | Customer age in years | Candidate feature |
| Annual Income (k$) | numeric | Annual income in thousands of dollars | Candidate feature |
| Spending Score (1-100) | numeric | Mall-assigned spending behavior score | Candidate feature |

## Derived fields

- `Gender_encoded`: Female=0, Male=1, unknown=0.5; used only in the explicit gender challenger configuration.
- `cluster`: model-assigned segment identifier.
- `pca.x`, `pca.y`: two-dimensional visualization coordinates, not modeling features.
