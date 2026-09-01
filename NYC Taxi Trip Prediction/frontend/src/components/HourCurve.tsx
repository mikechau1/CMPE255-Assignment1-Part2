import {
  Area,
  ComposedChart,
  Line,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatDuration, formatDurationShort, formatHour } from "../lib/format";
import type { CurveResponse } from "../lib/types";

interface Props {
  curve: CurveResponse;
  selectedHour: number;
  onSelectHour: (hour: number) => void;
}

/**
 * Duration across all 24 departure hours for the same trip -- the "leave now
 * or wait?" chart. The band is P10-P90, the line is the point estimate.
 */
export function HourCurve({ curve, selectedHour, onSelectHour }: Props) {
  const data = curve.points.map((p) => ({
    hour: p.hour,
    p50: p.p50_s,
    // Recharts stacks an Area from a [low, high] tuple, which draws the band
    // directly rather than faking it with two overlaid areas.
    band: [p.p10_s, p.p90_s] as [number, number],
  }));

  const selected = data.find((d) => d.hour === selectedHour);
  const best = curve.points[curve.best_hour];
  const worst = curve.points[curve.worst_hour];
  const saving = worst.p50_s - best.p50_s;

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="text-[11px] font-medium tracking-wide text-dim uppercase">
          Departure time
        </h3>
        <span className="text-[11px] text-faint">
          quickest {formatHour(curve.best_hour)} · slowest {formatHour(curve.worst_hour)}
        </span>
      </div>

      <div className="h-[132px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={data}
            margin={{ top: 6, right: 4, bottom: 0, left: -6 }}
            onClick={(e) => {
              const hour = e?.activePayload?.[0]?.payload?.hour;
              if (typeof hour === "number") onSelectHour(hour);
            }}
          >
            <defs>
              <linearGradient id="bandFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.28} />
                <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.06} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="hour"
              tickFormatter={formatHour}
              ticks={[0, 4, 8, 12, 16, 20]}
              tick={{ fontSize: 10, fill: "var(--text-faint)" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tickFormatter={formatDurationShort}
              tick={{ fontSize: 10, fill: "var(--text-faint)" }}
              axisLine={false}
              tickLine={false}
              // Wide enough for an "1h03"-style tick; anything narrower clips
              // the leading hour digit.
              width={46}
            />
            <Tooltip
              cursor={{ stroke: "var(--text-faint)", strokeDasharray: "3 3" }}
              contentStyle={{
                background: "var(--surface-solid)",
                border: "1px solid var(--border)",
                borderRadius: 10,
                fontSize: 12,
                color: "var(--text)",
              }}
              labelFormatter={(h) => `Leaving at ${formatHour(Number(h))}`}
              formatter={(value: unknown, name: string) => {
                if (name === "band" && Array.isArray(value)) {
                  return [
                    `${formatDuration(value[0] as number)} – ${formatDuration(value[1] as number)}`,
                    "80% range",
                  ];
                }
                return [formatDuration(value as number), "Estimate"];
              }}
            />
            <Area
              dataKey="band"
              stroke="none"
              fill="url(#bandFill)"
              isAnimationActive={false}
              activeDot={false}
            />
            <Line
              dataKey="p50"
              stroke="var(--accent)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            {selected && (
              <ReferenceDot
                x={selected.hour}
                y={selected.p50}
                r={4.5}
                fill="var(--accent)"
                stroke="var(--surface-solid)"
                strokeWidth={2}
                isFront
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {saving > 60 && (
        <p className="mt-1 text-[11px] leading-snug text-faint">
          Leaving at {formatHour(curve.best_hour)} instead of {formatHour(curve.worst_hour)} saves
          about <span className="text-good">{formatDuration(saving)}</span>. Click the chart to
          change departure hour.
        </p>
      )}
    </div>
  );
}
