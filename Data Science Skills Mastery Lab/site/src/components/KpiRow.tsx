import type { Kpi } from "../types";

export default function KpiRow({ kpis }: { kpis: Kpi[] }) {
  if (!kpis.length) return null;
  return (
    <div className="kpis">
      {kpis.map((k) => (
        <div className={`kpi ${k.tone ?? "neutral"}`} key={k.label}>
          <div className="label">{k.label}</div>
          <div className="value">{k.value}</div>
          {k.caption && <div className="caption">{k.caption}</div>}
        </div>
      ))}
    </div>
  );
}
