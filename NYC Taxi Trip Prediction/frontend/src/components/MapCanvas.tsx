import maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";
import { MAP_STYLES, type Theme } from "../hooks/useTheme";
import type { LatLon } from "../lib/types";

const NYC_CENTER: [number, number] = [-73.98, 40.75];

const ROUTE_SOURCE = "trip-route";
const ROUTE_LINE = "trip-route-line";
const ROUTE_GLOW = "trip-route-glow";
const ROUTE_DASH = "trip-route-dash";

interface Props {
  theme: Theme;
  pickup: LatLon | null;
  dropoff: LatLon | null;
  routeGeometry: GeoJSON.LineString | null;
  onPick: (point: LatLon) => void;
  onDragPickup: (point: LatLon) => void;
  onDragDropoff: (point: LatLon) => void;
}

/** Build the marker DOM once; MapLibre just repositions it afterwards. */
function markerElement(kind: "pickup" | "dropoff"): HTMLElement {
  const el = document.createElement("div");
  el.className = "relative grid place-items-center cursor-grab active:cursor-grabbing";
  el.style.width = "26px";
  el.style.height = "26px";
  const color = kind === "pickup" ? "#34d399" : "#ffc72c";
  el.innerHTML = `
    <span style="position:absolute;inset:0;border-radius:9999px;background:${color};opacity:.35;animation:pulse-ring 2.4s ease-out infinite"></span>
    <span style="position:relative;width:15px;height:15px;border-radius:9999px;background:${color};
                 border:2.5px solid rgba(10,12,16,.85);box-shadow:0 3px 10px rgba(0,0,0,.5)"></span>`;
  el.title = kind === "pickup" ? "Pickup — drag to move" : "Dropoff — drag to move";
  return el;
}

export function MapCanvas({
  theme,
  pickup,
  dropoff,
  routeGeometry,
  onPick,
  onDragPickup,
  onDragDropoff,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const pickupMarker = useRef<maplibregl.Marker | null>(null);
  const dropoffMarker = useRef<maplibregl.Marker | null>(null);
  const dashFrame = useRef<number | null>(null);

  // Handlers live in refs so the map is created once and never torn down on
  // re-render -- rebuilding a GL map on every keystroke would flicker badly.
  const handlers = useRef({ onPick, onDragPickup, onDragDropoff });
  handlers.current = { onPick, onDragPickup, onDragDropoff };

  // --- create map once -------------------------------------------------
  useEffect(() => {
    if (!container.current || map.current) return;
    const m = new maplibregl.Map({
      container: container.current,
      style: MAP_STYLES[theme],
      center: NYC_CENTER,
      zoom: 11.4,
      attributionControl: { compact: true },
    });
    map.current = m;
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    m.on("click", (e) => handlers.current.onPick({ lat: e.lngLat.lat, lon: e.lngLat.lng }));
    m.getCanvas().style.cursor = "crosshair";

    return () => {
      if (dashFrame.current) cancelAnimationFrame(dashFrame.current);
      m.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- theme swap ------------------------------------------------------
  const mountedTheme = useRef(theme);
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    // Skip the first run: the map was *constructed* with this style, and
    // calling setStyle again would trigger a redundant full style reload that
    // drops the route source mid-flight. Only a real theme change reloads.
    if (mountedTheme.current === theme) return;
    mountedTheme.current = theme;
    m.setStyle(MAP_STYLES[theme]);
  }, [theme]);

  // --- markers ---------------------------------------------------------
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    if (!pickup) {
      pickupMarker.current?.remove();
      pickupMarker.current = null;
      return;
    }
    if (!pickupMarker.current) {
      pickupMarker.current = new maplibregl.Marker({
        element: markerElement("pickup"),
        draggable: true,
      })
        .setLngLat([pickup.lon, pickup.lat])
        .addTo(m);
      pickupMarker.current.on("dragend", () => {
        const p = pickupMarker.current!.getLngLat();
        handlers.current.onDragPickup({ lat: p.lat, lon: p.lng });
      });
    } else {
      pickupMarker.current.setLngLat([pickup.lon, pickup.lat]);
    }
  }, [pickup]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    if (!dropoff) {
      dropoffMarker.current?.remove();
      dropoffMarker.current = null;
      return;
    }
    if (!dropoffMarker.current) {
      dropoffMarker.current = new maplibregl.Marker({
        element: markerElement("dropoff"),
        draggable: true,
      })
        .setLngLat([dropoff.lon, dropoff.lat])
        .addTo(m);
      dropoffMarker.current.on("dragend", () => {
        const p = dropoffMarker.current!.getLngLat();
        handlers.current.onDragDropoff({ lat: p.lat, lon: p.lng });
      });
    } else {
      dropoffMarker.current.setLngLat([dropoff.lon, dropoff.lat]);
    }
  }, [dropoff]);

  // --- route line ------------------------------------------------------
  useEffect(() => {
    const m = map.current;
    if (!m) return;

    const draw = () => {
      // Fall back to a straight line when routing is unavailable, so the map
      // always shows the trip it is estimating.
      const line: GeoJSON.LineString | null =
        routeGeometry ??
        (pickup && dropoff
          ? {
              type: "LineString",
              coordinates: [
                [pickup.lon, pickup.lat],
                [dropoff.lon, dropoff.lat],
              ],
            }
          : null);

      const existing = m.getSource(ROUTE_SOURCE) as maplibregl.GeoJSONSource | undefined;

      // Updating an existing source must NOT be gated on isStyleLoaded().
      // The OSRM route usually arrives while the basemap style is still
      // loading; gating here silently dropped it and left the straight-line
      // placeholder on screen forever. setData is safe mid-load.
      if (existing) {
        existing.setData(line ? { type: "Feature", properties: {}, geometry: line } : {
          type: "FeatureCollection",
          features: [],
        });
        return;
      }
      if (!line) return;

      // Only adding sources and layers genuinely needs a loaded style; if it
      // is not ready the load/styledata listeners below call us again.
      if (!m.isStyleLoaded()) return;

      const data: GeoJSON.Feature = { type: "Feature", properties: {}, geometry: line };
      {
        // A style reload wipes sources but can leave layer ids behind, so
        // adding blindly here can throw and abort the redraw.
        for (const id of [ROUTE_GLOW, ROUTE_LINE, ROUTE_DASH]) {
          if (m.getLayer(id)) m.removeLayer(id);
        }
        m.addSource(ROUTE_SOURCE, { type: "geojson", data });
        // Three stacked layers: a soft glow, the solid route, and a moving
        // dash on top that reads as direction of travel.
        m.addLayer({
          id: ROUTE_GLOW,
          type: "line",
          source: ROUTE_SOURCE,
          layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": "#ffc72c", "line-width": 14, "line-blur": 14, "line-opacity": 0.3 },
        });
        m.addLayer({
          id: ROUTE_LINE,
          type: "line",
          source: ROUTE_SOURCE,
          layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": "#ffc72c", "line-width": 4.5, "line-opacity": 0.95 },
        });
        m.addLayer({
          id: ROUTE_DASH,
          type: "line",
          source: ROUTE_SOURCE,
          layout: { "line-cap": "butt" },
          paint: {
            "line-color": "#0a0c10",
            "line-width": 2,
            "line-opacity": 0.55,
            "line-dasharray": [0, 4, 3],
          },
        });
        animateDash();
      }
    };

    // Marching-ants: cycling the dash pattern gives the route motion without
    // re-uploading geometry each frame.
    const dashPatterns: [number, number, number][] = [
      [0, 4, 3],
      [0.5, 4, 2.5],
      [1, 4, 2],
      [1.5, 4, 1.5],
      [2, 4, 1],
      [2.5, 4, 0.5],
      [3, 4, 0],
    ];
    let step = 0;
    let last = 0;
    function animateDash(t = 0) {
      const m2 = map.current;
      if (!m2) return;
      if (t - last > 90) {
        last = t;
        step = (step + 1) % dashPatterns.length;
        if (m2.getLayer(ROUTE_DASH)) {
          m2.setPaintProperty(ROUTE_DASH, "line-dasharray", dashPatterns[step]);
        }
      }
      dashFrame.current = requestAnimationFrame(animateDash);
    }

    draw();
    // Retry hooks for the add-source path only. Note `idle` is deliberately not
    // used: the dash animation repaints continuously, so the map never goes
    // idle and that event would never fire.
    m.on("styledata", draw);
    m.on("load", draw);
    return () => {
      m.off("styledata", draw);
      m.off("load", draw);
    };
  }, [routeGeometry, pickup, dropoff]);

  // --- keep both endpoints in view -------------------------------------
  useEffect(() => {
    const m = map.current;
    if (!m || !pickup || !dropoff) return;
    const bounds = new maplibregl.LngLatBounds(
      [Math.min(pickup.lon, dropoff.lon), Math.min(pickup.lat, dropoff.lat)],
      [Math.max(pickup.lon, dropoff.lon), Math.max(pickup.lat, dropoff.lat)],
    );
    m.fitBounds(bounds, {
      // Generous left pad: the control panel floats over that side of the map.
      padding: { top: 90, bottom: 90, left: 440, right: 90 },
      maxZoom: 14.5,
      duration: 900,
    });
  }, [pickup, dropoff]);

  // Sized with h/w rather than inset-0: MapLibre sets `position: relative` on
  // its own container, and insets only apply to positioned elements. Explicit
  // dimensions are immune to that.
  return <div ref={container} className="h-full w-full" />;
}
