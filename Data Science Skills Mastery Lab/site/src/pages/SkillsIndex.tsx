import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useCatalog } from "../hooks";
import { SourceBadge } from "../components/Badges";

type SourceFilter = "all" | "agent-ml-skills" | "data-analytics-skills";

export default function SkillsIndex() {
  const { catalog } = useCatalog();
  const [q, setQ] = useState("");
  const [source, setSource] = useState<SourceFilter>("all");

  const rows = useMemo(() => {
    if (!catalog) return [];
    const needle = q.trim().toLowerCase();
    return catalog.skills.filter((s) => {
      if (source !== "all" && s.source !== source) return false;
      if (!needle) return true;
      return `${s.skill} ${s.description} ${s.category} ${s.track_label}`.toLowerCase().includes(needle);
    });
  }, [catalog, q, source]);

  if (!catalog) return <div className="loading">Loading…</div>;

  const filters: SourceFilter[] = ["all", "agent-ml-skills", "data-analytics-skills"];

  return (
    <>
      <h1>All {catalog.counts.total} skills</h1>
      <p className="lede">
        Installed under <code className="inline">.claude/skills/</code> in this repository, unmodified.
        Descriptions are read live from each skill&rsquo;s own SKILL.md frontmatter.
      </p>

      <div style={{ display: "flex", gap: 10, margin: "20px 0 18px", flexWrap: "wrap" }}>
        <input
          className="searchbox"
          style={{ flex: "1 1 280px" }}
          placeholder="Search skills, categories, datasets…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        {filters.map((s) => (
          <button
            key={s}
            onClick={() => setSource(s)}
            className="badge"
            style={{
              cursor: "pointer",
              padding: "8px 14px",
              background: source === s ? "var(--bg-raised)" : "transparent",
              borderColor: source === s ? "var(--accent)" : "var(--border)",
              color: source === s ? "var(--text)" : "var(--text-dim)",
            }}
          >
            {s === "all" ? `All (${catalog.counts.total})` : `${s} (${catalog.counts[s]})`}
          </button>
        ))}
      </div>

      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Skill</th>
              <th>Phase</th>
              <th>Dataset</th>
              <th>Source</th>
              <th>What it is for</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.skill}>
                <td>
                  <Link
                    to={`/skill/${s.skill}`}
                    style={{ color: "var(--accent)", fontFamily: "var(--mono)", fontSize: 12.5 }}
                  >
                    {s.skill}
                  </Link>
                </td>
                <td className="small">
                  {s.phase}. {s.phase_name}
                </td>
                <td className="small muted">{s.track_label}</td>
                <td>
                  <SourceBadge source={s.source} />
                </td>
                <td className="small muted">{s.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small muted" style={{ marginTop: 12 }}>
        {rows.length} of {catalog.counts.total} shown.
      </p>
    </>
  );
}
