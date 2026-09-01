import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useCatalog } from "../hooks";

interface DatasetEntry {
  dataset: string;
  kaggle_equivalent?: string;
  source_url?: string;
  local_path?: string;
  bytes?: number;
  rows?: number;
  sha256?: string;
  track?: string;
  status?: string;
}

export default function Datasets() {
  const { catalog } = useCatalog();
  const [manifest, setManifest] = useState<{ retrieved_at: string; note: string; datasets: DatasetEntry[] } | null>(
    null,
  );

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}artifacts/_datasets.json`)
      .then((r) => r.json())
      .then(setManifest)
      .catch(() => setManifest(null));
  }, []);

  if (!catalog) return <div className="loading">Loading…</div>;

  return (
    <>
      <h1>Datasets</h1>
      <p className="lede">
        Public no-auth mirrors of popular Kaggle datasets. Each file is pinned by SHA-256 at download time, so
        every number on this site can be traced to exact bytes.
      </p>

      <h2>Tracks</h2>
      <div className="grid two">
        {catalog.tracks.map((t) => {
          const skills = catalog.skills.filter((s) => s.track === t.id);
          if (!skills.length) return null;
          return (
            <div className="card" key={t.id}>
              <div className="badge-row" style={{ marginBottom: 8 }}>
                <span className="badge phase">{t.id}</span>
                <strong>{t.label}</strong>
              </div>
              <div className="chips" style={{ padding: 0 }}>
                {skills.map((s) => (
                  <Link key={s.skill} className={`chip ${s.source === "agent-ml-skills" ? "ml" : "da"}`} to={`/skill/${s.skill}`}>
                    {s.skill}
                  </Link>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <h2>Download manifest</h2>
      {manifest ? (
        <>
          <p className="small muted">
            {manifest.note} Retrieved {manifest.retrieved_at.replace("T", " ")}.
          </p>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Kaggle equivalent</th>
                  <th>Size</th>
                  <th>SHA-256</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {manifest.datasets.map((d) => (
                  <tr key={d.dataset}>
                    <td className="small">
                      <code className="inline">{d.local_path ?? d.dataset}</code>
                    </td>
                    <td className="small muted">{d.kaggle_equivalent ?? "-"}</td>
                    <td className="num small">{d.bytes ? `${(d.bytes / 1e6).toFixed(2)} MB` : "-"}</td>
                    <td className="small muted" style={{ fontFamily: "var(--mono)", fontSize: 11.5 }}>
                      {d.sha256 ? `${d.sha256.slice(0, 16)}…` : "-"}
                    </td>
                    <td className="small muted" style={{ maxWidth: 340, wordBreak: "break-all" }}>
                      {d.source_url ?? d.status ?? "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p className="small muted">
          Manifest not published to the site. Run <code className="inline">python pipeline/skills_registry.py</code>{" "}
          to copy <code className="inline">data/raw/manifest.json</code> into the site assets.
        </p>
      )}
    </>
  );
}
