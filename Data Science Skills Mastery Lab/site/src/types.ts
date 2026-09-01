/** Mirrors pipeline/lib/emit.py -- one shape for every skill artifact. */

export type ValueFormat = "number" | "percent" | "currency" | "compact";

export interface Series {
  key: string;
  label: string;
}

export interface Chart {
  id: string;
  kind:
    | "line"
    | "bar"
    | "hbar"
    | "stacked-bar"
    | "area"
    | "scatter"
    | "heatmap"
    | "funnel"
    | "pie";
  title: string;
  subtitle?: string;
  data: Record<string, string | number | null>[];
  x: string;
  series: Series[];
  xLabel?: string;
  yLabel?: string;
  note?: string;
  valueFormat?: ValueFormat;
  domain?: [number, number] | null;
}

export interface Table {
  id: string;
  title: string;
  columns: string[];
  rows: (string | number | null)[][];
  note?: string;
}

export interface Kpi {
  label: string;
  value: string;
  caption?: string;
  tone?: "neutral" | "good" | "warn" | "bad";
}

export interface SkillArtifact {
  skill: string;
  source: "agent-ml-skills" | "data-analytics-skills";
  category: string;
  phase: number;
  track: string;
  title: string;
  prescribes: string;
  applied: string;
  narrative: string[];
  kpis: Kpi[];
  charts: Chart[];
  tables: Table[];
  code_excerpt: string;
  code_language: string;
  takeaway: string;
  used_skill_scripts: string[];
  artifacts: string[];
  generated_at: string;
}

export interface CatalogSkill {
  skill: string;
  source: SkillArtifact["source"];
  category: string;
  phase: number;
  phase_name: string;
  track: string;
  track_label: string;
  description: string;
  bundled_files: string[];
  installed: boolean;
  has_scripts: boolean;
}

export interface Catalog {
  phases: { phase: number; name: string; blurb: string }[];
  tracks: { id: string; label: string }[];
  skills: CatalogSkill[];
  counts: Record<string, number>;
}
