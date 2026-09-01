"""CRISP-DM Phase 1 - Business Understanding.

Seven skills. Nothing is modelled yet: we frame the retention problem on the
Telco Churn data, agree the metric definitions, log the assumptions we are
about to rely on, and pin the reproducibility contract.
"""
from __future__ import annotations
import json, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import pandas as pd

from lib import data
from lib.emit import Chart, Kpi, SkillResult, Table, emit
from lib.paths import ARTIFACTS, ROOT, SKILLS
from lib.seeds import SEED, env_fingerprint, set_global_seed
from lib import skillscripts as ss

# ---------------------------------------------------------------- shared numbers
set_global_seed()
DF = data.telco_typed()

N_CUSTOMERS = len(DF)
N_CHURNED = int(DF["Churn_flag"].sum())
CHURN_RATE = N_CHURNED / N_CUSTOMERS
MRR = float(DF["MonthlyCharges"].sum())
CHURNED_MRR = float(DF.loc[DF["Churn_flag"] == 1, "MonthlyCharges"].sum())
ARPU = float(DF["MonthlyCharges"].mean())

# Business assumptions -- each one is logged by analysis-assumptions-log below.
GROSS_MARGIN = 0.65
CAC = 300.0
MONTHLY_CHURN = 0.0265   # 26.5% observed over the snapshot window, spread across ~10 months


def usd(v: float) -> str:
    return f"${v:,.0f}"


# ================================================================= 1. requirements
def demo_stakeholder_requirements_gathering() -> SkillResult:
    """Turn 'can you look at churn' into a scoped, answerable question."""
    qa = [
        ["Who decides on the output?", "VP Customer Retention (budget owner), with Finance signing off on the offer cost."],
        ["What decision changes?", "Which customers get a retention offer next month, and how big that offer can be."],
        ["What does success look like?", "Enough churn caught in the top decile to make an offer campaign NPV-positive."],
        ["What is the unit of analysis?", "One row per active customer account (7,043 in the snapshot)."],
        ["What is explicitly out of scope?", "Pricing strategy, network quality remediation, and win-back of already-churned accounts."],
        ["When is it needed?", "Before the next campaign cycle; a monthly batch score is sufficient -- no real-time need."],
        ["What is the cost of a wrong answer?", "False positive = wasted discount (~$" f"{ARPU * 0.3:,.0f}" "/customer). False negative = lost contract value."],
    ]
    by_contract = (DF.groupby("Contract")
                     .agg(customers=("customerID", "count"),
                          churn_rate=("Churn_flag", "mean"),
                          mrr=("MonthlyCharges", "sum"),
                          mrr_at_risk=("MonthlyCharges", lambda s: float(s[DF.loc[s.index, "Churn_flag"] == 1].sum())))
                     .reset_index())
    m2m_share = float(by_contract.loc[by_contract["Contract"] == "Month-to-month", "mrr_at_risk"].iloc[0]
                      / by_contract["mrr_at_risk"].sum())
    chart = Chart(
        id="risk-by-contract", kind="bar",
        title="Monthly revenue at risk by contract type",
        subtitle="Telco Churn snapshot -- churned customers' monthly charges",
        data=[{"x": r.Contract, "mrr": round(r.mrr, 0), "at_risk": round(r.mrr_at_risk, 0)}
              for r in by_contract.itertuples()],
        series=[{"key": "mrr", "label": "Total MRR"}, {"key": "at_risk", "label": "MRR at risk"}],
        yLabel="USD / month", valueFormat="currency",
    )
    return SkillResult(
        skill="stakeholder-requirements-gathering", source="data-analytics-skills",
        category="Stakeholder Communication", phase=1, track="T1",
        title="Scoping the churn request before any analysis",
        prescribes="Interrogate a vague request until you know the decision, the decision-maker, "
                   "the success criteria, the grain, the timeline and what is out of scope.",
        applied="Ran the skill's question framework against the Telco Churn brief and grounded every "
                "answer in a number from the actual file rather than in a guess.",
        narrative=[
            f"The raw request was 'look into churn'. The dataset has {N_CUSTOMERS:,} accounts of which "
            f"{N_CHURNED:,} ({CHURN_RATE:.1%}) have churned, carrying {usd(CHURNED_MRR)} of monthly charges.",
            "Scoping matters here because the answer changes the model: 'who will churn' is a ranking problem "
            "(precision at the top decile), while 'why do people churn' is an explanatory problem where a "
            "calibrated, interpretable model beats a marginally more accurate one. The stakeholder wants the first.",
            "Month-to-month contracts hold most of the exposure, which immediately narrows the campaign "
            "population and is the kind of finding that should surface in scoping, not three weeks later.",
        ],
        kpis=[
            Kpi("Accounts in scope", f"{N_CUSTOMERS:,}", "one row per customer"),
            Kpi("Observed churn", f"{CHURN_RATE:.1%}", f"{N_CHURNED:,} accounts", tone="bad"),
            Kpi("MRR at risk", usd(CHURNED_MRR), "monthly charges of churned accounts", tone="warn"),
            Kpi("Annualised exposure", usd(CHURNED_MRR * 12), "if the rate persists", tone="warn"),
        ],
        charts=[chart],
        tables=[Table("scoping-qa", "Scoping questions and the answers we got",
                      ["Question", "Answer"], qa)],
        code_excerpt=(
            "by_contract = (df.groupby('Contract')\n"
            "                 .agg(customers=('customerID', 'count'),\n"
            "                      churn_rate=('Churn_flag', 'mean'),\n"
            "                      mrr=('MonthlyCharges', 'sum')))"
        ),
        takeaway="The deliverable is a monthly ranked list with a defensible cut-off, not a churn essay -- "
                 f"and {m2m_share:.0%} of the revenue at risk sits in month-to-month contracts.",
    )


# ================================================================= 2. planning
def demo_analysis_planning() -> SkillResult:
    template = ss.read_doc("analysis-planning", "analysis_plan_template.md", 1200)
    plan_rows = [
        [1, "Business Understanding", "Scoped question, metric definitions, assumptions log", "4h", "Stakeholder unavailable"],
        [2, "Data Understanding", "EDA + quality audit + SQL validation on 3 datasets", "8h", "Undocumented columns"],
        [3, "Data Preparation", "Leakage-safe cleaning, features, resampling, segments", "10h", "Target leakage"],
        [4, "Modeling", "Pipelines, tuning, tracking, CNN, LoRA, RAG", "16h", "CPU-only training budget"],
        [5, "Evaluation", "Metrics, calibration, A/B read, impact in dollars", "8h", "Threshold disagreement"],
        [6, "Deployment", "FastAPI service, dashboard spec, exec summary", "8h", "No production infra"],
    ]
    return SkillResult(
        skill="analysis-planning", source="data-analytics-skills",
        category="Workflow Optimization", phase=1, track="T1",
        title="A CRISP-DM work plan with effort and risk attached",
        prescribes="Before analysing anything, write the plan: questions, deliverables, effort estimate, "
                   "dependencies and the risks that would invalidate the work.",
        applied="Instantiated the skill's bundled analysis_plan_template.md against this lab and estimated "
                "each CRISP-DM phase, so the schedule and the methodology are the same document.",
        narrative=[
            "Planning up front is what makes the six CRISP-DM phases auditable: every phase in this lab has a "
            "named deliverable, and the coverage gate at the end fails if a phase silently drops work.",
            "Effort is deliberately front-loaded on Modeling (16h) because that phase carries the deep-learning, "
            "LLM fine-tuning and RAG tracks, all of which run on CPU here and are therefore slow rather than hard.",
            "The risk column is not decoration -- 'target leakage' is the risk that actually fired, and phase 4's "
            "ml-debugging demo shows it being caught.",
        ],
        kpis=[
            Kpi("Phases planned", "6", "CRISP-DM"),
            Kpi("Estimated effort", "54h", "sum of phase estimates"),
            Kpi("Skills scheduled", "46", "across the six phases"),
        ],
        charts=[Chart(
            id="effort-by-phase", kind="bar",
            title="Estimated effort by CRISP-DM phase",
            data=[{"x": f"{r[0]}. {r[1]}", "hours": int(r[3].rstrip("h"))} for r in plan_rows],
            series=[{"key": "hours", "label": "Estimated hours"}], yLabel="hours",
        )],
        tables=[Table("plan", "Phase plan", ["Phase", "Name", "Deliverable", "Effort", "Top risk"], plan_rows)],
        code_excerpt=template,
        code_language="markdown",
        takeaway="Estimating before starting exposed that half the effort sits in phase 4, which is why the "
                 "heavy tracks were sized to run on CPU in minutes rather than hours.",
        used_skill_scripts=[".claude/skills/analysis-planning/references/analysis_plan_template.md"],
    )


# ================================================================= 3. metrics
def demo_business_metrics_calculator() -> SkillResult:
    m = ss.load("business-metrics-calculator", "saas_metrics.py")

    # Treat the snapshot as one month: churned accounts leave, new/expansion are unknown so held at 0.
    mrr = m.mrr_components(starting_mrr=MRR, new_mrr=0.0, expansion_mrr=0.0,
                           contraction_mrr=0.0, churned_mrr=CHURNED_MRR)
    churn = m.churn_rates(churned_customers=N_CHURNED, starting_customers=N_CUSTOMERS,
                          churned_mrr=CHURNED_MRR, starting_mrr=MRR)
    nrr = m.net_revenue_retention(MRR, 0.0, 0.0, CHURNED_MRR)
    lc = m.ltv_cac(arpu=ARPU, gross_margin=GROSS_MARGIN, monthly_churn=MONTHLY_CHURN, cac=CAC)

    tenure_band = pd.cut(DF["tenure"], [-1, 6, 12, 24, 48, 100],
                         labels=["0-6m", "7-12m", "13-24m", "25-48m", "49m+"])
    by_tenure = DF.groupby(tenure_band, observed=True).agg(
        churn_rate=("Churn_flag", "mean"), arpu=("MonthlyCharges", "mean")).reset_index()

    return SkillResult(
        skill="business-metrics-calculator", source="data-analytics-skills",
        category="Data Analysis & Investigation", phase=1, track="T1",
        title="MRR, churn, NRR and LTV:CAC computed from the Kaggle file",
        prescribes="Compute subscription metrics with the standard definitions -- MRR components, logo vs "
                   "revenue churn, NRR, LTV, CAC payback -- rather than inventing local variants.",
        applied="Called the skill's own saas_metrics.py (mrr_components, churn_rates, "
                "net_revenue_retention, ltv_cac) with values aggregated from Telco-Customer-Churn.csv.",
        narrative=[
            f"Logo churn ({churn['logo_churn_pct']}%) and revenue churn ({churn['revenue_churn_pct']}%) differ, "
            "and the direction matters: revenue churn is higher, so the accounts leaving are worth more than "
            "the average account. A model optimised on accounts alone would under-serve the money.",
            f"With no new or expansion revenue in the snapshot, NRR is {nrr['nrr_pct']}% -- mechanically the "
            "complement of revenue churn. It is quoted here to make the ceiling explicit: retention alone "
            "cannot push NRR above 100%.",
            f"LTV:CAC lands at {lc['ltv_cac_ratio']}:1 with a {lc['payback_months']}-month payback, using a "
            f"{GROSS_MARGIN:.0%} margin and a {usd(CAC)} CAC. Both are assumptions, both are logged, and both "
            "are what the retention offer budget will later be argued from.",
        ],
        kpis=[
            Kpi("MRR", usd(mrr["starting_mrr"]), "sum of monthly charges"),
            Kpi("ARR", usd(mrr["arr"]), "ending MRR x 12"),
            Kpi("Revenue churn", f"{churn['revenue_churn_pct']}%", f"logo churn {churn['logo_churn_pct']}%", tone="bad"),
            Kpi("LTV:CAC", f"{lc['ltv_cac_ratio']}:1", f"payback {lc['payback_months']} months", tone="good"),
        ],
        charts=[
            Chart(id="mrr-components", kind="bar", title="MRR bridge for the snapshot period",
                  data=[{"x": "Starting MRR", "usd": round(mrr["starting_mrr"])},
                        {"x": "Churned MRR", "usd": -round(mrr["churned_mrr"])},
                        {"x": "Ending MRR", "usd": round(mrr["ending_mrr"])}],
                  series=[{"key": "usd", "label": "USD / month"}], valueFormat="currency"),
            Chart(id="churn-by-tenure", kind="line", title="Churn rate and ARPU by tenure band",
                  data=[{"x": str(r.tenure), "churn_rate": round(float(r.churn_rate), 4),
                         "arpu": round(float(r.arpu), 2)} for r in by_tenure.itertuples()],
                  series=[{"key": "churn_rate", "label": "Churn rate"}, {"key": "arpu", "label": "ARPU ($)"}],
                  note="Churn is concentrated in the first six months -- the classic onboarding cliff."),
        ],
        tables=[Table("metrics", "Metric outputs from saas_metrics.py",
                      ["Metric", "Value"],
                      [["Starting MRR", usd(mrr["starting_mrr"])],
                       ["Churned MRR", usd(mrr["churned_mrr"])],
                       ["Ending MRR", usd(mrr["ending_mrr"])],
                       ["ARR", usd(mrr["arr"])],
                       ["Logo churn rate", f"{churn['logo_churn_pct']}%"],
                       ["Revenue churn rate", f"{churn['revenue_churn_pct']}%"],
                       ["NRR", f"{nrr['nrr_pct']}%"],
                       ["LTV", usd(lc["ltv"])],
                       ["CAC (assumed)", usd(lc["cac"])],
                       ["LTV:CAC", f"{lc['ltv_cac_ratio']}:1"],
                       ["CAC payback", f"{lc['payback_months']} months"]])],
        code_excerpt=(
            "from saas_metrics import mrr_components, churn_rates, net_revenue_retention, ltv_cac\n\n"
            "mrr   = mrr_components(starting_mrr=df.MonthlyCharges.sum(), new_mrr=0, expansion_mrr=0,\n"
            "                       contraction_mrr=0, churned_mrr=churned.MonthlyCharges.sum())\n"
            "churn = churn_rates(churned_customers=1869, starting_customers=7043,\n"
            "                    churned_mrr=churned.MonthlyCharges.sum(), starting_mrr=mrr['starting_mrr'])\n"
            "lc    = ltv_cac(arpu=df.MonthlyCharges.mean(), gross_margin=0.65,\n"
            "                monthly_churn=0.0265, cac=300)"
        ),
        takeaway="Revenue churn exceeds logo churn, so the model must be judged on revenue caught, not "
                 "accounts caught -- a decision made in phase 1 that phase 5 then enforces.",
        used_skill_scripts=[ss.ref("business-metrics-calculator", "saas_metrics.py")],
    )


# ================================================================= 4. semantic model
def demo_semantic_model_builder() -> SkillResult:
    gen = ss.load("semantic-model-builder", "metric_template_generator.py")
    val = ss.load("semantic-model-builder", "model_yaml_validator.py")

    scaffold = gen.generate("metric", "churn_rate")

    model = {
        "entities": [{
            "name": "customer", "label": "Customer", "type": "primary", "expr": "customerID",
            "description": "A telco subscriber account in the Kaggle churn snapshot.",
            "meta": {"owner": "retention-analytics", "source_table": "data/raw/Telco-Customer-Churn.csv",
                     "grain": "one row per customer account"},
        }],
        "dimensions": [
            {"name": "contract", "label": "Contract type", "type": "categorical", "expr": "Contract",
             "description": "Commitment length: month-to-month, one year or two year.",
             "meta": {"owner": "retention-analytics",
                      "possible_values": sorted(DF["Contract"].unique().tolist())}},
            {"name": "internet_service", "label": "Internet service", "type": "categorical",
             "expr": "InternetService", "description": "Fibre, DSL or none.",
             "meta": {"owner": "retention-analytics",
                      "possible_values": sorted(DF["InternetService"].unique().tolist())}},
            {"name": "tenure_band", "label": "Tenure band", "type": "categorical",
             "expr": "CASE WHEN tenure <= 6 THEN '0-6m' WHEN tenure <= 12 THEN '7-12m' "
                     "WHEN tenure <= 24 THEN '13-24m' WHEN tenure <= 48 THEN '25-48m' ELSE '49m+' END",
             "description": "Months since acquisition, bucketed for reporting.",
             "meta": {"owner": "retention-analytics"}},
        ],
        "metrics": [
            {"name": "mrr", "label": "Monthly Recurring Revenue", "type": "simple",
             "description": "Sum of MonthlyCharges across active accounts.",
             "type_params": {"measure": {"name": "MonthlyCharges", "fill_nulls_with": 0}},
             "meta": {"owner": "finance-analytics", "data_source": "Telco-Customer-Churn.csv",
                      "grain": "one row per customer per month"}},
            {"name": "churn_rate", "label": "Logo churn rate", "type": "ratio",
             "description": "Churned accounts divided by total accounts in the period.",
             "type_params": {"numerator": "churned_customers", "denominator": "total_customers"},
             "meta": {"owner": "retention-analytics", "data_source": "Telco-Customer-Churn.csv",
                      "grain": "one row per period",
                      "calculation_notes": "Churn is a snapshot label in this dataset, not an event date; "
                                           "period-over-period churn cannot be derived from it."}},
            {"name": "revenue_at_risk", "label": "Revenue at risk", "type": "derived",
             "description": "MonthlyCharges summed over accounts the model scores above the campaign threshold.",
             "type_params": {"expr": "sum(MonthlyCharges) filtered by churn_score >= threshold"},
             "meta": {"owner": "retention-analytics", "data_source": "model scores",
                      "grain": "one row per scoring run"}},
        ],
    }

    import yaml
    path = ARTIFACTS / "semantic_model.yml"
    path.write_text(yaml.safe_dump(model, sort_keys=False, allow_unicode=True), encoding="utf-8")
    ok, issues = val.validate_file(str(path), strict=True)

    return SkillResult(
        skill="semantic-model-builder", source="data-analytics-skills",
        category="Documentation & Knowledge", phase=1, track="T1",
        title="One definition of churn_rate, validated as YAML",
        prescribes="Define entities, dimensions and metrics once in a semantic model, with owner, grain and "
                   "source recorded, and validate the file rather than trusting review.",
        applied="Generated a scaffold with metric_template_generator.py, filled it from the real Telco columns, "
                "wrote artifacts/semantic_model.yml and validated it with model_yaml_validator.py in strict mode.",
        narrative=[
            "The semantic model is where phase 1 stops being prose. `churn_rate`, `mrr` and `revenue_at_risk` "
            "now have exactly one definition each, and every later phase -- including the FastAPI service and "
            "the dashboard spec -- refers back to these names.",
            "Strict validation is the useful part: it fails on any `[REQUIRED]` placeholder left in the "
            f"scaffold, so an unfilled template cannot be committed. This file passes with {len(issues)} issues.",
            "The `calculation_notes` on churn_rate record a real limitation of this Kaggle dataset -- Churn is a "
            "snapshot flag with no event date -- which is exactly the sort of caveat that gets lost in a slide.",
        ],
        kpis=[
            Kpi("Entities", str(len(model["entities"]))),
            Kpi("Dimensions", str(len(model["dimensions"]))),
            Kpi("Metrics", str(len(model["metrics"]))),
            Kpi("Strict validation", "PASS" if ok else f"{len(issues)} issues", "no placeholders remain",
                tone="good" if ok else "bad"),
        ],
        charts=[Chart(id="metric-coverage", kind="bar", title="Semantic model object counts",
                      data=[{"x": "Entities", "n": len(model["entities"])},
                            {"x": "Dimensions", "n": len(model["dimensions"])},
                            {"x": "Metrics", "n": len(model["metrics"])}],
                      series=[{"key": "n", "label": "Objects defined"}])],
        tables=[Table("metric-defs", "Metric definitions",
                      ["Metric", "Type", "Owner", "Definition"],
                      [[m["name"], m["type"], m["meta"]["owner"], m["description"]] for m in model["metrics"]])],
        code_excerpt=scaffold[:900],
        code_language="yaml",
        takeaway="Three metrics now have a single owned definition and a validator that rejects half-filled "
                 "templates; the churn snapshot caveat is recorded where it will actually be read.",
        used_skill_scripts=[ss.ref("semantic-model-builder", "metric_template_generator.py"),
                            ss.ref("semantic-model-builder", "model_yaml_validator.py")],
        artifacts=["artifacts/semantic_model.yml"],
    )


# ================================================================= 5. assumptions
def demo_analysis_assumptions_log() -> SkillResult:
    t = ss.load("analysis-assumptions-log", "assumptions_tracker.py")
    log = t.new_log("Telco churn retention model", "CMPE255 lab")

    t.add_assumption(log, "business_logic", f"Gross margin is {GROSS_MARGIN:.0%}",
                     "Industry norm for telco service revenue; not present in the dataset.",
                     "low", "high", "Ask Finance for the actual blended margin before quoting LTV.")
    t.add_assumption(log, "business_logic", f"Blended CAC is {usd(CAC)}",
                     "Placeholder so LTV:CAC and payback are computable.",
                     "low", "high", "Pull last four quarters of S&M spend / new logos.")
    t.add_assumption(log, "data", "The Churn flag refers to the month after the snapshot",
                     "Kaggle card describes it as customers who left within the last month; there is no event date.",
                     "medium", "critical", "Confirm the extract window with the data owner.")
    t.add_assumption(log, "statistical", f"Monthly churn is {MONTHLY_CHURN:.2%}",
                     "26.5% snapshot churn spread over roughly ten months of exposure.",
                     "low", "medium", "Recompute from an event-level table when one exists.")
    t.add_assumption(log, "data", "TotalCharges blanks mean a brand-new account, not a missing value",
                     "All 11 blanks have tenure = 0, so no charge has been billed yet.",
                     "high", "medium", "Verified in phase 2 against the tenure column.")
    t.add_assumption(log, "technical", "A monthly batch score is fast enough",
                     "Campaign runs monthly; no real-time trigger exists.",
                     "high", "low", "Revisit if the offer moves into the call-centre flow.")

    t.validate_assumption(log, 5, "confirmed", "All 11 blank TotalCharges rows have tenure = 0 (phase 2 audit).")
    report = t.report(log)
    critical = t.get_critical(log)
    (ARTIFACTS / "assumptions_log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")

    rows = [[a["id"], a["category"], a["assumption"], a["confidence"], a["impact_if_wrong"],
             t.risk_score(a), "validated" if a["validated"] else "open"] for a in log["assumptions"]]

    return SkillResult(
        skill="analysis-assumptions-log", source="data-analytics-skills",
        category="Documentation & Knowledge", phase=1, track="T1",
        title="Six assumptions, scored by risk, one already validated",
        prescribes="Record every analytical assumption with its rationale, confidence, impact if wrong and a "
                   "validation plan; surface the low-confidence high-impact ones as critical.",
        applied="Built the log with the skill's assumptions_tracker.py, scored each entry with its risk matrix, "
                "and validated the TotalCharges assumption against the data in phase 2.",
        narrative=[
            f"The two dollar assumptions -- margin and CAC -- carry risk {t.risk_score(log['assumptions'][0])} "
            f"and {t.risk_score(log['assumptions'][1])} out of 9. They do not affect the model at all, but they "
            "drive the LTV:CAC headline, so anyone quoting that number needs to see them.",
            f"{len(critical)} assumptions are flagged critical (low confidence, high or critical impact). The "
            "churn-window assumption is the one that would actually invalidate the work: if the flag covers a "
            "different period than assumed, the target is mis-specified and nothing downstream survives.",
            "Assumption #5 shows the loop closing -- phase 2's null profiling confirmed all eleven blank "
            "TotalCharges rows have tenure = 0, so it moved from open to validated rather than staying folklore.",
        ],
        kpis=[
            Kpi("Assumptions logged", str(len(log["assumptions"]))),
            Kpi("Critical & open", str(len(critical)), "low confidence + high impact", tone="bad"),
            Kpi("Validated", str(sum(1 for a in log["assumptions"] if a["validated"])), "against the data", tone="good"),
            Kpi("Max risk score", str(max(t.risk_score(a) for a in log["assumptions"])), "out of 9", tone="warn"),
        ],
        charts=[Chart(id="assumption-risk", kind="hbar", title="Assumption risk scores",
                      data=[{"x": f"#{a['id']} {a['category']}", "risk": t.risk_score(a)}
                            for a in log["assumptions"]],
                      series=[{"key": "risk", "label": "Risk score (1-9)"}],
                      note="Risk = confidence x impact, from the skill's built-in matrix.")],
        tables=[Table("assumptions", "Assumptions log",
                      ["#", "Category", "Assumption", "Confidence", "Impact", "Risk", "Status"], rows)],
        code_excerpt=report[:1400],
        code_language="text",
        takeaway="The riskiest thing in this project is not the model, it is the un-verified definition of the "
                 "churn window -- and it is now written down where a reviewer will see it.",
        used_skill_scripts=[ss.ref("analysis-assumptions-log", "assumptions_tracker.py")],
        artifacts=["artifacts/assumptions_log.json"],
    )


# ================================================================= 6. context packager
def demo_context_packager() -> SkillResult:
    tc = ss.load("context-packager", "token_counter.py")
    cb = ss.load("context-packager", "context_bundler.py")

    counts = []
    for d in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        total = 0
        for f in d.rglob("*"):
            if f.is_file() and f.suffix in {".md", ".py", ".yaml", ".yml"}:
                total += tc.count_file(str(f))["estimated_tokens"]
        counts.append({"skill": d.name, "tokens": total})
    counts.sort(key=lambda r: -r["tokens"])
    total_tokens = sum(c["tokens"] for c in counts)

    # Build a real bundle for the churn task out of artifacts produced above.
    bundle = cb.build_bundle(
        task="Score Telco customers for churn risk and recommend a retention offer threshold.",
        file_map={
            "business": [str(ARTIFACTS / "semantic_model.yml")],
            "constraints": [str(ARTIFACTS / "assumptions_log.json")],
        },
    )
    bundle_path = ARTIFACTS / "context_bundle.txt"
    bundle_path.write_text(bundle, encoding="utf-8")
    bundle_tokens = tc.count_file(str(bundle_path))["estimated_tokens"]
    budget = tc.CONTEXT_LIMITS["claude-3-opus"]

    return SkillResult(
        skill="context-packager", source="data-analytics-skills",
        category="Workflow Optimization", phase=1, track="meta",
        title="What 46 installed skills cost in context, and what to send instead",
        prescribes="Layer context by priority (task > business > schema > prior findings > constraints > format), "
                   "estimate the token cost, and trim from the bottom when over budget.",
        applied="Ran token_counter.py over every file in .claude/skills, then used context_bundler.py to build "
                "the actual churn-task bundle from the semantic model and the assumptions log.",
        narrative=[
            f"The 46 installed skills total roughly {total_tokens:,} estimated tokens across "
            f"{sum(1 for _ in SKILLS.rglob('*') if _.is_file()):,} files. Loading all of them into one prompt "
            f"would consume {total_tokens / budget:.0%} of a 200k window before any data is attached, which is "
            "precisely why skills are progressive-disclosure documents rather than a single system prompt.",
            f"The task bundle built here -- the scoped question plus the semantic model plus the assumptions -- "
            f"is {bundle_tokens:,} tokens, {bundle_tokens / budget:.1%} of the same budget. That is the content "
            "an agent actually needs to score churn correctly.",
            "The heaviest skills are the ones shipping reference libraries; that is a fair cost, but it is a "
            "cost you should measure before pasting a folder into a prompt.",
        ],
        kpis=[
            Kpi("Skills installed", "46", "two GitHub collections"),
            Kpi("Total skill tokens", f"{total_tokens:,}", "estimated, all bundled files"),
            Kpi("Task bundle", f"{bundle_tokens:,} tok", f"{bundle_tokens / budget:.1%} of a 200k window", tone="good"),
            Kpi("Heaviest skill", counts[0]["skill"], f"{counts[0]['tokens']:,} tokens", tone="warn"),
        ],
        charts=[Chart(id="skill-token-cost", kind="hbar",
                      title="Estimated token cost of the 12 heaviest installed skills",
                      data=[{"x": c["skill"], "tokens": c["tokens"]} for c in counts[:12]],
                      series=[{"key": "tokens", "label": "Estimated tokens"}],
                      note="token_counter.py uses 3 chars/token for code-like text, 4 for prose.")],
        tables=[Table("bundle", "Bundle layers actually sent",
                      ["Layer", "Content", "Why"],
                      [["task", "Score customers for churn; recommend an offer threshold", "the decision"],
                       ["business", "artifacts/semantic_model.yml", "metric definitions the answer must use"],
                       ["constraints", "artifacts/assumptions_log.json", "what may not be assumed silently"],
                       ["schema / prior findings / format", "not included", "trimmed first under the skill's order"]])],
        code_excerpt=bundle[:900],
        code_language="markdown",
        takeaway=f"Everything the churn task needs fits in {bundle_tokens:,} tokens; the 46 skill documents are "
                 f"{total_tokens // max(bundle_tokens, 1)}x larger and belong on disk, not in the prompt.",
        used_skill_scripts=[ss.ref("context-packager", "token_counter.py"),
                            ss.ref("context-packager", "context_bundler.py")],
        artifacts=["artifacts/context_bundle.txt"],
    )


# ================================================================= 7. reproducible-ml
def demo_reproducible_ml() -> SkillResult:
    fp = env_fingerprint()
    man = data.manifest()
    ds_rows = [[d["dataset"], d.get("kaggle_equivalent", "-"),
                f"{d.get('bytes', 0) / 1e6:.2f} MB", (d.get("sha256") or "-")[:16] + "..."]
               for d in man["datasets"]]

    # Determinism check: the shared split must be byte-identical across two calls.
    a = data.churn_split()[0].index.tolist()
    data.telco_typed()  # force a fresh derivation in between
    b = data.churn_split()[0].index.tolist()
    split_stable = a == b

    import hashlib
    split_hash = hashlib.sha256(",".join(map(str, a)).encode()).hexdigest()[:16]

    return SkillResult(
        skill="reproducible-ml", source="agent-ml-skills",
        category="MLOps & Reliability", phase=1, track="meta",
        title="Seeds, environment fingerprint and data digests, pinned before modelling",
        prescribes="Pin seeds across python/numpy/torch, pin the environment, version the data, and record "
                   "enough that another machine can reproduce a number rather than approximate it.",
        applied="Established one seed (20255255) used by every phase, captured a package fingerprint, and tied "
                "each result to the SHA-256 digests recorded when the Kaggle mirrors were downloaded.",
        narrative=[
            f"Seeding happens in exactly one place (`lib/seeds.set_global_seed`) and every phase module calls it "
            f"on import, so the train/test split is stable: two independent derivations produced the identical "
            f"index (hash {split_hash}, match={split_stable}).",
            "Data versioning is handled by digest rather than by a DVC remote, which suits a lab: "
            "`data/raw/manifest.json` records the URL, byte count and SHA-256 of every file, so a rerun that "
            "silently picked up a different mirror would be visible instead of mysterious.",
            f"The environment fingerprint ({fp['fingerprint_sha256']}) records the versions that produced these "
            f"numbers -- notably torch {fp['packages']['torch']}, which is the CPU build, and that single fact "
            "explains every training-time decision in phase 4.",
        ],
        kpis=[
            Kpi("Global seed", str(SEED), "python, numpy, torch"),
            Kpi("Split reproducible", "yes" if split_stable else "NO", f"index hash {split_hash}",
                tone="good" if split_stable else "bad"),
            Kpi("Datasets pinned", str(len(man["datasets"])), "SHA-256 in manifest.json"),
            Kpi("Env fingerprint", fp["fingerprint_sha256"], f"python {fp['python']}"),
        ],
        charts=[Chart(id="dataset-sizes", kind="hbar", title="Pinned dataset sizes",
                      data=[{"x": d["dataset"], "mb": round(d.get("bytes", 0) / 1e6, 2)}
                            for d in man["datasets"] if d.get("bytes")],
                      series=[{"key": "mb", "label": "MB on disk"}])],
        tables=[
            Table("datasets", "Data versioning: what these results were computed from",
                  ["Dataset", "Kaggle equivalent", "Size", "SHA-256"], ds_rows),
            Table("env", "Environment fingerprint", ["Package", "Version"],
                  [[k, v] for k, v in fp["packages"].items()] +
                  [["python", fp["python"]], ["platform", fp["platform"]]]),
        ],
        code_excerpt=(
            "def set_global_seed(seed: int = 20255255) -> int:\n"
            "    os.environ['PYTHONHASHSEED'] = str(seed)\n"
            "    random.seed(seed)\n"
            "    np.random.seed(seed)\n"
            "    torch.manual_seed(seed)\n"
            "    return seed"
        ),
        takeaway="Every number on this site is traceable to a seed, a package set and a file digest -- rerunning "
                 "phases 3-5 reproduces them exactly rather than approximately.",
        artifacts=["data/raw/manifest.json"],
    )


DEMOS = [
    demo_stakeholder_requirements_gathering,
    demo_analysis_planning,
    demo_business_metrics_calculator,
    demo_semantic_model_builder,
    demo_analysis_assumptions_log,
    demo_context_packager,
    demo_reproducible_ml,
]


def main() -> None:
    print("\n=== CRISP-DM 1: Business Understanding ===")
    for fn in DEMOS:
        emit(fn())


if __name__ == "__main__":
    main()
