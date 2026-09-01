import { useCallback, useEffect, useRef, useState } from "react";
import { HourCurve } from "../components/HourCurve";
import { MapCanvas } from "../components/MapCanvas";
import { ResultCard } from "../components/ResultCard";
import { SearchBox } from "../components/SearchBox";
import type { Theme } from "../hooks/useTheme";
import { api, ApiError } from "../lib/api";
import { toLocalInputValue } from "../lib/format";
import type { CurveResponse, LatLon, PredictResponse } from "../lib/types";

/** Recognisable trips, so the app is useful before the user knows the map. */
const PRESETS: { name: string; from: LatLon; to: LatLon; fromName: string; toName: string }[] = [
  {
    name: "Midtown → JFK",
    from: { lat: 40.7580, lon: -73.9855 },
    to: { lat: 40.6413, lon: -73.7781 },
    fromName: "Times Square",
    toName: "JFK Airport",
  },
  {
    name: "Wall St → LaGuardia",
    from: { lat: 40.7061, lon: -74.0087 },
    to: { lat: 40.7769, lon: -73.8740 },
    fromName: "Wall Street",
    toName: "LaGuardia Airport",
  },
  {
    name: "Village → Upper East",
    from: { lat: 40.7336, lon: -74.0027 },
    to: { lat: 40.7736, lon: -73.9566 },
    fromName: "West Village",
    toName: "Upper East Side",
  },
];

interface Props {
  theme: Theme;
}

export function Estimator({ theme }: Props) {
  const [pickup, setPickup] = useState<LatLon | null>(null);
  const [dropoff, setDropoff] = useState<LatLon | null>(null);
  const [pickupName, setPickupName] = useState("");
  const [dropoffName, setDropoffName] = useState("");
  const [departure, setDeparture] = useState(() => toLocalInputValue(new Date()));
  const [passengers, setPassengers] = useState(1);

  const [prediction, setPrediction] = useState<PredictResponse | null>(null);
  const [curve, setCurve] = useState<CurveResponse | null>(null);
  const [routeGeometry, setRouteGeometry] = useState<GeoJSON.LineString | null>(null);
  const [roadKm, setRoadKm] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Clicking the map fills whichever endpoint is empty, then alternates.
  const nextTarget = useRef<"pickup" | "dropoff">("pickup");

  const handleMapPick = useCallback(
    (point: LatLon) => {
      const target = !pickup ? "pickup" : !dropoff ? "dropoff" : nextTarget.current;
      if (target === "pickup") {
        setPickup(point);
        setPickupName(`${point.lat.toFixed(4)}, ${point.lon.toFixed(4)}`);
        nextTarget.current = "dropoff";
      } else {
        setDropoff(point);
        setDropoffName(`${point.lat.toFixed(4)}, ${point.lon.toFixed(4)}`);
        nextTarget.current = "pickup";
      }
    },
    [pickup, dropoff],
  );

  // --- fetch the road route whenever the endpoints move ----------------
  useEffect(() => {
    if (!pickup || !dropoff) {
      setRouteGeometry(null);
      setRoadKm(null);
      return;
    }
    let cancelled = false;
    api
      .route(pickup, dropoff)
      .then((r) => {
        if (cancelled) return;
        if (r.available && r.geometry) {
          setRouteGeometry(r.geometry);
          setRoadKm(r.distance_km ?? null);
        } else {
          // Public OSRM is rate-limited; the map falls back to a straight line.
          setRouteGeometry(null);
          setRoadKm(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setRouteGeometry(null);
          setRoadKm(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [pickup, dropoff]);

  // --- predict ----------------------------------------------------------
  useEffect(() => {
    if (!pickup || !dropoff) {
      setPrediction(null);
      setCurve(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);

    const body = {
      // `departure` is already a naive local wall-clock string from the
      // datetime-local input. Sent verbatim on purpose: converting to UTC here
      // would shift the hour and score the trip against the wrong traffic.
      pickup,
      dropoff,
      departure: `${departure}:00`,
      passengers,
      road_distance_km: roadKm,
    };

    Promise.all([api.predict(body), api.curve(body)])
      .then(([p, c]) => {
        if (cancelled) return;
        setPrediction(p);
        setCurve(c);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(
          e instanceof ApiError
            ? e.message
            : "Could not reach the prediction service. Is the API running?",
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [pickup, dropoff, departure, passengers, roadKm]);

  const applyPreset = (p: (typeof PRESETS)[number]) => {
    setPickup(p.from);
    setDropoff(p.to);
    setPickupName(p.fromName);
    setDropoffName(p.toName);
    nextTarget.current = "pickup";
  };

  const swap = () => {
    setPickup(dropoff);
    setDropoff(pickup);
    setPickupName(dropoffName);
    setDropoffName(pickupName);
  };

  const setHour = (hour: number) => {
    const d = new Date(departure);
    d.setHours(hour, 0, 0, 0);
    setDeparture(toLocalInputValue(d));
  };

  const selectedHour = new Date(departure).getHours();

  return (
    <div className="absolute inset-0 top-[52px]">
      <MapCanvas
        theme={theme}
        pickup={pickup}
        dropoff={dropoff}
        routeGeometry={routeGeometry}
        onPick={handleMapPick}
        onDragPickup={setPickup}
        onDragDropoff={setDropoff}
      />

      {/* control + result panel, floating over the map */}
      <div className="pointer-events-none absolute inset-y-0 left-0 z-20 w-full max-w-[400px] overflow-y-auto p-4">
        <div className="pointer-events-auto glass fade-up rounded-2xl p-4">
          <div className="space-y-3">
            <SearchBox
              label="Pickup"
              placeholder="Search an address, or click the map"
              value={pickupName}
              accent="#34d399"
              onSelect={(p, name) => {
                setPickup(p);
                setPickupName(name);
              }}
              onClear={() => {
                setPickup(null);
                setPickupName("");
              }}
            />

            <div className="flex justify-end">
              <button
                onClick={swap}
                disabled={!pickup || !dropoff}
                className="rounded-lg border border-line px-2 py-1 text-[11px] text-dim transition hover:border-accent/50 hover:text-ink disabled:opacity-30"
                title="Swap pickup and dropoff"
              >
                ↑↓ swap
              </button>
            </div>

            <SearchBox
              label="Dropoff"
              placeholder="Search an address, or click the map"
              value={dropoffName}
              accent="#ffc72c"
              onSelect={(p, name) => {
                setDropoff(p);
                setDropoffName(name);
              }}
              onClear={() => {
                setDropoff(null);
                setDropoffName("");
              }}
            />

            <div className="grid grid-cols-[1fr_auto] gap-2">
              <div>
                <label className="mb-1.5 block text-[11px] font-medium tracking-wide text-dim uppercase">
                  Departure
                </label>
                <div className="flex gap-1.5">
                  <input
                    type="datetime-local"
                    value={departure}
                    onChange={(e) => setDeparture(e.target.value)}
                    className="w-full rounded-xl border border-line bg-surface-solid/60 px-2.5 py-2 text-[12.5px] text-ink outline-none focus:border-accent/60"
                  />
                  <button
                    onClick={() => setDeparture(toLocalInputValue(new Date()))}
                    className="rounded-xl border border-line px-2.5 text-[11px] text-dim transition hover:border-accent/50 hover:text-ink"
                  >
                    now
                  </button>
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-[11px] font-medium tracking-wide text-dim uppercase">
                  Riders
                </label>
                <select
                  value={passengers}
                  onChange={(e) => setPassengers(Number(e.target.value))}
                  className="rounded-xl border border-line bg-surface-solid/60 px-2 py-2 text-[12.5px] text-ink outline-none focus:border-accent/60"
                >
                  {[1, 2, 3, 4, 5, 6].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {!pickup || !dropoff ? (
              <div className="rounded-xl border border-dashed border-line px-3 py-3">
                <p className="text-[12.5px] leading-snug text-dim">
                  {!pickup
                    ? "Click the map to drop a pickup pin, or search an address."
                    : "Now set a dropoff — click the map again."}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {PRESETS.map((p) => (
                    <button
                      key={p.name}
                      onClick={() => applyPreset(p)}
                      className="rounded-lg border border-line px-2 py-1 text-[11px] text-dim transition hover:border-accent/50 hover:text-accent-ink"
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {error && (
              <div className="rounded-xl border border-warn/40 bg-warn/10 px-3 py-2 text-[12px] text-warn">
                {error}
              </div>
            )}
          </div>

          {prediction && (
            <>
              <div className="my-4 h-px bg-line" />
              <ResultCard data={prediction} stale={loading} />
            </>
          )}

          {curve && (
            <>
              <div className="my-4 h-px bg-line" />
              <HourCurve curve={curve} selectedHour={selectedHour} onSelectHour={setHour} />
            </>
          )}

          {prediction?.zone_resolution && (
            <p className="mt-3 rounded-lg border border-line bg-surface-solid/40 px-2.5 py-2 text-[10.5px] leading-snug text-faint">
              Trained on TLC zone-level data, so predictions are at taxi-zone resolution. Add
              Kaggle credentials and retrain for true address-level coordinates.
            </p>
          )}
        </div>
      </div>

      {/* map legend */}
      <div className="glass pointer-events-none absolute bottom-4 left-4 z-10 rounded-xl px-3 py-2 text-[11px] text-dim">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-[#34d399]" /> pickup
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-[#ffc72c]" /> dropoff
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded bg-[#ffc72c]" />
            {routeGeometry ? "road route" : "straight line"}
          </span>
        </div>
      </div>
    </div>
  );
}
