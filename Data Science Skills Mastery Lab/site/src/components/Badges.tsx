import type { SkillArtifact } from "../types";

export function SourceBadge({ source }: { source: SkillArtifact["source"] }) {
  const ml = source === "agent-ml-skills";
  return <span className={`badge ${ml ? "ml" : "da"}`}>{ml ? "agent-ml-skills" : "data-analytics-skills"}</span>;
}

export function PhaseBadge({ phase, name }: { phase: number; name?: string }) {
  return (
    <span className="badge phase">
      CRISP-DM {phase}
      {name ? ` · ${name}` : ""}
    </span>
  );
}
