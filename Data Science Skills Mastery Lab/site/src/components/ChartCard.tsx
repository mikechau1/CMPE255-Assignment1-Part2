import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Chart, ValueFormat } from "../types";

const PALETTE = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--c5)", "var(--c6)"];

export function formatValue(v: unknown, fmt: ValueFormat = "number"): string {
  if (v === null || v === undefined || v === "") return "-";
  const n = typeof v === "number" ? v : Number(v);
  if (Number.isNaN(n)) return String(v);
  if (fmt === "percent") return `${(n * 100).toFixed(Math.abs(n) < 0.1 ? 1 : 1)}%`;
  if (fmt === "currency")
    return n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  if (fmt === "compact") return Intl.NumberFormat(undefined, { notation: "compact" }).format(n);
  if (Number.isInteger(n)) return n.toLocaleString();
  return n.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function TooltipBox({ active, payload, label, fmt }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rc-tooltip">
      <div className="t-label">{label}</div>
      {payload.map((p: any) => (
        <div className="t-row" key={p.dataKey ?? p.name}>
          <span style={{ color: p.color }}>{p.name}</span>
          <span>{formatValue(p.value, fmt)}</span>
        </div>
      ))}
    </div>
  );
}

/** Heatmap: rendered as a table rather than a chart library, so labels stay readable. */
function Heatmap({ chart }: { chart: Chart }) {
  const rows = Array.from(new Set(chart.data.map((d) => String(d.row))));
  const cols = Array.from(new Set(chart.data.map((d) => String(d[chart.x] ?? d.col))));
  const key = chart.series[0]?.key ?? "value";
  const values = chart.data.map((d) => Number(d[key])).filter((n) => !Number.isNaN(n));
  const [lo, hi] = chart.domain ?? [Math.min(...values), Math.max(...values)];
  const diverging = lo < 0;

  const cell = (v: number) => {
    if (Number.isNaN(v)) return { background: "transparent", color: "var(--text-faint)" };
    if (diverging) {
      const t = Math.max(-1, Math.min(1, v / Math.max(Math.abs(lo), Math.abs(hi))));
      const color = t >= 0 ? "var(--c2)" : "var(--c1)";
      return {
        background: `color-mix(in srgb, ${color} ${Math.abs(t) * 72}%, var(--bg-sunken))`,
        color: Math.abs(t) > 0.55 ? "#fff" : "var(--text)",
      };
    }
    const t = hi === lo ? 0 : (v - lo) / (hi - lo);
    return {
      background: `color-mix(in srgb, var(--c2) ${t * 82}%, var(--bg-sunken))`,
      color: t > 0.55 ? "#fff" : "var(--text)",
    };
  };

  const lookup = new Map(
    chart.data.map((d) => [`${d.row}|${d[chart.x] ?? d.col}`, Number(d[key])]),
  );

  return (
    <div className="heat">
      <table>
        <thead>
          <tr>
            <th />
            {cols.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r}>
              <th>{r}</th>
              {cols.map((c) => {
                const v = lookup.get(`${r}|${c}`);
                return (
                  <td key={c} style={cell(v as number)}>
                    {v === undefined || Number.isNaN(v) ? "" : formatValue(v, chart.valueFormat)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Funnel({ chart }: { chart: Chart }) {
  const key = chart.series[0]?.key ?? "users";
  const top = Math.max(...chart.data.map((d) => Number(d[key])));
  return (
    <div className="funnel">
      {chart.data.map((d, i) => {
        const v = Number(d[key]);
        return (
          <div className="funnel-row" key={String(d[chart.x]) + i}>
            <div className="muted small">{String(d[chart.x])}</div>
            <div
              className="funnel-bar"
              style={{ width: `${(v / top) * 100}%`, background: PALETTE[i % PALETTE.length] }}
            />
            <div className="num">
              {formatValue(v)} <span className="muted">({((v / top) * 100).toFixed(1)}%)</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function ChartCard({ chart }: { chart: Chart }) {
  const fmt = chart.valueFormat ?? "number";
  const axisProps = { stroke: "var(--border-strong)", tickLine: false, axisLine: false };
  const yTick = (v: number) => formatValue(v, fmt === "currency" ? "compact" : fmt);

  let body: JSX.Element;

  if (chart.kind === "heatmap") {
    body = <Heatmap chart={chart} />;
  } else if (chart.kind === "funnel") {
    body = <Funnel chart={chart} />;
  } else if (chart.kind === "line" || chart.kind === "area") {
    const C = chart.kind === "line" ? LineChart : AreaChart;
    body = (
      <ResponsiveContainer width="100%" height={280}>
        <C data={chart.data} margin={{ top: 6, right: 14, left: 4, bottom: 18 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis
            dataKey={chart.x}
            {...axisProps}
            label={
              chart.xLabel
                ? { value: chart.xLabel, position: "insideBottom", offset: -10, fill: "var(--text-faint)", fontSize: 11 }
                : undefined
            }
          />
          <YAxis {...axisProps} tickFormatter={yTick} domain={chart.domain ?? ["auto", "auto"]} width={62} />
          <Tooltip content={<TooltipBox fmt={fmt} />} />
          {chart.series.length > 1 && <Legend verticalAlign="top" height={28} />}
          {chart.series.map((s, i) =>
            chart.kind === "line" ? (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={PALETTE[i % PALETTE.length]}
                strokeWidth={2}
                dot={chart.data.length <= 20}
                connectNulls
              />
            ) : (
              <Area
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={PALETTE[i % PALETTE.length]}
                fill={PALETTE[i % PALETTE.length]}
                fillOpacity={0.18}
              />
            ),
          )}
        </C>
      </ResponsiveContainer>
    );
  } else if (chart.kind === "scatter") {
    const groups = Array.from(new Set(chart.data.map((d) => String(d.series ?? "series"))));
    body = (
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart margin={{ top: 6, right: 14, left: 4, bottom: 20 }}>
          <CartesianGrid stroke="var(--grid)" />
          <XAxis
            type="number"
            dataKey="x"
            {...axisProps}
            name={chart.xLabel || "x"}
            label={
              chart.xLabel
                ? { value: chart.xLabel, position: "insideBottom", offset: -12, fill: "var(--text-faint)", fontSize: 11 }
                : undefined
            }
          />
          <YAxis type="number" dataKey="y" {...axisProps} name={chart.yLabel || "y"} tickFormatter={yTick} width={62} />
          <Tooltip content={<TooltipBox fmt={fmt} />} cursor={{ strokeDasharray: "3 3" }} />
          {groups.length > 1 && groups.length <= 8 && <Legend verticalAlign="top" height={28} />}
          {groups.map((g, i) => (
            <Scatter
              key={g}
              name={g}
              data={chart.data.filter((d) => String(d.series ?? "series") === g)}
              fill={PALETTE[i % PALETTE.length]}
              fillOpacity={0.7}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    );
  } else if (chart.kind === "pie") {
    const key = chart.series[0]?.key ?? "value";
    body = (
      <ResponsiveContainer width="100%" height={290}>
        <PieChart>
          <Pie data={chart.data} dataKey={key} nameKey={chart.x} outerRadius={100} label>
            {chart.data.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Pie>
          <Tooltip content={<TooltipBox fmt={fmt} />} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    );
  } else {
    const horizontal = chart.kind === "hbar";
    const stacked = chart.kind === "stacked-bar";
    const height = horizontal ? Math.max(240, chart.data.length * 30 + 60) : 290;
    body = (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={chart.data}
          layout={horizontal ? "vertical" : "horizontal"}
          margin={{ top: 6, right: 18, left: horizontal ? 8 : 4, bottom: horizontal ? 8 : 24 }}
        >
          <CartesianGrid stroke="var(--grid)" horizontal={!horizontal} vertical={horizontal} />
          {horizontal ? (
            <>
              <XAxis type="number" {...axisProps} tickFormatter={yTick} domain={chart.domain ?? undefined} />
              <YAxis type="category" dataKey={chart.x} {...axisProps} width={186} interval={0} />
            </>
          ) : (
            <>
              <XAxis
                dataKey={chart.x}
                {...axisProps}
                interval={0}
                angle={chart.data.length > 6 ? -22 : 0}
                textAnchor={chart.data.length > 6 ? "end" : "middle"}
                height={chart.data.length > 6 ? 62 : 34}
              />
              <YAxis {...axisProps} tickFormatter={yTick} domain={chart.domain ?? undefined} width={62} />
            </>
          )}
          <Tooltip content={<TooltipBox fmt={fmt} />} cursor={{ fill: "var(--bg-sunken)" }} />
          {chart.series.length > 1 && <Legend verticalAlign="top" height={28} />}
          {chart.series.map((s, i) => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.label}
              fill={PALETTE[i % PALETTE.length]}
              stackId={stacked ? "a" : undefined}
              radius={horizontal ? [0, 3, 3, 0] : [3, 3, 0, 0]}
              maxBarSize={horizontal ? 22 : 54}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }

  return (
    <div className="chart-card">
      <div className="head">
        <h3>{chart.title}</h3>
        {chart.subtitle && <div className="sub">{chart.subtitle}</div>}
      </div>
      {body}
      {chart.note && <div className="chart-note">{chart.note}</div>}
    </div>
  );
}
