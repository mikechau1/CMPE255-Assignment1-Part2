"""The 46 installed skills, mapped to CRISP-DM phases and dataset tracks.

Single source of truth for the pipeline (which demo runs where) and for the
website (the coverage matrix). Descriptions are read live out of the installed
`SKILL.md` frontmatter so the site never drifts from what is on disk.
"""
from __future__ import annotations
import json, re, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from lib.paths import SKILLS, SITE_ARTIFACTS

ML = "agent-ml-skills"
DA = "data-analytics-skills"

PHASES = {
    1: ("Business Understanding", "Frame the churn/retention problem, agree the metrics, plan the work."),
    2: ("Data Understanding", "Profile, audit and query the raw Kaggle data before touching a model."),
    3: ("Data Preparation", "Clean, engineer, rebalance and segment -- train-only, leakage-checked."),
    4: ("Modeling", "Pipelines, tuning, tracking, deep learning, LLM fine-tuning, RAG -- and a deliberate bug."),
    5: ("Evaluation", "Do the numbers hold up, and are they worth money?"),
    6: ("Deployment", "Serve the model, specify the dashboard, and tell the story to humans."),
}

TRACKS = {
    "T1": "Telco Customer Churn (blastchar/telco-customer-churn)",
    "T1b": "Credit Card Fraud (mlg-ulb/creditcardfraud)",
    "T2": "Online Retail (vijayuv/onlineretail)",
    "T3": "Titanic (c/titanic)",
    "T4": "Fashion-MNIST (zalando-research/fashionmnist)",
    "T5": "Text corpus: the 46 installed SKILL.md files",
    "meta": "The lab itself",
}

# skill -> (source, category, phase, track)
SKILL_MAP: dict[str, tuple[str, str, int, str]] = {
    # ---- Phase 1: Business Understanding
    "stakeholder-requirements-gathering": (DA, "Stakeholder Communication", 1, "T1"),
    "analysis-planning":                  (DA, "Workflow Optimization", 1, "T1"),
    "business-metrics-calculator":        (DA, "Data Analysis & Investigation", 1, "T1"),
    "semantic-model-builder":             (DA, "Documentation & Knowledge", 1, "T1"),
    "analysis-assumptions-log":           (DA, "Documentation & Knowledge", 1, "T1"),
    "context-packager":                   (DA, "Workflow Optimization", 1, "meta"),
    "reproducible-ml":                    (ML, "MLOps & Reliability", 1, "meta"),
    # ---- Phase 2: Data Understanding
    "exploratory-data-analysis":          (ML, "Data Prep & Exploration", 2, "T1"),
    "programmatic-eda":                   (DA, "Data Quality & Validation", 2, "T1"),
    "data-quality-audit":                 (DA, "Data Quality & Validation", 2, "T2"),
    "pandas-patterns":                    (ML, "Data Prep & Exploration", 2, "T2"),
    "query-validation":                   (DA, "Data Quality & Validation", 2, "T2"),
    "sql-to-business-logic":              (DA, "Documentation & Knowledge", 2, "T2"),
    "schema-mapper":                      (DA, "Data Quality & Validation", 2, "T1"),
    "metric-reconciliation":              (DA, "Data Quality & Validation", 2, "T2"),
    "data-catalog-entry":                 (DA, "Documentation & Knowledge", 2, "T1"),
    "time-series-analysis":               (DA, "Data Analysis & Investigation", 2, "T2"),
    # ---- Phase 3: Data Preparation
    "data-cleaning":                      (ML, "Data Prep & Exploration", 3, "T1"),
    "feature-engineering":                (ML, "Data Prep & Exploration", 3, "T1"),
    "imbalanced-data":                    (ML, "Data Prep & Exploration", 3, "T1b"),
    "segmentation-analysis":              (DA, "Data Analysis & Investigation", 3, "T2"),
    "cohort-analysis":                    (DA, "Data Analysis & Investigation", 3, "T2"),
    # ---- Phase 4: Modeling
    "sklearn-pipelines":                  (ML, "Modeling", 4, "T1"),
    "hyperparameter-tuning":              (ML, "Modeling", 4, "T1"),
    "experiment-tracking":                (ML, "MLOps & Reliability", 4, "T1"),
    "ml-debugging":                       (ML, "MLOps & Reliability", 4, "T1"),
    "pytorch-training-loop":              (ML, "Modeling", 4, "T4"),
    "llm-finetuning":                     (ML, "LLMs & GenAI", 4, "T5"),
    "rag-pipeline":                       (ML, "LLMs & GenAI", 4, "T5"),
    # ---- Phase 5: Evaluation
    "model-evaluation":                   (ML, "Modeling", 5, "T1"),
    "ab-test-analysis":                   (DA, "Data Analysis & Investigation", 5, "T1"),
    "root-cause-investigation":           (DA, "Data Analysis & Investigation", 5, "T2"),
    "insight-synthesis":                  (DA, "Data Storytelling & Visualization", 5, "T1"),
    "impact-quantification":              (DA, "Stakeholder Communication", 5, "T1"),
    "analysis-qa-checklist":              (DA, "Stakeholder Communication", 5, "T1"),
    "peer-review-template":               (DA, "Workflow Optimization", 5, "meta"),
    # ---- Phase 6: Deployment
    "model-serving":                      (ML, "MLOps & Reliability", 6, "T1"),
    "funnel-analysis":                    (DA, "Data Analysis & Investigation", 6, "T2"),
    "dashboard-specification":            (DA, "Data Storytelling & Visualization", 6, "T1"),
    "visualization-builder":              (DA, "Data Storytelling & Visualization", 6, "T1"),
    "executive-summary-generator":        (DA, "Data Storytelling & Visualization", 6, "T1"),
    "data-narrative-builder":             (DA, "Data Storytelling & Visualization", 6, "T1"),
    "technical-to-business-translator":   (DA, "Stakeholder Communication", 6, "T1"),
    "methodology-explainer":              (DA, "Stakeholder Communication", 6, "T1"),
    "analysis-documentation":             (DA, "Documentation & Knowledge", 6, "meta"),
    "analysis-retrospective":             (DA, "Workflow Optimization", 6, "meta"),
}


def frontmatter(skill: str) -> dict:
    path = SKILLS / skill / "SKILL.md"
    if not path.exists():
        return {"name": skill, "description": "", "bundled_files": []}
    txt = path.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\n(.*?)\n---", txt, re.S)
    fm = m.group(1) if m else ""
    name = re.search(r"^name:\s*(.+)$", fm, re.M)
    desc = re.search(r"^description:\s*(.+(?:\n\s+.+)*)$", fm, re.M)
    return {
        "name": name.group(1).strip() if name else skill,
        "description": " ".join(desc.group(1).split()) if desc else "",
        "body_chars": len(txt),
        "bundled_files": sorted(p.relative_to(SKILLS / skill).as_posix()
                                for p in (SKILLS / skill).rglob("*") if p.is_file()),
    }


def catalog() -> list[dict]:
    out = []
    for skill, (source, category, phase, track) in SKILL_MAP.items():
        fm = frontmatter(skill)
        out.append({
            "skill": skill, "source": source, "category": category,
            "phase": phase, "phase_name": PHASES[phase][0],
            "track": track, "track_label": TRACKS[track],
            "description": fm["description"], "bundled_files": fm["bundled_files"],
            "installed": (SKILLS / skill / "SKILL.md").exists(),
            "has_scripts": any(f.endswith(".py") for f in fm["bundled_files"]),
        })
    return sorted(out, key=lambda r: (r["phase"], r["skill"]))


def write_catalog() -> pathlib.Path:
    payload = {
        "phases": [{"phase": p, "name": n, "blurb": b} for p, (n, b) in PHASES.items()],
        "tracks": [{"id": k, "label": v} for k, v in TRACKS.items()],
        "skills": catalog(),
        "counts": {
            "total": len(SKILL_MAP),
            ML: sum(1 for v in SKILL_MAP.values() if v[0] == ML),
            DA: sum(1 for v in SKILL_MAP.values() if v[0] == DA),
        },
    }
    out = SITE_ARTIFACTS / "_catalog.json"
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    # The site's Datasets page reads the download manifest, so publish a copy alongside.
    manifest = SKILLS.parents[1] / "data" / "raw" / "manifest.json"
    if manifest.exists():
        (SITE_ARTIFACTS / "_datasets.json").write_text(manifest.read_text(encoding="utf-8"), encoding="utf-8")
    return out


def assert_full_coverage() -> None:
    """Hard gate: every registered skill must be installed AND have an artifact."""
    missing_install = [s for s in SKILL_MAP if not (SKILLS / s / "SKILL.md").exists()]
    on_disk = {p.name for p in SKILLS.iterdir() if p.is_dir()}
    unregistered = sorted(on_disk - set(SKILL_MAP))
    missing_artifact, bad = [], []
    for s in SKILL_MAP:
        f = SITE_ARTIFACTS / f"{s}.json"
        if not f.exists():
            missing_artifact.append(s)
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        if not d.get("narrative") or not d.get("takeaway"):
            bad.append(s)
    problems = []
    if missing_install:
        problems.append(f"not installed: {missing_install}")
    if unregistered:
        problems.append(f"installed but unregistered: {unregistered}")
    if missing_artifact:
        problems.append(f"no artifact ({len(missing_artifact)}): {missing_artifact}")
    if bad:
        problems.append(f"empty artifact: {bad}")
    if problems:
        raise SystemExit("COVERAGE FAILED\n  " + "\n  ".join(problems))
    print(f"COVERAGE OK: {len(SKILL_MAP)}/46 skills installed, demonstrated and serialized.")


if __name__ == "__main__":
    p = write_catalog()
    print(f"wrote {p}")
    for phase, (name, _) in PHASES.items():
        n = sum(1 for v in SKILL_MAP.values() if v[2] == phase)
        print(f"  phase {phase} {name:26s} {n:2d} skills")
    print(f"  total {len(SKILL_MAP)}")
    if "--check" in sys.argv:
        assert_full_coverage()
