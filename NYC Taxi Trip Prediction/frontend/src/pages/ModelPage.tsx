import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { api } from "../lib/api";
import { formatDuration, formatHour, formatNumber, humanizeModel } from "../lib/format";
import type { ModelInfo, ResidualsResponse } from "../lib/types";

const CHART_TOOLTIP = {
  background: "var(--surface-solid)",
  border: "1px solid var(--border)",
  borderRadius: 10,
  fontSize: 12,
  color: "var(--text)",
};

function Panel({
  title,
  subtitle,
  children,
  className = "",
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`glass rounded-2xl p-4 ${className}`}>
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      {subtitle && <p className="mt-0.5 mb-3 text-[11.5px] leading-snug text-dim">{subtitle}</p>}
      {children}
    </section>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface-solid/40 px-3 py-2.5">
      <div className="text-[11px] text-faint">{label}</div>
      <div className="mt-0.5 text-lg font-semibold text-ink tnum">{value}</div>
      {hint && <div className="mt-0.5 text-[10.5px] leading-snug text-faint">{hint}</div>}
    </div>
  );
}

export function ModelPage() {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [residuals, setResiduals] = useState<ResidualsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.model().then(setInfo).catch((e) => setError(String(e.message ?? e)));
    api.residuals().then(setResiduals).catch(() => setResiduals(null));
  }, []);

  if (error) {
    return (
      <div className="mx-auto max-w-2xl p-8">
        <div className="glass rounded-2xl p-6">
          <h2 className="text-sm font-semibold text-warn">No model loaded</h2>
          <p className="mt-2 text-[13px] leading-relaxed text-dim">{error}</p>
        </div>
      </div>
    );
  }
  if (!info) {
    return <div className="p-8 text-sm text-faint">Loading model report…</div>;
  }

  const { metadata: md, metrics } = info;
  const coverage = metrics.interval_coverage;
  const coverageGap = Math.abs(coverage.coverage_pct - coverage.nominal_pct);
  const ranked = [...metrics.leaderboard].sort((a, b) => a.rmsle - b.rmsle);
  const bestRmsle = ranked[0].rmsle;
  const worstRmsle = ranked[ranked.length - 1].rmsle;

  const importance = metrics.feature_importance.slice(0, 12).map((f) => ({
    feature: f.feature.replace(/^speed__/, "").replace(/_/g, " "),
    gain: f.gain,
  }));

  const scatter = (residuals?.points ?? []).map((p) => ({
    actual: p.y_true / 60,
    predicted: p.y_pred / 60,
  }));
  const scatterMax = Math.max(...scatter.map((p) => Math.max(p.actual, p.predicted)), 10);

  return (
    <div className="mx-auto max-w-[1180px] px-5 py-6">
      <header className="mb-5">
        <h1 className="text-xl font-semibold text-ink">Model report</h1>
        <p className="mt-1 text-[13px] text-dim">
          CRISP-DM phases 4 and 5. Every number here is read from the artifact the API is serving —
          version <span className="text-accent-ink tnum">{info.version}</span>, commit{" "}
          <span className="tnum">{md.git_sha}</span>.
        </p>
      </header>

      {/* headline metrics */}
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          label="RMSLE (validation)"
          value={metrics.validation.rmsle.toFixed(4)}
          hint="Competition metric. Lower is better."
        />
        <Stat
          label="Mean absolute error"
          value={formatDuration(metrics.validation.mae_s)}
          hint="Typical miss, in wall-clock time."
        />
        <Stat
          label="R²"
          value={metrics.validation.r2.toFixed(3)}
          hint="Variance explained on raw seconds."
        />
        <Stat
          label="Interval coverage"
          value={`${coverage.coverage_pct.toFixed(1)}%`}
          hint={`Nominal 80%. Median band ${formatDuration(coverage.median_width_s)}.`}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* leaderboard */}
        <Panel
          title="Model ladder"
          subtitle="Each step exists to show the next one earns its place. The production model is the one the API serves."
          className="lg:col-span-2"
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-[12.5px]">
              <thead>
                <tr className="border-b border-line text-left text-[11px] tracking-wide text-faint uppercase">
                  <th className="py-2 pr-3 font-medium">Model</th>
                  <th className="py-2 pr-3 font-medium">What it does</th>
                  <th className="py-2 pr-3 text-right font-medium">RMSLE</th>
                  <th className="py-2 pr-3 text-right font-medium">MAE</th>
                  <th className="py-2 pr-3 text-right font-medium">R²</th>
                  <th className="py-2 text-right font-medium">Train</th>
                </tr>
              </thead>
              <tbody>
                {ranked.map((row) => {
                  const isProd = row.model === metrics.production_model;
                  const share =
                    worstRmsle > bestRmsle
                      ? 1 - (row.rmsle - bestRmsle) / (worstRmsle - bestRmsle)
                      : 1;
                  return (
                    <tr
                      key={row.model}
                      className={`border-b border-line/50 ${isProd ? "bg-accent/8" : ""}`}
                    >
                      <td className="py-2 pr-3">
                        <span className={isProd ? "font-semibold text-accent-ink" : "text-ink"}>
                          {humanizeModel(row.model)}
                        </span>
                        {isProd && (
                          <span className="ml-1.5 rounded border border-accent/40 px-1 py-px text-[9.5px] text-accent-ink">
                            serving
                          </span>
                        )}
                      </td>
                      <td className="max-w-[280px] py-2 pr-3 text-[11.5px] leading-snug text-faint">
                        {row.description}
                      </td>
                      <td className="py-2 pr-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="h-1 w-14 overflow-hidden rounded-full bg-line">
                            <div
                              className="h-full rounded-full bg-accent/70"
                              style={{ width: `${Math.max(share * 100, 3)}%` }}
                            />
                          </div>
                          <span className="text-ink tnum">{row.rmsle.toFixed(4)}</span>
                        </div>
                      </td>
                      <td className="py-2 pr-3 text-right text-dim tnum">
                        {formatDuration(row.mae_s)}
                      </td>
                      <td className="py-2 pr-3 text-right text-dim tnum">{row.r2.toFixed(3)}</td>
                      <td className="py-2 text-right text-faint tnum">{row.train_seconds}s</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>

        {/* predicted vs actual */}
        <Panel
          title="Predicted vs actual"
          subtitle="Validation trips, in minutes. The diagonal is a perfect prediction; spread above it is over-estimation."
        >
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 8, right: 10, bottom: 4, left: -14 }}>
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  dataKey="actual"
                  name="Actual"
                  unit="m"
                  domain={[0, Math.ceil(scatterMax)]}
                  tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="number"
                  dataKey="predicted"
                  name="Predicted"
                  unit="m"
                  domain={[0, Math.ceil(scatterMax)]}
                  tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                  axisLine={false}
                  tickLine={false}
                />
                <ZAxis range={[6, 6]} />
                <Tooltip contentStyle={CHART_TOOLTIP} cursor={{ strokeDasharray: "3 3" }} />
                <Scatter data={scatter} fill="var(--accent)" fillOpacity={0.28} />
                <Scatter
                  data={[
                    { actual: 0, predicted: 0 },
                    { actual: scatterMax, predicted: scatterMax },
                  ]}
                  line={{ stroke: "var(--text-faint)", strokeWidth: 1 }}
                  shape={() => <g />}
                />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        {/* feature importance */}
        <Panel
          title="What the model leans on"
          subtitle="LightGBM split gain, top 12 features."
        >
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={importance}
                layout="vertical"
                margin={{ top: 4, right: 12, bottom: 4, left: 4 }}
              >
                <XAxis type="number" hide />
                <YAxis
                  type="category"
                  dataKey="feature"
                  width={150}
                  tick={{ fontSize: 10, fill: "var(--text-dim)" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={CHART_TOOLTIP}
                  formatter={(v: unknown) => [formatNumber(v as number), "gain"]}
                />
                <Bar dataKey="gain" radius={[0, 4, 4, 0]}>
                  {importance.map((_, i) => (
                    <Cell key={i} fill="var(--accent)" fillOpacity={1 - i * 0.055} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        {/* error by hour */}
        {residuals && (
          <Panel
            title="Error by hour of day"
            subtitle="Mean absolute error across departure hours — where the model struggles."
          >
            <div className="h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={residuals.by_hour}
                  margin={{ top: 4, right: 8, bottom: 4, left: -18 }}
                >
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="hour"
                    tickFormatter={formatHour}
                    ticks={[0, 4, 8, 12, 16, 20]}
                    tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tickFormatter={(v) => `${Math.round(v / 60)}m`}
                    tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={CHART_TOOLTIP}
                    labelFormatter={(h) => `Departing ${formatHour(Number(h))}`}
                    formatter={(v: unknown) => [formatDuration(v as number), "MAE"]}
                  />
                  <Bar dataKey="mae_s" fill="var(--accent)" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>
        )}

        {/* error by distance */}
        {residuals && (
          <Panel
            title="Error by trip length"
            subtitle="Absolute error grows with distance; RMSLE is what keeps that honest."
          >
            <div className="h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={residuals.by_distance}
                  margin={{ top: 4, right: 8, bottom: 4, left: -18 }}
                >
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="bucket"
                    tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tickFormatter={(v) => `${Math.round(v / 60)}m`}
                    tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={CHART_TOOLTIP}
                    formatter={(v: unknown) => [formatDuration(v as number), "MAE"]}
                  />
                  <Bar dataKey="mae_s" fill="var(--good)" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>
        )}

        {/* honesty panels */}
        <Panel
          title="Is the confidence band honest?"
          subtitle="The P10–P90 interval should contain the true duration 80% of the time."
        >
          <div className="flex items-baseline gap-3">
            <span className="text-3xl font-semibold text-ink tnum">
              {coverage.coverage_pct.toFixed(1)}%
            </span>
            <span className="text-[12px] text-faint">actual vs 80% nominal</span>
          </div>
          <div className="relative mt-3 h-2 overflow-hidden rounded-full bg-line">
            <div
              className={`h-full rounded-full ${coverageGap <= 5 ? "bg-good" : "bg-warn"}`}
              style={{ width: `${Math.min(coverage.coverage_pct, 100)}%` }}
            />
            <div
              className="absolute inset-y-0 w-px bg-ink"
              style={{ left: `${coverage.nominal_pct}%` }}
              title="80% nominal"
            />
          </div>
          <p className="mt-2.5 text-[11.5px] leading-snug text-dim">
            {coverageGap <= 5
              ? "Within 5 points of nominal — the band can be read at face value."
              : coverage.coverage_pct < coverage.nominal_pct
                ? "Below nominal: the band is narrower than it should be, so treat it as optimistic."
                : "Above nominal: the band is wider than needed — conservative, not misleading."}
          </p>
        </Panel>

        <Panel
          title="Time split vs random split"
          subtitle="Why the headline number is the more pessimistic one."
        >
          <div className="grid grid-cols-2 gap-3">
            <Stat
              label="Time split (reported)"
              value={metrics.split_comparison.time_split.rmsle.toFixed(4)}
              hint="Validates on trips later than every training trip."
            />
            <Stat
              label="Random split"
              value={metrics.split_comparison.random_split.rmsle.toFixed(4)}
              hint="Shuffles days together."
            />
          </div>
          <p className="mt-2.5 text-[11.5px] leading-snug text-dim">
            {metrics.split_comparison.note}
          </p>
        </Panel>

        {/* provenance */}
        <Panel
          title="Data and provenance"
          subtitle="What this model was trained on."
          className="lg:col-span-2"
        >
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Source" value={md.data_source.toUpperCase()} />
            <Stat
              label="Rows after cleaning"
              value={formatNumber(md.rows_clean)}
              hint={`${md.cleaning_report.pct_kept.toFixed(1)}% of ${formatNumber(md.rows_raw)} kept`}
            />
            <Stat label="Features" value={String(md.features.length)} hint={`${md.n_clusters} spatial clusters`} />
            <Stat label="Boosting rounds" value={formatNumber(md.best_iteration)} hint="chosen by early stopping" />
          </div>

          {md.zone_resolution && (
            <p className="mt-3 rounded-lg border border-warn/30 bg-warn/8 px-3 py-2 text-[11.5px] leading-snug text-dim">
              <strong className="text-warn">Zone resolution.</strong> TLC publishes taxi-zone IDs
              rather than coordinates, so trip endpoints were sampled inside zone polygons.
              Predictions are meaningful at zone level, not address level. Adding Kaggle
              credentials and retraining switches to true coordinates with no code change.
            </p>
          )}

          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[560px] text-[12px]">
              <thead>
                <tr className="border-b border-line text-left text-[11px] tracking-wide text-faint uppercase">
                  <th className="py-2 pr-3 font-medium">Cleaning rule</th>
                  <th className="py-2 pr-3 font-medium">Rationale</th>
                  <th className="py-2 pr-3 text-right font-medium">Removed</th>
                  <th className="py-2 text-right font-medium">Remaining</th>
                </tr>
              </thead>
              <tbody>
                {md.cleaning_report.steps.map((s) => (
                  <tr key={s.rule} className="border-b border-line/50">
                    <td className="py-1.5 pr-3 text-ink">{s.rule}</td>
                    <td className="max-w-[340px] py-1.5 pr-3 text-[11px] leading-snug text-faint">
                      {s.rationale}
                    </td>
                    <td className="py-1.5 pr-3 text-right text-dim tnum">
                      {formatNumber(s.removed)}
                      <span className="ml-1 text-faint">({s.pct_removed.toFixed(2)}%)</span>
                    </td>
                    <td className="py-1.5 text-right text-dim tnum">{formatNumber(s.remaining)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </div>
  );
}
