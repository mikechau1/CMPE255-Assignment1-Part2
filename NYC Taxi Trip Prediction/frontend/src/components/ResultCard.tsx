import { useState } from "react";
import {
  formatClock,
  formatCurrency,
  formatDistance,
  formatDuration,
} from "../lib/format";
import type { PredictResponse } from "../lib/types";

/** The P10-P90 band, drawn to scale with the point estimate marked. */
function IntervalBar({ p10, p50, p90 }: { p10: number; p50: number; p90: number }) {
  const span = Math.max(p90 - p10, 1);
  const pos = Math.min(Math.max(((p50 - p10) / span) * 100, 0), 100);
  return (
    <div className="mt-3">
      <div className="relative h-2 overflow-hidden rounded-full bg-line">
        <div className="absolute inset-y-0 right-0 left-0 rounded-full bg-gradient-to-r from-good/45 via-accent/60 to-warn/50" />
        <div
          className="absolute top-1/2 h-3.5 w-[3px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-ink shadow"
          style={{ left: `${pos}%` }}
          title="Point estimate"
        />
      </div>
      <div className="mt-1.5 flex justify-between text-[11px] text-faint tnum">
        <span>{formatDuration(p10)}</span>
        <span className="text-dim">80% of trips land in this range</span>
        <span>{formatDuration(p90)}</span>
      </div>
    </div>
  );
}

function FareRow({ label, value, muted }: { label: string; value: number; muted?: boolean }) {
  if (value === 0 && muted) return null;
  return (
    <div className="flex justify-between py-1 text-[12.5px]">
      <span className={muted ? "text-faint" : "text-dim"}>{label}</span>
      <span className="text-ink tnum">{formatCurrency(value)}</span>
    </div>
  );
}

export function ResultCard({ data, stale }: { data: PredictResponse; stale: boolean }) {
  const [showFare, setShowFare] = useState(false);
  const [showWhy, setShowWhy] = useState(false);
  const { duration, fare, contributions } = data;
  const maxContribution = Math.max(...contributions.map((c) => Math.abs(c.contribution_s)), 1);

  return (
    <div className={`transition-opacity duration-200 ${stale ? "opacity-50" : "opacity-100"}`}>
      {/* headline */}
      <div className="flex items-end justify-between gap-3">
        <div>
          <div className="text-[11px] font-medium tracking-wide text-dim uppercase">
            Estimated trip time
          </div>
          <div className="mt-0.5 text-[42px] leading-none font-semibold text-ink tnum">
            {formatDuration(duration.point_s)}
          </div>
        </div>
        <div className="pb-1 text-right">
          <div className="text-[11px] text-faint">Arrive</div>
          <div className="text-lg font-medium text-accent-ink tnum">
            {formatClock(duration.eta)}
          </div>
        </div>
      </div>

      <IntervalBar p10={duration.p10_s} p50={duration.p50_s} p90={duration.p90_s} />

      {/* distance + fare headline */}
      <div className="mt-4 grid grid-cols-2 gap-2">
        <div className="rounded-xl border border-line bg-surface-solid/40 px-3 py-2.5">
          <div className="text-[11px] text-faint">Distance</div>
          <div className="mt-0.5 text-sm text-ink tnum">{formatDistance(data.distance_km)}</div>
          <div className="mt-0.5 text-[10px] text-faint">
            {data.distance_source === "osrm_route" ? "along roads" : "estimated from straight line"}
          </div>
        </div>
        <button
          onClick={() => setShowFare((v) => !v)}
          className="rounded-xl border border-line bg-surface-solid/40 px-3 py-2.5 text-left transition hover:border-accent/40"
        >
          <div className="flex items-center justify-between text-[11px] text-faint">
            <span>Metered fare</span>
            <span className="text-faint">{showFare ? "hide" : "breakdown"}</span>
          </div>
          <div className="mt-0.5 text-sm font-medium text-ink tnum">
            {formatCurrency(fare.total)}
          </div>
          <div className="mt-0.5 text-[10px] text-faint">
            {fare.is_flat_fare ? "JFK flat fare" : "excl. tolls & tip"}
          </div>
        </button>
      </div>

      {showFare && (
        <div className="fade-up mt-2 rounded-xl border border-line bg-surface-solid/40 px-3 py-2">
          <FareRow label={fare.is_flat_fare ? "Flat fare" : "Initial charge"} value={fare.base_fare} />
          <FareRow label="Distance / time charge" value={fare.distance_time_charge} muted />
          <FareRow label="Rush-hour surcharge" value={fare.rush_hour_surcharge} muted />
          <FareRow label="Overnight surcharge" value={fare.overnight_surcharge} muted />
          <FareRow label="Congestion surcharge" value={fare.congestion_surcharge} muted />
          <FareRow label="Congestion Relief Zone fee" value={fare.crz_fee} muted />
          <FareRow label="MTA state tax" value={fare.mta_tax} />
          <FareRow label="Improvement surcharge" value={fare.improvement_surcharge} />
          <div className="mt-1 flex justify-between border-t border-line pt-1.5 text-sm font-semibold">
            <span className="text-ink">Total</span>
            <span className="text-accent-ink tnum">{formatCurrency(fare.total)}</span>
          </div>
          <ul className="mt-2 space-y-0.5">
            {fare.notes.map((n) => (
              <li key={n} className="text-[10.5px] leading-snug text-faint">
                · {n}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* why -- per-prediction SHAP attributions */}
      <button
        onClick={() => setShowWhy((v) => !v)}
        className="mt-3 flex w-full items-center justify-between text-[11px] font-medium tracking-wide text-dim uppercase transition hover:text-ink"
      >
        <span>Why this estimate</span>
        <span className="text-faint normal-case">{showWhy ? "hide" : "show"}</span>
      </button>

      {showWhy && (
        <div className="fade-up mt-2 space-y-1.5">
          {contributions.map((c) => {
            const width = (Math.abs(c.contribution_s) / maxContribution) * 100;
            const positive = c.contribution_s >= 0;
            return (
              <div key={c.feature} className="flex items-center gap-2">
                <div className="w-[46%] truncate text-[11.5px] text-dim" title={c.feature}>
                  {c.label}
                </div>
                <div className="relative h-3 flex-1">
                  <div className="absolute top-0 bottom-0 left-1/2 w-px bg-line" />
                  <div
                    className={`absolute top-0.5 bottom-0.5 rounded-sm ${
                      positive ? "bg-warn/70" : "bg-good/70"
                    }`}
                    style={
                      positive
                        ? { left: "50%", width: `${width / 2}%` }
                        : { right: "50%", width: `${width / 2}%` }
                    }
                  />
                </div>
                <div
                  className={`w-14 text-right text-[11px] tnum ${
                    positive ? "text-warn" : "text-good"
                  }`}
                >
                  {positive ? "+" : "−"}
                  {Math.abs(Math.round(c.contribution_s / 60)) >= 1
                    ? `${Math.abs(Math.round(c.contribution_s / 60))}m`
                    : `${Math.abs(Math.round(c.contribution_s))}s`}
                </div>
              </div>
            );
          })}
          <p className="pt-1 text-[10.5px] leading-snug text-faint">
            Exact SHAP values from the gradient-boosted model, converted to seconds. Orange pushes
            the estimate up, green pulls it down.
          </p>
        </div>
      )}
    </div>
  );
}
