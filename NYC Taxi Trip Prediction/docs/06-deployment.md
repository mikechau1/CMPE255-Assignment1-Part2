# CRISP-DM phase 6 — Deployment

## Shape of the deployment

**One process, one port.** FastAPI serves the JSON API *and* the built React
bundle. There is no second Node runtime at rest, no CORS configuration in
production, and one thing to start, containerise or crash-loop.

```
Browser ── GET /            → index.html + assets  (StaticFiles)
        ── POST /api/predict → PredictionService → LightGBM boosters
        ── GET  /api/route   → OSRM proxy   (cached, server-side)
        ── GET  /api/geocode → Nominatim proxy (cached, rate-limited, UA set)
```

The model bundle is loaded **once at startup** into application state, not per
request. A prediction is a feature transform plus four booster calls —
comfortably sub-second, which is what makes dragging a map pin feel live.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness, loaded model version, data source |
| `GET /api/model` | Metadata, metrics, feature importance |
| `GET /api/model/residuals` | Validation predictions + error slices |
| `POST /api/predict` | Duration, P10–P90, ETA, fare breakdown, SHAP contributions |
| `POST /api/predict/curve` | The same trip at all 24 departure hours |
| `GET /api/route` | OSRM driving route (display + fare input only) |
| `GET /api/geocode` | Nominatim address search, NYC-bounded |
| `GET /api/zones` | Taxi-zone GeoJSON |
| `POST /api/zones/travel-time` | Predicted duration from all 263 zones to one destination |

Interactive OpenAPI docs at `/docs`.

## Why the external services are proxied server-side

Nominatim's usage policy requires an identifying `User-Agent` and roughly one
request per second. A browser cannot set `User-Agent`, and every open tab would
be an independent, uncached client hammering a free service. Proxying gives us
one polite consumer with a shared cache, and removes CORS from the picture.

Both proxies are **best-effort**. If OSRM or Nominatim is slow or rate-limited,
the endpoint returns `available: false` rather than an error, and the map falls
back to drawing a straight line. A degraded map beats a broken one.

## The train/serve skew trap, and how it is avoided

The map draws a real road route, and it would be tempting to feed OSRM's
distance or duration to the model as a feature. **It is not a feature.** Calling
a routing service once per row is infeasible for two million training rows, so
the model would depend at serving time on a signal it never saw during
training — a silent correctness bug that no test on the training set would
catch.

The route is used for exactly two things: drawing the line, and supplying road
distance to the *deterministic* fare calculator. This is documented at the top
of `src/nyctaxi/api/routing.py` so the next person does not undo it.

## Running it

### Local, one command

```powershell
./run.ps1              # venv, deps, data, train, build, serve
./run.ps1 -Serve       # skip training, just serve an existing model
./run.ps1 -Port 8100   # if 8000 is taken
```

Or step by step:

```bash
python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -r requirements.txt
PYTHONPATH=src python -m nyctaxi.train --sample-frac 0.06
PYTHONPATH=src python -m nyctaxi.evaluate
cd frontend && npm install && npm run build && cd ..
PYTHONPATH=src python -m uvicorn nyctaxi.api.main:app --port 8000
```

### Container

```bash
docker compose up --build
```

The Dockerfile is multi-stage: a Node stage builds the frontend, and a slim
Python runtime carries only the built assets plus the trained model. It runs as
a non-root user and declares a healthcheck against `/api/health`.

> Docker is not installed on the machine this was developed on, so the
> container files are written and reviewed but **have not been executed here**.
> Treat the first `docker compose up` as unverified.

## Monitoring and retraining

Deployed, this model needs two things watched:

1. **Drift in the input distribution.** Traffic patterns are not stationary —
   construction, congestion pricing, and seasonal demand all move them. The
   model was trained on Q1 2016.
2. **Coverage of the P10–P90 band.** This is the best available early warning.
   If realised coverage drifts away from 80%, the model's confidence no longer
   matches reality, and that shows up before the point estimate visibly rots.

`/api/health` and `/api/model` expose version and metrics for scraping.
Retraining is one command and writes a new version directory rather than
overwriting; `models/latest.json` is the only thing that changes, so rollback
is a one-line edit.

## Upgrading the data source

The shipped model was trained on the TLC fallback, which is zone-resolution.
To switch to true coordinates:

1. Create a token at kaggle.com → Settings → API → **Create New Token**
2. Accept the rules for the `nyc-taxi-trip-duration` competition
3. Save `kaggle.json` to `~/.kaggle/`
4. Re-run training

No code changes. The loader detects the credentials and switches sources; the
UI and model report update to say so automatically.

← Back to [Evaluation](05-evaluation.md) · [README](../README.md)
