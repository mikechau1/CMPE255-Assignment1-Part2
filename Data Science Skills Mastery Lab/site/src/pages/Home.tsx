import { Link } from "react-router-dom";
import { useCatalog, useAllArtifacts } from "../hooks";

const HEADLINES: { skill: string; label: string }[] = [
  { skill: "model-evaluation", label: "ROC-AUC" },
  { skill: "impact-quantification", label: "Net value (test split)" },
  { skill: "rag-pipeline", label: "Best recall@1" },
  { skill: "pytorch-training-loop", label: "Best val accuracy" },
  { skill: "llm-finetuning", label: "Held-out perplexity" },
  { skill: "model-serving", label: "p50 latency" },
];

export default function Home() {
  const { catalog, error } = useCatalog();
  const headline = useAllArtifacts(HEADLINES.map((h) => h.skill));

  if (error) return <div className="loading">Could not load the catalog: {error}</div>;
  if (!catalog) return <div className="loading">Loading…</div>;

  const byPhase = catalog.phases.map((p) => ({
    ...p,
    skills: catalog.skills.filter((s) => s.phase === p.phase),
  }));
  const withScripts = catalog.skills.filter((s) => s.has_scripts).length;

  return (
    <>
      <section className="hero">
        <div>
          <div className="eyebrow">CMPE 255 · Assignment 1 Part 2</div>
          <h1>Forty-six skills, run for real, on Kaggle data</h1>
          <p className="lede">
            Two public Claude Code skill collections were installed into this repository and every one of their
            skills was demonstrated end to end — not described. The work is organised as a single CRISP-DM
            project: a telco churn model from framing to a live scoring API, with retail, Titanic,
            Fashion-MNIST and a text corpus supporting the skills the churn track cannot exercise.
          </p>
          <div className="stat-strip">
            <div className="s">
              <div className="n">{catalog.counts.total}</div>
              <div className="l">skills demonstrated</div>
            </div>
            <div className="s">
              <div className="n">6</div>
              <div className="l">CRISP-DM phases</div>
            </div>
            <div className="s">
              <div className="n">6</div>
              <div className="l">datasets</div>
            </div>
            <div className="s">
              <div className="n">{withScripts}</div>
              <div className="l">skills whose own scripts were executed</div>
            </div>
          </div>
        </div>

        <div className="card">
          <h3>Headline results</h3>
          <p className="small muted" style={{ marginBottom: 14 }}>
            Pulled live from the artifacts the pipeline wrote.
          </p>
          <div style={{ display: "grid", gap: 10 }}>
            {HEADLINES.map((h) => {
              const a = headline.find((x) => x.skill === h.skill);
              const k = a?.kpis.find((x) => x.label === h.label);
              return (
                <Link
                  key={h.skill}
                  to={`/skill/${h.skill}`}
                  style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "baseline" }}
                >
                  <span className="small muted">
                    {h.label} <span style={{ color: "var(--text-faint)" }}>· {h.skill}</span>
                  </span>
                  <strong style={{ fontVariantNumeric: "tabular-nums" }}>{k ? k.value : "…"}</strong>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      <h2>Coverage matrix</h2>
      <p className="muted small" style={{ marginTop: -6 }}>
        Every chip is a skill with a page of executed output.{" "}
        <span className="badge ml">agent-ml-skills ({catalog.counts["agent-ml-skills"]})</span>{" "}
        <span className="badge da">data-analytics-skills ({catalog.counts["data-analytics-skills"]})</span>
      </p>
      <div className="matrix">
        {byPhase.map((p) => (
          <div className="matrix-phase" key={p.phase}>
            <div className="ph-head">
              <span className="n">{p.phase}</span>
              <Link to={`/phase/${p.phase}`}>
                <strong>{p.name}</strong>
              </Link>
              <span className="badge">{p.skills.length} skills</span>
              <span className="blurb">{p.blurb}</span>
            </div>
            <div className="chips">
              {p.skills.map((s) => (
                <Link
                  key={s.skill}
                  to={`/skill/${s.skill}`}
                  className={`chip ${s.source === "agent-ml-skills" ? "ml" : "da"}`}
                  title={s.description}
                >
                  {s.skill}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>

      <h2>How to read this</h2>
      <div className="grid two">
        <div className="card prose">
          <h3>Nothing here is a mock-up</h3>
          <p>
            Each skill page states what the skill prescribes, what this lab actually ran, the numbers that came
            back, and one takeaway. Where a skill ships its own Python — {withScripts} of the 46 do — that code
            was imported and called on the Kaggle data rather than reimplemented.
          </p>
        </div>
        <div className="card prose">
          <h3>Negative results were kept</h3>
          <p>
            Cross-encoder reranking added no accuracy over rank fusion; Bayesian search tied with random search;
            an ONNX export failed. Those are on the site with their numbers, because a demonstration in which
            every technique wins is a brochure.
          </p>
        </div>
      </div>
    </>
  );
}
