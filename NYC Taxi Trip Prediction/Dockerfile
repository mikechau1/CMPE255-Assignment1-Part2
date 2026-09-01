# ---- stage 1: build the frontend ----------------------------------------
FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- stage 2: python runtime --------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# libgomp is LightGBM's OpenMP runtime; the slim image does not ship it.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 curl \
 && rm -rf /var/lib/apt/lists/*

# Dependencies first: this layer is cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ./src/
COPY config.yaml ./
COPY --from=frontend /build/dist ./frontend/dist

# Trained artifacts and the cached zone geometry. Both are gitignored, so
# build after training locally, or mount them as volumes at run time.
COPY model[s]/ ./models/
COPY data/ge[o]/ ./data/geo/

RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "nyctaxi.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
