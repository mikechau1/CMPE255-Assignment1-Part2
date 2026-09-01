# Linux/macOS/container equivalent of run.ps1.
.PHONY: help setup data train evaluate test lint frontend serve docker clean

PY  := .venv/bin/python
export PYTHONPATH := src
PORT ?= 8000
SAMPLE_FRAC ?= 0.06

help:  ## Show this help
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup:  ## Create the virtualenv and install dependencies
	python3 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt
	cd frontend && npm install

data:  ## Download source data and build the taxi-zone GeoJSON
	$(PY) -c "from nyctaxi.data.zones import build_zone_geojson; build_zone_geojson()"

train:  ## Train the model ladder (SAMPLE_FRAC=0.06)
	$(PY) -m nyctaxi.train --sample-frac $(SAMPLE_FRAC)

evaluate:  ## Render evaluation figures and docs/05-evaluation.md
	$(PY) -m nyctaxi.evaluate

test:  ## Run the test suite
	$(PY) -m pytest -q

lint:  ## Lint Python and typecheck the frontend
	$(PY) -m ruff check src tests
	cd frontend && npm run typecheck

frontend:  ## Build the production bundle
	cd frontend && npm run build

serve: ## Serve API + frontend on one port (PORT=8000)
	$(PY) -m uvicorn nyctaxi.api.main:app --host 127.0.0.1 --port $(PORT)

docker:  ## Build and run the container
	docker compose up --build

clean:  ## Remove caches and build output (keeps data and models)
	rm -rf .pytest_cache .ruff_cache frontend/dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
