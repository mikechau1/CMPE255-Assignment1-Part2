# BasketLab: CRISP-DM Associative Pattern Mining

BasketLab is a reproducible market-basket research application for the Kaggle Groceries benchmark (9,835 transactions, 169 items). It combines a Python mining engine, metric-aware hill-climbing autoresearch, FastAPI, and a Vite/React analyst dashboard.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m basketlab.cli demo --output artifacts/demo.json
uvicorn basketlab.api:app --reload
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The demo uses a deterministic fixture when retail data is absent. For observed-price GMV, download the MIT-licensed Kaggle Online Retail CSV and place it at `data/raw/online_retail.csv`:

```powershell
python -c "import kagglehub; print(kagglehub.dataset_download('luisrenterialezano/retail-sales-dataset'))"
python -m basketlab.cli run --input data/raw/online_retail.csv --output artifacts/demo.json --search-budget 8
```

The loader groups positive, non-cancelled invoice lines into baskets and uses each product's median observed `UnitPrice` in GBP for cart GMV.

## Research workflow

```powershell
python -m basketlab.cli run --input data/raw/online_retail.csv --output artifacts/latest.json --search-budget 8
pytest
```

The complete CRISP-DM and dashboard specifications are in `docs/`. Research claims and primary sources are recorded in `docs/research-log.md`.

## Scope and limitations

The source data contains basket membership but no price, quantity, timestamp, or customer identity. Rules are associations, not causal effects. Validation is transaction-level and should be treated as an educational robustness check, not a production recommendation evaluation.
