import maplibregl from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { MAP_STYLES, type Theme } from "../hooks/useTheme";
import { api } from "../lib/api";
import { formatDuration, formatHour, toNaiveLocalISO } from "../lib/format";
import type { LatLon, ZoneTravelTime } from "../lib/types";

const ZONE_SOURCE = "zones";
const ZONE_FILL = "zones-fill";
const ZONE_LINE = "zones-line";

const DESTINATIONS: { name: string; point: LatLon }[] = [
  { name: "Times Square", point: { lat: 40.758, lon: -73.9855 } },
  { name: "JFK Airport", point: { lat: 40.6413, lon: -73.7781 } },
  { name: "Wall Street", point: { lat: 40.7061, lon: -74.0087 } },
  { name: "LaGuardia", point: { lat: 40.7769, lon: -73.874 } },
  { name: "Barclays Center", point: { lat: 40.6826, lon: -73.9754 } },
];

// Sequential ramp, dark-to-bright, readable on both basemaps.
const RAMP = ["#0d3b66", "#1e6091", "#3d8ea8", "#7fb069", "#e9c46a", "#f4a261", "#e76f51"];

/**
 * "How far is everywhere from here?" -- the model answers for all 263 taxi
 * zones at once, so the choropleth shows the deployed model's own view of the
 * city rather than a static historical average, and recolours when the
 * destination or hour changes.
 */
export function Insights({ theme }: { theme: Theme }) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const popup = useRef<maplibregl.Popup | null>(null);
  // The zone GeoJSON is ~3.7 MB and never changes. Fetch and parse it once,
  // not on every hour-slider move.
  const zoneGeometry = useRef<GeoJSON.FeatureCollection | null>(null);

  const [destination, setDestination] = useState(DESTINATIONS[0]);
  const [hour, setHour] = useState(18);
  const [data, setData] = useState<ZoneTravelTime | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // --- create map -------------------------------------------------------
  useEffect(() => {
    if (!container.current || map.current) return;
    const m = new maplibregl.Map({
      container: container.current,
      style: MAP_STYLES[theme],
      center: [-73.94, 40.72],
      zoom: 10.1,
      attributionControl: { compact: true },
    });
    map.current = m;
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    popup.current = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
    return () => {
      m.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    map.current?.setStyle(MAP_STYLES[theme]);
  }, [theme]);

  // --- fetch predictions -------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const when = new Date();
    when.setHours(hour, 0, 0, 0);

    api
      .zoneTravelTimes({
        pickup: destination.point, // ignored server-side; origins are the zones
        dropoff: destination.point,
        // Naive local, not UTC -- see toNaiveLocalISO. The hour slider must
        // mean the hour it says.
        departure: toNaiveLocalISO(when),
        passengers: 1,
      })
      .then((d) => !cancelled && setData(d))
      .catch(() => !cancelled && setError("Could not load zone travel times."))
      .finally(() => !cancelled && setLoading(false));

    return () => {
      cancelled = true;
    };
  }, [destination, hour]);

  // --- paint the choropleth ---------------------------------------------
  useEffect(() => {
    const m = map.current;
    if (!m || !data) return;

    // Colour stops depend on the current min/max, which change with the hour,
    // so they are recomputed on every render rather than fixed at layer-add.
    const colourStops = () =>
      RAMP.flatMap((color, i) => [
        data.min_s + ((data.max_s - data.min_s) * i) / (RAMP.length - 1),
        color,
      ]);

    const render = async () => {
      if (!zoneGeometry.current) {
        zoneGeometry.current = await api.zones();
      }
      const zones = zoneGeometry.current;
      const byId = new Map(data.zones.map((z) => [z.location_id, z]));

      // Merge the predictions onto the geometry so the paint expression can
      // read duration straight off each feature.
      const merged = {
        ...zones,
        features: zones.features.map((f) => {
          const z = byId.get((f.properties as { location_id: number }).location_id);
          return {
            ...f,
            properties: { ...f.properties, duration_s: z?.duration_s ?? null },
          };
        }),
      } as GeoJSON.FeatureCollection;

      // Updating an existing source is safe mid-style-load; only adding the
      // source and layers needs a loaded style. Gating the update too meant a
      // slow style load left the choropleth permanently unpainted.
      const existing = m.getSource(ZONE_SOURCE) as maplibregl.GeoJSONSource | undefined;
      if (existing) {
        existing.setData(merged);
        if (m.getLayer(ZONE_FILL)) {
          m.setPaintProperty(ZONE_FILL, "fill-color", [
            "interpolate",
            ["linear"],
            ["get", "duration_s"],
            ...colourStops(),
          ]);
        }
        return;
      }

      if (!m.isStyleLoaded()) return;

      m.addSource(ZONE_SOURCE, { type: "geojson", data: merged });
      m.addLayer({
        id: ZONE_FILL,
        type: "fill",
        source: ZONE_SOURCE,
        paint: {
          "fill-color": ["interpolate", ["linear"], ["get", "duration_s"], ...colourStops()],
          "fill-opacity": 0.72,
        },
      });
      m.addLayer({
        id: ZONE_LINE,
        type: "line",
        source: ZONE_SOURCE,
        paint: { "line-color": "rgba(255,255,255,.18)", "line-width": 0.5 },
      });

      m.on("mousemove", ZONE_FILL, (e) => {
        const f = e.features?.[0];
        if (!f) return;
        m.getCanvas().style.cursor = "pointer";
        const p = f.properties as { zone: string; borough: string; duration_s: number | null };
        popup.current
          ?.setLngLat(e.lngLat)
          .setHTML(
            `<strong>${p.zone}</strong><br/><span style="opacity:.7">${p.borough}</span><br/>` +
              (p.duration_s
                ? `<span style="color:var(--accent)">${formatDuration(p.duration_s)}</span> to ${destination.name}`
                : "no estimate"),
          )
          .addTo(m);
      });
      m.on("mouseleave", ZONE_FILL, () => {
        m.getCanvas().style.cursor = "";
        popup.current?.remove();
      });
    };

    render();
    // `load` is the retry that actually lands: styledata fires while the style
    // is still settling, when isStyleLoaded() is false and the add path bails.
    m.on("styledata", render);
    m.on("load", render);
    return () => {
      m.off("styledata", render);
      m.off("load", render);
    };
  }, [data, destination.name]);

  return (
    <div className="absolute inset-0 top-[52px]">
      {/* h/w rather than inset-0 -- see the note in MapCanvas */}
      <div ref={container} className="h-full w-full" />

      <div className="glass fade-up absolute top-4 left-4 z-20 w-[302px] rounded-2xl p-4">
        <h2 className="text-sm font-semibold text-ink">Travel time across the city</h2>
        <p className="mt-1 text-[11.5px] leading-snug text-dim">
          The model predicts a trip from every one of the 263 taxi zones to one destination. Hover
          a zone for its estimate.
        </p>

        <label className="mt-3 mb-1.5 block text-[11px] font-medium tracking-wide text-dim uppercase">
          Destination
        </label>
        <div className="flex flex-wrap gap-1.5">
          {DESTINATIONS.map((d) => (
            <button
              key={d.name}
              onClick={() => setDestination(d)}
              className={`rounded-lg border px-2 py-1 text-[11px] transition ${
                d.name === destination.name
                  ? "border-accent/60 bg-accent/15 text-accent-ink"
                  : "border-line text-dim hover:border-accent/40 hover:text-ink"
              }`}
            >
              {d.name}
            </button>
          ))}
        </div>

        <label className="mt-3 mb-1 block text-[11px] font-medium tracking-wide text-dim uppercase">
          Departure hour · <span className="text-accent-ink">{formatHour(hour)}</span>
        </label>
        <input
          type="range"
          min={0}
          max={23}
          value={hour}
          onChange={(e) => setHour(Number(e.target.value))}
          className="w-full accent-[var(--accent)]"
        />

        {data && (
          <div className="mt-3">
            <div
              className="h-2 w-full rounded-full"
              style={{ background: `linear-gradient(to right, ${RAMP.join(",")})` }}
            />
            <div className="mt-1 flex justify-between text-[10.5px] text-faint tnum">
              <span>{formatDuration(data.min_s)}</span>
              <span>{formatDuration(data.max_s)}</span>
            </div>
          </div>
        )}

        {loading && <p className="mt-2 text-[11px] text-faint">Predicting 263 trips…</p>}
        {error && <p className="mt-2 text-[11px] text-warn">{error}</p>}
      </div>
    </div>
  );
}
