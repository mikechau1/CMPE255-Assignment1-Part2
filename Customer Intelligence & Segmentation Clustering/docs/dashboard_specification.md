# Dashboard specification

**Purpose:** This dashboard answers “Which customer segments are present, how trustworthy are they, and what action does each suggest?” for data scientists and marketing analysts who need to inspect and operationalize clustering decisions.

## Information hierarchy

- Hero KPIs: customers, chosen clusters, silhouette, stability.
- Context: algorithm, feature set, source type, generated time, score progression.
- Diagnostics: profiles, PCA scatter, quality checks, challenger metrics, experiment log.

## Interactivity

- Filter PCA points and customer table by cluster.
- Select dashboard view from Overview, Data Quality, Segments, Model Evaluation, Autoresearch, and Lineage.
- Inspect accepted/rejected experiments and configuration details.

## Data contract

The frontend consumes `/api/dashboard`, which returns metadata, quality, selected configuration, metrics, PCA coordinates, profiles, cluster sizes, and experiment history.

