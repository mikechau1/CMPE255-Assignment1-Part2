import { Link, useParams } from "react-router-dom";
import { useCatalog, useAllArtifacts } from "../hooks";
import KpiRow from "../components/KpiRow";
import { SourceBadge } from "../components/Badges";

export default function PhasePage() {
  const { n } = useParams();
  const phase = Number(n);
  const { catalog } = useCatalog();
  const skills = catalog?.skills.filter((s) => s.phase === phase) ?? [];
  const artifacts = useAllArtifacts(skills.map((s) => s.skill));

  if (!catalog) return <div className="loading">Loading…</div>;
  const meta = catalog.phases.find((p) => p.phase === phase);
  if (!meta) return <div className="loading">No such phase.</div>;

  return (
    <>
      <div className="eyebrow">CRISP-DM phase {phase} of 6</div>
      <h1>{meta.name}</h1>
      <p className="lede">{meta.blurb}</p>

      <h2>{skills.length} skills in this phase</h2>
      <div className="grid" style={{ gap: 18 }}>
        {skills.map((s) => {
          const a = artifacts.find((x) => x.skill === s.skill);
          return (
            <Link className="skill-card" to={`/skill/${s.skill}`} key={s.skill}>
              <div className="badge-row" style={{ marginBottom: 6 }}>
                <span className="name">{s.skill}</span>
                <SourceBadge source={s.source} />
                <span className="badge">{s.track_label}</span>
                {s.has_scripts && <span className="badge">ships scripts</span>}
              </div>
              <h3>{a ? a.title : s.description.slice(0, 90)}</h3>
              <p>{a ? a.takeaway : s.description}</p>
              {a && a.kpis.length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <KpiRow kpis={a.kpis.slice(0, 4)} />
                </div>
              )}
            </Link>
          );
        })}
      </div>

      <div className="pager">
        {phase > 1 ? <Link to={`/phase/${phase - 1}`}>← Phase {phase - 1}</Link> : <span />}
        {phase < 6 ? (
          <Link to={`/phase/${phase + 1}`}>Phase {phase + 1} →</Link>
        ) : (
          <Link to="/skills">All skills →</Link>
        )}
      </div>
    </>
  );
}
