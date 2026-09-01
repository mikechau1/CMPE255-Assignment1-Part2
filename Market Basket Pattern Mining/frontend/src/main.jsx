import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';
import NetworkCart from './NetworkCart.jsx';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const fmt = (value, digits = 2) => Number(value ?? 0).toFixed(digits);
const pages = ['Overview', 'Association Rules', 'Network & Cart', 'Autoresearch Lab', 'Methodology'];

function App() {
  const [page, setPage] = useState('Overview');
  const [summary, setSummary] = useState(null);
  const [rules, setRules] = useState([]);
  const [trials, setTrials] = useState([]);
  const [priceData, setPriceData] = useState({catalog: {}, pricing: {source: 'unavailable'}});
  const [lift, setLift] = useState(1);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  const loadData = async () => {
    const responses = await Promise.all([
      fetch(`${API}/api/summary`),
      fetch(`${API}/api/rules?limit=300`),
      fetch(`${API}/api/trials`),
      fetch(`${API}/api/prices`),
    ]);
    const failed = responses.find(response => !response.ok);
    if (failed) throw new Error(`API request failed (${failed.status})`);
    const [nextSummary, nextRules, nextTrials, nextPrices] = await Promise.all(responses.map(response => response.json()));
    setSummary(nextSummary);
    setRules(nextRules);
    setTrials(nextTrials);
    setPriceData(nextPrices);
  };

  useEffect(() => { loadData().catch(reason => setError(reason.message)); }, []);

  const runExperiment = async () => {
    setRunning(true);
    setError(null);
    try {
      const response = await fetch(`${API}/api/experiments`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({budget: 8}),
      });
      if (!response.ok) throw new Error(`Experiment failed (${response.status})`);
      await loadData();
      setPage('Autoresearch Lab');
    } catch (reason) {
      setError(reason.message);
    } finally {
      setRunning(false);
    }
  };

  if (error && !summary) return <ConnectionError message={error}/>;
  if (!summary) return <main className="loading">Loading BasketLab...</main>;

  const filteredRules = rules.filter(rule => rule.lift >= lift);
  return <div className="shell">
    <aside>
      <div className="brand"><span className="logo">✦</span><div><b>BasketLab</b><small>Pattern intelligence</small></div></div>
      <nav>{pages.map(item => <button type="button" key={item} className={page === item ? 'active' : ''} onClick={() => setPage(item)}>{item}</button>)}</nav>
      <div className="side-foot"><span className="dot"/> Local experiment<br/><small>Dataset v1 · seed 42</small></div>
    </aside>
    <main className="content">
      <header><div><p className="eyebrow">RETAIL ANALYTICS / CRISP-DM</p><h1>{page === 'Overview' ? 'Basket intelligence' : page}</h1><p className="sub">Discover product relationships with transparent, reproducible experiments.</p></div><button type="button" className="run" disabled={running} onClick={runExperiment}>{running ? 'Running...' : '↻ Run experiment'}</button></header>
      {error && <div className="alert">{error}</div>}
      {page === 'Overview' && <Overview summary={summary} rules={filteredRules} trials={trials} lift={lift} setLift={setLift}/>}
      {page === 'Association Rules' && <RulesPage rules={filteredRules} lift={lift} setLift={setLift}/>}
      {page === 'Network & Cart' && <NetworkCart rules={filteredRules} priceData={priceData}/>}
      {page === 'Autoresearch Lab' && <ResearchPage trials={trials} config={summary.best_config}/>}
      {page === 'Methodology' && <MethodologyPage/>}
    </main>
  </div>;
}

function Overview({summary, rules, trials, lift, setLift}) {
  const profile = summary.profile;
  return <><section className="hero-grid"><Kpi label="Transactions" value={profile.transactions.toLocaleString()} note="80/20 deterministic split"/><Kpi label="Unique items" value={profile.unique_items} note="Normalized vocabulary"/><Kpi label="Avg. basket" value={fmt(profile.average_basket_size)} note="Items per transaction"/><Kpi label="Best score" value={fmt(summary.best_score)} note="Autoresearch objective" accent/></section><section className="grid"><RulesPanel rules={rules} lift={lift} setLift={setLift}/><div className="panel"><PanelTitle eyebrow="DATA HEALTH" title="Basket profile"/><ProfileRow label="Sparsity" value={`${fmt(profile.sparsity * 100, 1)}%`} width={profile.sparsity * 100}/><ProfileRow label="Singleton baskets" value={`${fmt(profile.singleton_rate * 100, 1)}%`} width={profile.singleton_rate * 100}/><ProfileRow label="Median basket" value={fmt(profile.median_basket_size, 0)} width={profile.median_basket_size / 6 * 100}/></div><ResearchPanel trials={trials}/><MethodPanel/></section></>;
}

function RulesPage(props) { return <section className="panel"><RulesPanel {...props} standalone/></section>; }
function RulesPanel({rules, lift, setLift, standalone = false}) { const body = <><div className="panel-head"><PanelTitle eyebrow="DISCOVERY" title="Highest-signal rules"/><label>Min lift <input aria-label="Minimum lift" type="number" step=".05" value={lift} onChange={event => setLift(Number(event.target.value))}/></label></div><RuleTable rules={rules}/></>; return standalone ? body : <div className="panel wide">{body}</div>; }
function RuleTable({rules}) { return <div className="table-wrap"><table><thead><tr><th>Association</th><th>Support</th><th>Confidence</th><th>Lift</th><th>Validation</th></tr></thead><tbody>{rules.slice(0, 20).map((rule, index) => <tr key={index}><td><span className="rule-a">{rule.antecedent.join(' + ')}</span><span className="arrow">→</span>{rule.consequent.join(' + ')}</td><td>{fmt(rule.support * 100, 1)}%</td><td>{fmt(rule.confidence * 100, 1)}%</td><td><strong className="lift">{fmt(rule.lift)}</strong></td><td><div className="bar"><i style={{width: `${Math.min(rule.validation_hit_rate * 100, 100)}%`}}/></div>{fmt(rule.validation_hit_rate * 100, 0)}%</td></tr>)}</tbody></table></div>; }

function ResearchPage({trials, config}) { return <section className="grid"><ResearchPanel trials={trials}/><div className="panel"><PanelTitle eyebrow="BEST CONFIGURATION" title="Accepted result"/><ul className="method"><li><b>{config.algorithm}</b><span>Algorithm</span></li><li><b>{config.min_support}</b><span>Minimum support</span></li><li><b>{config.min_confidence}</b><span>Minimum confidence</span></li><li><b>{config.min_lift}</b><span>Minimum lift</span></li></ul></div></section>; }
function ResearchPanel({trials}) { return <div className="panel wide"><div className="panel-head"><PanelTitle eyebrow="AUTORESEARCH" title="Hill-climbing trajectory"/><span className="chip">{trials.filter(trial => trial.accepted).length} accepted moves</span></div><div className="chart">{trials.slice(-12).map(trial => <div className={`column ${trial.accepted ? 'accepted' : ''}`} key={trial.trial} style={{height: `${Math.max(10, trial.score * 190)}px`}}><span>{fmt(trial.score)}</span></div>)}</div><div className="chart-labels"><span>Trial {trials[0]?.trial}</span><span>Trial {trials.at(-1)?.trial}</span></div></div>; }

function MethodologyPage() { return <section className="grid"><div className="panel wide"><PanelTitle eyebrow="CRISP-DM" title="Research workflow"/><div className="method-copy"><p><b>Business understanding</b><br/>Prioritize cross-sell, bundle, and placement opportunities.</p><p><b>Data understanding</b><br/>Profile grocery baskets and normalized items.</p><p><b>Modeling</b><br/>Compare Apriori candidate pruning with FP-Growth pattern-tree mining.</p><p><b>Evaluation</b><br/>Use support, confidence, lift, conviction, coverage, validation hit rate, and runtime.</p><p><b>Deployment</b><br/>Serve versioned experiment artifacts through FastAPI.</p></div></div><div className="panel"><PanelTitle eyebrow="LIMITATIONS" title="Interpret carefully"/><p className="muted">No prices, quantities, timestamps, or customer identity. Association is not causation.</p></div></section>; }
function MethodPanel() { return <div className="panel"><PanelTitle eyebrow="METHOD" title="Research alignment"/><ul className="method"><li><b>Apriori</b><span>Candidate pruning baseline</span></li><li><b>FP-Growth</b><span>Pattern-tree mining</span></li><li><b>Metrics</b><span>Support · confidence · lift</span></li></ul></div>; }

function PanelTitle({eyebrow, title}) { return <div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2></div>; }
function Kpi({label, value, note, accent}) { return <div className={`kpi ${accent ? 'accent' : ''}`}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>; }
function ProfileRow({label, value, width}) { return <div className="profile-row"><div><span>{label}</span><b>{value}</b></div><div className="track"><i style={{width: `${Math.min(width, 100)}%`}}/></div></div>; }
function ConnectionError({message}) { return <main className="loading error"><h2>BasketLab could not connect</h2><p>{message}</p><p>Start the API with <code>uvicorn basketlab.api:app --reload</code>, then refresh.</p></main>; }

createRoot(document.getElementById('root')).render(<App/>);
