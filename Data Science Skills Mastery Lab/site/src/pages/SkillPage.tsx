import { Link, useParams } from "react-router-dom";
import { useArtifact, useCatalog } from "../hooks";
import KpiRow from "../components/KpiRow";
import ChartCard from "../components/ChartCard";
import DataTable from "../components/DataTable";
import { PhaseBadge, SourceBadge } from "../components/Badges";

export default function SkillPage() {
  const { name } = useParams();
  const { artifact, error } = useArtifact(name);
  const { catalog } = useCatalog();

  if (error)
    return (
      <div className="loading">
        No artifact for “{name}”. {error}
      </div>
    );
  if (!artifact) return <div className="loading">Loading…</div>;

  const meta = catalog?.skills.find((s) => s.skill === artifact.skill);
  const phaseName = catalog?.phases.find((p) => p.phase === artifact.phase)?.name;
  const siblings = catalog?.skills.filter((s) => s.phase === artifact.phase) ?? [];
  const idx = siblings.findIndex((s) => s.skill === artifact.skill);
  const prev = idx > 0 ? siblings[idx - 1] : null;
  const next = idx >= 0 && idx < siblings.length - 1 ? siblings[idx + 1] : null;

  return (
    <>
      <div className="badge-row" style={{ marginBottom: 12 }}>
        <Link to={`/phase/${artifact.phase}`}>
          <PhaseBadge phase={artifact.phase} name={phaseName} />
        </Link>
        <SourceBadge source={artifact.source} />
        <span className="badge">{artifact.category}</span>
        <span className="badge">{meta ? meta.track_label : artifact.track}</span>
      </div>

      <div className="eyebrow" style={{ fontFamily: "var(--mono)", textTransform: "none", letterSpacing: 0 }}>
        {artifact.skill}
      </div>
      <h1>{artifact.title}</h1>

      <div className="grid two" style={{ margin: "18px 0 26px" }}>
        <div className="card">
          <div className="eyebrow">What the skill prescribes</div>
          <p style={{ margin: 0 }}>{artifact.prescribes}</p>
        </div>
        <div className="card">
          <div className="eyebrow">What this lab ran</div>
          <p style={{ margin: 0 }}>{artifact.applied}</p>
        </div>
      </div>

      <KpiRow kpis={artifact.kpis} />

      <h2>Findings</h2>
      <div className="prose">
        {artifact.narrative.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
        <div className="callout">
          <strong>Takeaway.</strong> {artifact.takeaway}
        </div>
      </div>

      {artifact.charts.length > 0 && (
        <>
          <h2>Charts</h2>
          <div className="grid" style={{ gap: 18 }}>
            {artifact.charts.map((c) => (
              <ChartCard chart={c} key={c.id} />
            ))}
          </div>
        </>
      )}

      {artifact.tables.length > 0 && (
        <>
          <h2>Tables</h2>
          <div className="grid" style={{ gap: 22 }}>
            {artifact.tables.map((t) => (
              <DataTable table={t} key={t.id} />
            ))}
          </div>
        </>
      )}

      <h2>Code · {artifact.code_language}</h2>
      <pre className="code">{artifact.code_excerpt}</pre>

      <h2>Provenance</h2>
      <div className="grid two">
        <div className="card">
          <h3>Skill files executed</h3>
          {artifact.used_skill_scripts.length ? (
            <ul className="small muted" style={{ margin: 0, paddingLeft: 18 }}>
              {artifact.used_skill_scripts.map((s) => (
                <li key={s}>
                  <code className="inline">{s}</code>
                </li>
              ))}
            </ul>
          ) : (
            <p className="small muted" style={{ margin: 0 }}>
              This skill ships guidance rather than code; the demo follows its SKILL.md directly.
            </p>
          )}
        </div>
        <div className="card">
          <h3>Files produced</h3>
          {artifact.artifacts.length ? (
            <ul className="small muted" style={{ margin: 0, paddingLeft: 18 }}>
              {artifact.artifacts.map((s) => (
                <li key={s}>
                  <code className="inline">{s}</code>
                </li>
              ))}
            </ul>
          ) : (
            <p className="small muted" style={{ margin: 0 }}>
              Output is this page&rsquo;s artifact:{" "}
              <code className="inline">site/public/artifacts/{artifact.skill}.json</code>
            </p>
          )}
          <p className="small muted" style={{ marginTop: 12, marginBottom: 0 }}>
            Generated {artifact.generated_at.replace("T", " ")}
          </p>
        </div>
      </div>

      <div className="pager">
        {prev ? <Link to={`/skill/${prev.skill}`}>← {prev.skill}</Link> : <span />}
        {next ? (
          <Link to={`/skill/${next.skill}`}>{next.skill} →</Link>
        ) : (
          <Link to={`/phase/${artifact.phase}`}>Back to phase →</Link>
        )}
      </div>
    </>
  );
}
