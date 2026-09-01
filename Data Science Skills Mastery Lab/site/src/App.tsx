import { NavLink, Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
import PhasePage from "./pages/PhasePage";
import SkillPage from "./pages/SkillPage";
import SkillsIndex from "./pages/SkillsIndex";
import Datasets from "./pages/Datasets";

const PHASES = [
  { n: 1, short: "Business" },
  { n: 2, short: "Data" },
  { n: 3, short: "Prep" },
  { n: 4, short: "Model" },
  { n: 5, short: "Evaluate" },
  { n: 6, short: "Deploy" },
];

export default function App() {
  return (
    <div className="shell">
      <header className="topbar">
        <NavLink to="/" className="brand">
          Data Science Skills Mastery Lab <small>46 skills · CRISP-DM · Kaggle</small>
        </NavLink>
        <nav className="nav">
          {PHASES.map((p) => (
            <NavLink key={p.n} to={`/phase/${p.n}`}>
              {p.n}. {p.short}
            </NavLink>
          ))}
          <NavLink to="/skills">All skills</NavLink>
          <NavLink to="/datasets">Datasets</NavLink>
        </nav>
      </header>

      <main className="page">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/phase/:n" element={<PhasePage />} />
          <Route path="/skill/:name" element={<SkillPage />} />
          <Route path="/skills" element={<SkillsIndex />} />
          <Route path="/datasets" element={<Datasets />} />
          <Route path="*" element={<Home />} />
        </Routes>
      </main>

      <footer className="footer">
        <span>CMPE 255 · Assignment 1 Part 2</span>
        <span>
          Skills: <code className="inline">param087/agent-ml-skills</code> ·{" "}
          <code className="inline">nimrodfisher/data-analytics-skills</code>
        </span>
        <span>Every number on this site was produced by running the pipeline in <code className="inline">pipeline/</code>.</span>
      </footer>
    </div>
  );
}
