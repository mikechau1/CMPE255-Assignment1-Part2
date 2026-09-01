import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { GeocodeResult, LatLon } from "../lib/types";

interface Props {
  label: string;
  placeholder: string;
  value: string;
  accent: string;
  onSelect: (point: LatLon, label: string) => void;
  onClear: () => void;
}

/** Address search over the Nominatim proxy, debounced and keyboard-navigable. */
export function SearchBox({ label, placeholder, value, accent, onSelect, onClear }: Props) {
  const [query, setQuery] = useState(value);
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(0);
  const box = useRef<HTMLDivElement>(null);
  // Guards against a slow early request landing after a later one.
  const seq = useRef(0);

  useEffect(() => setQuery(value), [value]);

  useEffect(() => {
    if (!open || query.trim().length < 3 || query === value) {
      setResults([]);
      return;
    }
    // Nominatim asks for ~1 req/s; 450 ms of quiet typing is a fair proxy for
    // "the user stopped".
    const id = setTimeout(async () => {
      const mine = ++seq.current;
      setLoading(true);
      try {
        const found = await api.geocode(query);
        if (mine === seq.current) {
          setResults(found);
          setActive(0);
        }
      } catch {
        if (mine === seq.current) setResults([]);
      } finally {
        if (mine === seq.current) setLoading(false);
      }
    }, 450);
    return () => clearTimeout(id);
  }, [query, open, value]);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const choose = (r: GeocodeResult) => {
    onSelect({ lat: r.lat, lon: r.lon }, r.short);
    setQuery(r.short);
    setOpen(false);
    setResults([]);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!results.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => (i + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => (i - 1 + results.length) % results.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(results[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div ref={box} className="relative">
      <label className="mb-1.5 flex items-center gap-2 text-[11px] font-medium tracking-wide text-dim uppercase">
        <span className="h-2 w-2 rounded-full" style={{ background: accent }} />
        {label}
      </label>
      <div className="relative">
        <input
          value={query}
          placeholder={placeholder}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          className="w-full rounded-xl border border-line bg-surface-solid/60 px-3 py-2.5 pr-8 text-sm text-ink outline-none transition placeholder:text-faint focus:border-accent/60 focus:ring-2 focus:ring-accent/20"
        />
        {query && (
          <button
            onClick={() => {
              setQuery("");
              setResults([]);
              onClear();
            }}
            aria-label={`Clear ${label}`}
            className="absolute top-1/2 right-2 -translate-y-1/2 rounded-md px-1.5 py-0.5 text-faint transition hover:bg-line hover:text-ink"
          >
            ×
          </button>
        )}
      </div>

      {open && (loading || results.length > 0) && (
        <div className="glass fade-up absolute top-full right-0 left-0 z-30 mt-1.5 max-h-56 overflow-y-auto rounded-xl p-1">
          {loading && <div className="px-3 py-2 text-xs text-faint">Searching…</div>}
          {results.map((r, i) => (
            <button
              key={`${r.lat},${r.lon},${i}`}
              onMouseEnter={() => setActive(i)}
              onClick={() => choose(r)}
              className={`block w-full rounded-lg px-3 py-2 text-left transition ${
                i === active ? "bg-accent/15" : "hover:bg-line/60"
              }`}
            >
              <div className="truncate text-sm text-ink">{r.short}</div>
              <div className="truncate text-[11px] text-faint">{r.label}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
