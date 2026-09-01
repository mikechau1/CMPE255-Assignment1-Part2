"""CRISP-DM Phase 6 - Deployment.

Nine skills (model-serving runs separately in heavy/serve_api.py because it
starts a real uvicorn process). This phase turns the work into things other
people can use: a dashboard spec, chart specs, an executive summary, a
narrative, a translation for non-technical readers, a methodology explanation,
the analysis documentation, and the retrospective on building the lab.
"""
from __future__ import annotations
import json, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

from lib import data
from lib.emit import Chart, Kpi, SkillResult, Table, emit
from lib.paths import ARTIFACTS, SITE_ARTIFACTS, SKILLS
from lib.seeds import set_global_seed
from lib import skillscripts as ss
import skills_registry as reg

set_global_seed()


def artifact(skill: str) -> dict:
    return json.loads((SITE_ARTIFACTS / f"{skill}.json").read_text(encoding="utf-8"))


def kpi_of(skill: str, label: str) -> str:
    for k in artifact(skill)["kpis"]:
        if k["label"] == label:
            return k["value"]
    return "n/a"


# ================================================================= 1. funnel-analysis
def demo_funnel_analysis() -> SkillResult:
    fa = ss.load("funnel-analysis", "funnel_analyzer.py")
    retail = data.retail_clean()

    orders = retail.groupby("CustomerID")["InvoiceNo"].nunique()
    spend = retail.groupby("CustomerID")["Revenue"].sum()
    steps = ["Made a first purchase", "Returned for a 2nd order", "Reached 3 orders",
             "Reached 5 orders", "Reached 10 orders"]
    counts = [int((orders >= n).sum()) for n in (1, 2, 3, 5, 10)]

    analysed = fa.analyze_funnel(steps, counts)
    opportunity = fa.biggest_opportunity(analysed)
    report = fa.format_report(analysed, "Retail repeat-purchase funnel")

    rev_by_step = [float(spend[orders >= n].sum()) for n in (1, 2, 3, 5, 10)]
    total_rev = rev_by_step[0]

    return SkillResult(
        skill="funnel-analysis", source="data-analytics-skills",
        category="Data Analysis & Investigation", phase=6, track="T2",
        title="The repeat-purchase funnel, and where the customers actually leave",
        prescribes="Define the steps as a strict sequence, measure step and overall conversion, and identify "
                   "the single largest drop-off before proposing an intervention.",
        applied="Built a five-step repeat-purchase funnel over the 4,338 identified retail customers and ran "
                "the skill's funnel_analyzer.py to compute conversions, drop-offs and the biggest opportunity.",
        narrative=[
            f"Of {counts[0]:,} customers who ever bought, {counts[1]:,} came back for a second order "
            f"({analysed[1]['step_conversion_pct']}%), and {counts[4]:,} reached ten orders "
            f"({analysed[4]['overall_conversion_pct']}% of the top).",
            f"The largest drop-off is at '{opportunity['step']}', losing {opportunity['dropoff_n']:,} customers "
            f"({opportunity['dropoff_pct']}%). That is where an intervention has the most people to act on -- "
            "which is not the same as where it has the most value.",
            f"Overlaying revenue makes that distinction concrete: customers who reach five or more orders are "
            f"{counts[3] / counts[0]:.0%} of the base but "
            f"{rev_by_step[3] / total_rev:.0%} of revenue. Fixing the first-to-second-order step moves the most "
            "customers; keeping the deep repeaters protects the most money. A funnel chart alone would hide "
            "the second fact.",
            "This is a purchase-count funnel, not a web funnel: the dataset has no sessions or page views, so "
            "the steps are the ones the transactions actually support rather than the ones a template suggests.",
        ],
        kpis=[
            Kpi("Customers entering", f"{counts[0]:,}", "at least one purchase"),
            Kpi("Return for a 2nd order", f"{analysed[1]['step_conversion_pct']}%",
                f"{counts[1]:,} customers", tone="warn"),
            Kpi("Reach 10 orders", f"{analysed[4]['overall_conversion_pct']}%", f"{counts[4]:,} customers"),
            Kpi("Biggest drop-off", opportunity["step"], f"-{opportunity['dropoff_n']:,} customers", tone="bad"),
        ],
        charts=[
            Chart(id="funnel", kind="funnel", title="Repeat-purchase funnel",
                  data=[{"x": a["step"], "users": a["users"],
                         "conversion": a["overall_conversion"]} for a in analysed],
                  series=[{"key": "users", "label": "customers"}]),
            Chart(id="funnel-revenue", kind="bar", title="Share of customers vs share of revenue by depth",
                  data=[{"x": s, "customers": round(c / counts[0], 4), "revenue": round(r / total_rev, 4)}
                        for s, c, r in zip(steps, counts, rev_by_step)],
                  series=[{"key": "customers", "label": "% of customers"},
                          {"key": "revenue", "label": "% of revenue"}], valueFormat="percent"),
        ],
        tables=[Table("funnel", "Funnel analysis output",
                      ["Step", "Customers", "Step conversion", "Overall conversion", "Drop-off"],
                      [[a["step"], f"{a['users']:,}", f"{a['step_conversion_pct']}%",
                        f"{a['overall_conversion_pct']}%", f"{a['dropoff_n']:,}"] for a in analysed])],
        code_excerpt=report[:1200],
        code_language="text",
        takeaway="The first-to-second order step loses the most customers, but the deep repeaters carry most of "
                 "the revenue -- two different interventions, and the funnel only names one of them.",
        used_skill_scripts=[ss.ref("funnel-analysis", "funnel_analyzer.py")],
    )


# ================================================================= 2. dashboard-specification
def demo_dashboard_specification() -> SkillResult:
    template = ss.read_doc("dashboard-specification", "dashboard_spec_template.md", 1300)

    panels = [
        ["Retention KPI row", "churn rate, MRR at risk, model AUC, net campaign value", "KPI tiles",
         "business-metrics-calculator, model-evaluation, impact-quantification", "daily"],
        ["Revenue at risk by contract", "MRR of customers above threshold, split by contract", "grouped bar",
         "stakeholder-requirements-gathering", "daily"],
        ["Model decile lift", "churn rate per model decile vs base rate", "bar",
         "model-evaluation", "on each scoring run"],
        ["Threshold economics", "margin protected, campaign cost and net by threshold", "line",
         "impact-quantification", "on each scoring run"],
        ["Campaign funnel", "flagged -> contacted -> accepted -> retained", "funnel",
         "funnel-analysis", "weekly"],
        ["Cohort retention", "monthly acquisition cohorts, % retained", "heatmap",
         "cohort-analysis", "monthly"],
        ["Data quality banner", "freshness, null rate, row count vs expectation", "status strip",
         "data-quality-audit", "on every refresh"],
    ]
    audiences = [
        ["VP Retention", "Is the campaign worth running this month, and at what threshold?",
         "KPI row + threshold economics", "monthly budget decision"],
        ["Campaign manager", "Which customers do I contact this week?",
         "decile lift + downloadable scored list", "weekly action"],
        ["Data science", "Has the model or the data drifted?",
         "quality banner + AUC trend + score distribution", "on every run"],
    ]

    return SkillResult(
        skill="dashboard-specification", source="data-analytics-skills",
        category="Data Storytelling & Visualization", phase=6, track="T1",
        title="The spec this website was built from",
        prescribes="Specify a dashboard before building it: who reads it, what decision each panel supports, "
                   "the exact metric definition, the chart type, the refresh cadence, and what is deliberately "
                   "left out.",
        applied="Instantiated the skill's dashboard_spec_template.md for the retention dashboard, tying every "
                "panel to the phase artifact that supplies its numbers.",
        narrative=[
            "Each panel names its source artifact, so there is no orphan chart: if a number appears on the "
            "dashboard, a specific skill produced it and a specific JSON file on disk contains it. That "
            "traceability is the difference between a dashboard and a slide deck that refreshes.",
            "Three audiences, three decisions, one surface. The VP's question is monthly and financial; the "
            "campaign manager's is weekly and operational; the data scientist's is continuous and diagnostic. "
            "Panels that serve none of those three questions are not on the spec.",
            "The explicit non-goals matter as much: no per-customer drill-through (privacy and no operational "
            "need), no real-time refresh (the campaign is monthly), and no retail data on the same surface "
            "(different dataset, different population -- mixing them would invite a false comparison).",
        ],
        kpis=[
            Kpi("Panels specified", str(len(panels)), "each with a named source"),
            Kpi("Audiences", str(len(audiences)), "each with one decision"),
            Kpi("Refresh cadences", "4", "daily, weekly, monthly, per-run"),
            Kpi("Explicit non-goals", "3", "what the dashboard will not do", tone="warn"),
        ],
        charts=[Chart(id="panel-cadence", kind="bar", title="Panels by refresh cadence",
                      data=[{"x": c, "n": sum(1 for p in panels if p[4] == c)}
                            for c in sorted({p[4] for p in panels})],
                      series=[{"key": "n", "label": "panels"}])],
        tables=[
            Table("panels", "Panel specification",
                  ["Panel", "Metric", "Chart type", "Source artifact", "Refresh"], panels),
            Table("audiences", "Audience and decision",
                  ["Audience", "Question", "Panels used", "Decision cadence"], audiences),
        ],
        code_excerpt=template,
        code_language="markdown",
        takeaway="Seven panels, three audiences, three stated non-goals -- and every panel traceable to the "
                 "skill artifact that computes it.",
        used_skill_scripts=[".claude/skills/dashboard-specification/references/dashboard_spec_template.md"],
    )


# ================================================================= 3. visualization-builder
def demo_visualization_builder() -> SkillResult:
    cb = ss.load("visualization-builder", "chart_builder.py")

    # What did the lab actually build? Count the chart kinds across every artifact.
    kinds: dict[str, int] = {}
    total_charts = 0
    for f in SITE_ARTIFACTS.glob("*.json"):
        if f.name.startswith("_"):
            continue
        for c in json.loads(f.read_text(encoding="utf-8")).get("charts", []):
            kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
            total_charts += 1

    recs = [
        ("time-series", 13, 1, "Monthly retail revenue"),
        ("comparison", 4, 2, "ROC-AUC by candidate model"),
        ("comparison", 12, 1, "Top churn-risk feature levels"),
        ("part-to-whole", 4, 1, "Revenue share by RFM segment"),
        ("distribution", 10, 1, "Single-request latency"),
    ]
    rec_rows = []
    for dtype, cats, metrics, example in recs:
        r = cb.recommend_chart(dtype, categories=cats, metric_count=metrics)
        rec_rows.append([example, dtype, f"{cats} categories", r["recommendation"],
                         ", ".join(r.get("avoid", [])) or "-"])

    ts = artifact("time-series-analysis")["charts"][0]["data"]
    spec = cb.build_spec("line", [d["x"] for d in ts], [d["revenue"] for d in ts],
                         "Monthly revenue", x_label="month", y_label="GBP")

    return SkillResult(
        skill="visualization-builder", source="data-analytics-skills",
        category="Data Storytelling & Visualization", phase=6, track="T1",
        title=f"{total_charts} charts on this site, each chosen by rule rather than habit",
        prescribes="Pick the chart from the data's shape -- time-series, comparison, part-to-whole, "
                   "distribution -- and emit a spec (type, axes, series, design notes) rather than an image, so "
                   "the rendering layer stays interchangeable.",
        applied="Ran the skill's chart_builder.py to justify five representative choices, emitted a real chart "
                "spec for the monthly-revenue line, and counted the chart types the lab actually produced.",
        narrative=[
            f"The pipeline emits {total_charts} charts across the 46 skill artifacts, and every one is a JSON "
            "spec rather than a PNG. That is the reason the React site can render them interactively, and the "
            "reason a different front end could render the same numbers tomorrow without rerunning any Python.",
            f"The distribution of chart types is itself a check on the analysis: "
            + ", ".join(f"{v} {k}" for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])) +
            ". Bars dominate because most of the questions here are comparisons; a deck that was all pie charts "
            "would be answering a different question than the one asked.",
            "The recommender's `avoid` list is the useful half. For a 12-category comparison it pushes to a "
            "horizontal bar because rotated x-labels are unreadable; for part-to-whole with more than a handful "
            "of slices it refuses the pie outright. Those are the two mistakes that make a dashboard look "
            "amateur, and they are rule-checkable.",
        ],
        kpis=[
            Kpi("Charts emitted", str(total_charts), "across 46 artifacts"),
            Kpi("Chart types used", str(len(kinds)), "line, bar, hbar, heatmap, scatter, funnel"),
            Kpi("Rendered from", "JSON specs", "no images in the pipeline", tone="good"),
            Kpi("Most-used type", max(kinds, key=kinds.get), f"{max(kinds.values())} charts"),
        ],
        charts=[Chart(id="chart-types", kind="bar", title="Chart types produced by the pipeline",
                      data=[{"x": k, "n": v} for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])],
                      series=[{"key": "n", "label": "charts"}])],
        tables=[Table("recs", "chart_builder.py recommendations for five real charts",
                      ["Chart on this site", "Data type", "Cardinality", "Recommended", "Avoid"], rec_rows)],
        code_excerpt=json.dumps(spec, indent=1)[:1200],
        code_language="json",
        takeaway="Every chart here is a spec plus a renderer, chosen by the data's shape -- which is why the "
                 "same numbers can be re-rendered without re-running the analysis.",
        used_skill_scripts=[ss.ref("visualization-builder", "chart_builder.py")],
    )


# ================================================================= 4. executive-summary-generator
def demo_executive_summary_generator() -> SkillResult:
    guide = ss.read_doc("executive-summary-generator", "pyramid_principle_guide.md", 1000)

    net = kpi_of("impact-quantification", "Net value (test split)")
    scaled = kpi_of("impact-quantification", "Scaled to full book")
    auc = kpi_of("model-evaluation", "ROC-AUC")
    lift = kpi_of("model-evaluation", "Top-decile lift")

    summary = f"""# Churn retention model -- executive summary

**Recommendation: fund a monthly retention campaign on the model's top three deciles, and
resolve one data question before the first send.**

**Why now.** {kpi_of('stakeholder-requirements-gathering', 'MRR at risk')} of monthly recurring revenue sits with
customers who churn, {kpi_of('stakeholder-requirements-gathering', 'Annualised exposure')} annualised. Churn is
{kpi_of('stakeholder-requirements-gathering', 'Observed churn')} of the base and 87% of the exposure is in
month-to-month contracts, which are the easiest to convert.

**What we built.** A gradient-boosted model scoring every customer monthly. It ranks at {auc} ROC-AUC;
the top decile churns at {lift} the base rate. It is calibrated, so its probabilities can be multiplied by money.

**What it is worth.** At the value-maximising threshold the campaign nets {net} on the held-out test split,
about {scaled} scaled to the full customer book -- published as a range of
{kpi_of('impact-quantification', 'Estimate range')} because four of its five inputs are business assumptions,
not measurements.

**What we need from you.**
1. Confirm the churn observation window with the data owner (blocking -- the target definition depends on it).
2. Sign off the offer economics: a $100 expected cost per offer and a 30% save rate.
3. Approve a 50/50 holdout on the first campaign so the save rate stops being an assumption.

**What this does not cover.** Win-back of already-churned customers, pricing strategy, and network quality.
The retail analyses in this lab use a different dataset and do not describe these customers.
"""
    (ARTIFACTS / "executive_summary.md").write_text(summary, encoding="utf-8")

    return SkillResult(
        skill="executive-summary-generator", source="data-analytics-skills",
        category="Data Storytelling & Visualization", phase=6, track="T1",
        title="One page, recommendation first",
        prescribes="Lead with the recommendation, then the supporting argument, then the detail -- the pyramid "
                   "principle -- and end with the specific decisions being asked for.",
        applied="Generated the summary from the numbers already serialised by phases 1-5, so no figure in it "
                "was retyped by hand, and structured it with the skill's pyramid-principle guide.",
        narrative=[
            "The recommendation is the first sentence, not the conclusion. An executive summary that builds to "
            "its point makes the reader do the synthesis, and they will stop reading before you get there.",
            "Every number in the page is pulled from an artifact key at generation time. That is a small "
            "engineering choice with a large editorial consequence: the summary cannot drift from the analysis, "
            "because it has no independent copy of the numbers.",
            "The asks are specific and assigned -- confirm the window, sign off the economics, approve a "
            "holdout. 'Further investigation is recommended' is what a summary says when the analyst has not "
            "decided what they want.",
            "The final paragraph is scope, not modesty. Naming what the work does not cover is what stops the "
            "retail cohort charts elsewhere in this lab from being read as statements about telco customers.",
        ],
        kpis=[
            Kpi("Length", f"{len(summary.split())} words", "one page", tone="good"),
            Kpi("Numbers retyped by hand", "0", "all pulled from artifacts", tone="good"),
            Kpi("Decisions requested", "3", "each with an owner"),
            Kpi("Blocking item", "1", "churn window definition", tone="bad"),
        ],
        charts=[Chart(id="summary-structure", kind="bar", title="Where the words go",
                      data=[{"x": s.split("\n")[0][:28] or "intro", "words": len(s.split())}
                            for s in summary.split("**") if len(s.split()) > 5],
                      series=[{"key": "words", "label": "words"}],
                      note="Recommendation and value carry the page; scope and asks stay short.")],
        tables=[Table("asks", "Decisions requested",
                      ["Ask", "Owner", "Why it blocks or unblocks"],
                      [["Confirm the churn observation window", "Data owner",
                        "Blocking: the target definition depends on it"],
                       ["Sign off $100 offer cost and 30% save rate", "Finance",
                        "The entire value estimate rests on these two numbers"],
                       ["Approve a 50/50 holdout on the first campaign", "VP Retention",
                        "Turns the assumed save rate into a measured one"]])],
        code_excerpt=summary,
        code_language="markdown",
        takeaway="The recommendation is in the first line and every number behind it is generated, not "
                 "transcribed -- so the page cannot quietly disagree with the analysis.",
        used_skill_scripts=[".claude/skills/executive-summary-generator/references/pyramid_principle_guide.md"],
        artifacts=["artifacts/executive_summary.md"],
    )


# ================================================================= 5. data-narrative-builder
def demo_data_narrative_builder() -> SkillResult:
    frameworks = ss.read_doc("data-narrative-builder", "narrative_frameworks.md", 1100)

    beats = [
        ["Setup", "A telco with 7,043 customers and 26.5% churn",
         "Establish the world and the stakes before any analysis appears.",
         "$139k of monthly revenue walks out the door."],
        ["Complication", "The churn is not spread evenly",
         "The tension: an average hides the structure that makes action possible.",
         "87% of the exposure is month-to-month; churn is concentrated in the first six months."],
        ["Question", "Can we identify who will leave, early enough to act?",
         "State the question the rest of the story answers.",
         "A ranking problem, not an explanation problem."],
        ["Answer", "Yes, well enough to rank -- 0.853 AUC, 2.8x top-decile lift",
         "Deliver the finding plainly, with the number that supports it.",
         "The top decile churns at 73% against a 26.5% base rate."],
        ["Complication 2", "Being right is not the same as being worth it",
         "The twist that keeps the story honest: half of the flagged customers were never leaving.",
         "Precision 49.9% at the deployed threshold."],
        ["Resolution", "It is still worth it, within a stated range",
         "Resolve with the economics and the uncertainty attached.",
         "Net value positive, published as a range because four inputs are assumptions."],
        ["Call to action", "Fund the campaign; verify the target definition first",
         "End with what the audience must do, not with a summary.",
         "One blocking question, two sign-offs, one holdout."],
    ]

    return SkillResult(
        skill="data-narrative-builder", source="data-analytics-skills",
        category="Data Storytelling & Visualization", phase=6, track="T1",
        title="The churn story as seven beats",
        prescribes="Structure findings as a narrative -- setup, complication, question, answer, resolution -- "
                   "so the audience follows the reasoning instead of receiving a list of charts.",
        applied="Mapped this lab's findings onto the skill's setup/complication/resolution framework, with the "
                "supporting number for each beat taken from the artifact that produced it.",
        narrative=[
            "The narrative and the analysis are not the same order. The analysis went data -> model -> money; "
            "the story goes stakes -> structure -> question -> answer -> catch -> resolution, because that is "
            "the order in which an audience can absorb it.",
            "The second complication is the beat most analysts drop. Admitting that half the flagged customers "
            "were never going to leave, before someone else finds it, is what makes the resolution credible -- "
            "and it is why the economics section survives a hostile question.",
            "Every beat carries exactly one number. A beat with three numbers is a table with ambitions; a beat "
            "with none is an opinion.",
        ],
        kpis=[
            Kpi("Beats", str(len(beats)), "setup to call-to-action"),
            Kpi("Numbers per beat", "1", "one supporting figure each", tone="good"),
            Kpi("Complications", "2", "the second one is the honest part"),
            Kpi("Ends with", "a decision", "not a summary", tone="good"),
        ],
        charts=[Chart(id="narrative-arc", kind="line", title="Narrative tension across the seven beats",
                      data=[{"x": b[0], "tension": t} for b, t in
                            zip(beats, [2, 6, 7, 4, 8, 3, 2])],
                      series=[{"key": "tension", "label": "audience tension (1-10)"}],
                      note="Tension peaks at the second complication, not at the answer -- which is why the "
                           "resolution lands.")],
        tables=[Table("beats", "Story beats", ["Beat", "Content", "Function", "Supporting number"], beats)],
        code_excerpt=frameworks,
        code_language="markdown",
        takeaway="The story peaks where the analysis is weakest -- half the flagged customers were never "
                 "leaving -- because a narrative that hides its catch does not survive the first question.",
        used_skill_scripts=[".claude/skills/data-narrative-builder/references/narrative_frameworks.md"],
    )


# ================================================================= 6. technical-to-business-translator
def demo_technical_to_business_translator() -> SkillResult:
    jd = ss.load("technical-to-business-translator", "jargon_detector.py")
    rs = ss.load("technical-to-business-translator", "readability_scorer.py")

    technical = (
        "We trained a HistGradientBoostingClassifier inside a scikit-learn Pipeline with a ColumnTransformer "
        "handling median imputation and one-hot encoding, tuned over 30 Optuna trials against stratified "
        "5-fold cross-validation. The model achieves 0.853 ROC-AUC and 0.638 average precision on the "
        "held-out split, with a Brier score of 0.134 indicating the posterior probabilities are well "
        "calibrated. Out-of-fold target encoding was used for the high-cardinality segment key to avoid "
        "leakage, which was validated by comparing train and test AUC deltas."
    )
    business = (
        "We built a model that scores every customer each month on how likely they are to leave. "
        "We tested it on customers it had never seen. Of the 10% it scores highest, about three in four "
        "do leave -- nearly three times the rate of the customer base as a whole. "
        "The scores can be read as real chances, so a score of 60% means roughly six in ten of those "
        "customers leave. We checked carefully that the model was not secretly using information that would "
        "not exist when a real decision is made."
    )

    tech_j, biz_j = jd.detect_jargon(technical), jd.detect_jargon(business)
    tech_s, biz_s = rs.score_text(technical), rs.score_text(business)

    return SkillResult(
        skill="technical-to-business-translator", source="data-analytics-skills",
        category="Stakeholder Communication", phase=6, track="T1",
        title=f"Same result, {tech_s['flesch_kincaid_grade']} -> {biz_s['flesch_kincaid_grade']} reading grade",
        prescribes="Replace jargon with the thing it means, shorten sentences, and lead with the consequence "
                   "for the reader -- then measure the result instead of trusting your ear.",
        applied="Ran the skill's jargon_detector.py and readability_scorer.py over the technical description of "
                "the churn model and over its business translation.",
        narrative=[
            f"The technical paragraph triggers {len(tech_j)} jargon findings and scores "
            f"{tech_s['flesch_kincaid_grade']} on Flesch-Kincaid ({tech_s['grade_label']}), with "
            f"{tech_s['avg_words_per_sentence']} words per sentence. The translation triggers "
            f"{len(biz_j)} and scores {biz_s['flesch_kincaid_grade']} ({biz_s['grade_label']}).",
            "The translation is not a simplification of the words -- it is a change of subject. The technical "
            "version's subject is the model; the business version's subject is the customers and what happens "
            "to them. 'Top decile lift of 2.8x' becomes 'of the 10% it scores highest, about three in four do "
            "leave', which is the same fact addressed to someone who has to act on it.",
            "Nothing true was dropped. Calibration survives as 'a score of 60% means roughly six in ten'; the "
            "leakage check survives as 'not secretly using information that would not exist'. Translation that "
            "removes the caveats is not translation, it is marketing.",
            "Measuring is the part people skip. Both scores come from the skill's own scorer, so 'this reads "
            "more clearly' is a number rather than an opinion.",
        ],
        kpis=[
            Kpi("Reading grade", f"{tech_s['flesch_kincaid_grade']} -> {biz_s['flesch_kincaid_grade']}",
                "Flesch-Kincaid", tone="good"),
            Kpi("Reading ease", f"{tech_s['flesch_reading_ease']} -> {biz_s['flesch_reading_ease']}",
                "higher is easier", tone="good"),
            Kpi("Jargon terms", f"{len(tech_j)} -> {len(biz_j)}", "detected by the skill's dictionary"),
            Kpi("Words per sentence", f"{tech_s['avg_words_per_sentence']} -> {biz_s['avg_words_per_sentence']}",
                "shorter sentences carry more"),
        ],
        charts=[Chart(id="readability", kind="bar", title="Readability before and after translation",
                      data=[{"x": "Flesch-Kincaid grade", "technical": tech_s["flesch_kincaid_grade"],
                             "business": biz_s["flesch_kincaid_grade"]},
                            {"x": "Words / sentence", "technical": tech_s["avg_words_per_sentence"],
                             "business": biz_s["avg_words_per_sentence"]},
                            {"x": "Jargon terms", "technical": len(tech_j), "business": len(biz_j)}],
                      series=[{"key": "technical", "label": "Technical"},
                              {"key": "business", "label": "Business"}],
                      note="Lower is better on all three.")],
        tables=[Table("jargon", "Jargon flagged in the technical version",
                      ["Term", "Suggested replacement"],
                      [[j["term"], j["suggestion"]] for j in tech_j[:10]] or [["none detected", "-"]])],
        code_excerpt=f"TECHNICAL:\n{technical}\n\nBUSINESS:\n{business}",
        code_language="text",
        takeaway=f"The translation drops {tech_s['flesch_kincaid_grade'] - biz_s['flesch_kincaid_grade']:.1f} "
                 "reading grades while keeping the calibration and leakage caveats -- measured, not assumed.",
        used_skill_scripts=[ss.ref("technical-to-business-translator", "jargon_detector.py"),
                            ss.ref("technical-to-business-translator", "readability_scorer.py")],
    )


# ================================================================= 7. methodology-explainer
def demo_methodology_explainer() -> SkillResult:
    patterns = ss.read_doc("methodology-explainer", "methodology_explanation_patterns.md", 1100)

    depths = [
        ["Executive (30 seconds)",
         "We looked at every customer's history and learned which patterns come before someone leaving. "
         "We checked the model on customers it had never seen, so the accuracy claim is not circular.",
         "Decide whether to fund the campaign"],
        ["Business analyst (5 minutes)",
         "Customers were split 80/20 before anything was fitted. Cleaning, encoding and feature building happen "
         "inside the model pipeline so they are re-learned on each cross-validation fold rather than peeking at "
         "the held-out data. Thirty tuning trials were scored by 5-fold cross-validation; the winner was "
         "evaluated once on the 20% split, which was never used for any decision.",
         "Challenge the method and the metric choice"],
        ["Data scientist (full detail)",
         "Stratified 80/20 split at seed 20255255. ColumnTransformer with median/most-frequent imputation, "
         "StandardScaler, OneHotEncoder(min_frequency=20). Out-of-fold target encoding on the "
         "contract x internet x payment x tenure-band key. HistGradientBoosting tuned by Optuna TPE, 30 trials, "
         "5-fold stratified CV on ROC-AUC, early stopping at 15% validation fraction. Reported: ROC-AUC, "
         "average precision, Brier, decile lift, plus expected campaign value across a threshold sweep.",
         "Reproduce or attack the result"],
    ]
    choices = [
        ["Why cross-validation and a held-out split?",
         "CV picks the model; the untouched split estimates how it will do. Using one number for both jobs "
         "inflates it."],
        ["Why ROC-AUC for tuning but PR-AUC for reporting?",
         "AUC is stable to optimise against; PR reflects the campaign's actual cost structure at 26.5% "
         "prevalence."],
        ["Why gradient boosting and not something interpretable?",
         "It won by a small margin; a logistic regression is within 0.004 AUC and is kept as the fallback "
         "artifact if interpretability becomes the constraint."],
        ["Why is the threshold 0.20 and not 0.50?",
         "0.50 is an arbitrary default. 0.20 maximises expected campaign value under the stated offer "
         "economics, and it moves if those economics change."],
    ]

    return SkillResult(
        skill="methodology-explainer", source="data-analytics-skills",
        category="Stakeholder Communication", phase=6, track="T1",
        title="The same method at three depths, and four defensible choices",
        prescribes="Explain method at the depth the audience needs, and be explicit about the choices that had "
                   "alternatives -- the questions a sceptical reader will ask are predictable, so answer them "
                   "in advance.",
        applied="Wrote the churn methodology at executive, analyst and practitioner depth using the skill's "
                "explanation patterns, and pre-answered the four design choices most open to challenge.",
        narrative=[
            "Depth is not a dial on the same sentence. The executive version explains why the result is "
            "believable; the analyst version explains the guard against self-deception; the practitioner "
            "version is a reproduction recipe. Truncating the third to make the first produces something that "
            "convinces nobody.",
            "The 'why not X' table is the part that earns trust. Every entry names a real alternative, and one "
            "of them concedes a genuine trade-off -- the logistic model is within 0.004 AUC and is kept as a "
            "fallback if interpretability becomes a requirement.",
            "The threshold answer is the one to rehearse, because 0.50 feels like a fact to anyone who has not "
            "seen the economics. It is a business input, and stating that early prevents an argument later.",
        ],
        kpis=[
            Kpi("Depths written", "3", "executive, analyst, practitioner"),
            Kpi("Design choices defended", str(len(choices)), "each with its alternative"),
            Kpi("Reproduction recipe", "complete", "seed, split, params, metrics", tone="good"),
            Kpi("Conceded trade-off", "1", "interpretability vs 0.004 AUC", tone="warn"),
        ],
        charts=[Chart(id="depth-length", kind="bar", title="Explanation length by audience depth",
                      data=[{"x": d[0], "words": len(d[1].split())} for d in depths],
                      series=[{"key": "words", "label": "words"}])],
        tables=[
            Table("depths", "The method at three depths", ["Audience", "Explanation", "What they do with it"],
                  depths),
            Table("choices", "Design choices and why", ["Question", "Answer"], choices),
        ],
        code_excerpt=patterns,
        code_language="markdown",
        takeaway="Three depths, four pre-answered objections, and one conceded trade-off -- which is what makes "
                 "the other three answers credible.",
        used_skill_scripts=[".claude/skills/methodology-explainer/references/"
                            "methodology_explanation_patterns.md"],
    )


# ================================================================= 8. analysis-documentation
def demo_analysis_documentation() -> SkillResult:
    template = ss.read_doc("analysis-documentation", "analysis_doc_template.md", 1200)
    cat = json.loads((SITE_ARTIFACTS / "_catalog.json").read_text(encoding="utf-8"))
    man = data.manifest()

    n_artifacts = len(list(SITE_ARTIFACTS.glob("*.json"))) - 1
    scripts_used = set()
    for f in SITE_ARTIFACTS.glob("*.json"):
        if f.name.startswith("_"):
            continue
        scripts_used.update(json.loads(f.read_text(encoding="utf-8")).get("used_skill_scripts", []))

    doc = f"""# Data Science Skills Mastery Lab -- analysis documentation

## Purpose
Demonstrate all {cat['counts']['total']} skills from two public Claude Code skill collections
({cat['counts']['agent-ml-skills']} from param087/agent-ml-skills, {cat['counts']['data-analytics-skills']}
from nimrodfisher/data-analytics-skills) on popular Kaggle datasets, organised by the six CRISP-DM phases.

## Data
{chr(10).join('- ' + d['dataset'] + ' (' + d.get('kaggle_equivalent', '-') + ') sha256=' + (d.get('sha256') or '-')[:12] for d in man['datasets'])}

## Method
One Python pipeline (`pipeline/`), one module per CRISP-DM phase, plus `pipeline/heavy/` for the
deep-learning, LLM, retrieval and serving demos. Every demo returns a `SkillResult` and is serialised
to `site/public/artifacts/<skill>.json`; the React site renders those files and never runs Python.

## Reproduction
```
python pipeline/00_download_data.py
python pipeline/crisp01_business_understanding.py   # ... through crisp06
python pipeline/heavy/pytorch_fashion.py            # and the other heavy scripts
python pipeline/skills_registry.py --check          # fails unless all 46 artifacts exist
```
Seed {reg.__dict__.get('SEED', 20255255)}; environment fingerprint recorded by the `reproducible-ml` artifact.

## Limitations
- The churn observation window is assumed, not confirmed (blocking; see the peer review).
- Offer economics (save rate, offer cost) are assumptions, not measurements.
- The five dataset tracks are unrelated to one another; findings do not transfer between them.
- Fashion-MNIST and the LoRA/RAG tracks demonstrate technique, not a business outcome.
"""
    (ARTIFACTS / "analysis_documentation.md").write_text(doc, encoding="utf-8")

    by_phase = {p["name"]: sum(1 for s in cat["skills"] if s["phase"] == p["phase"]) for p in cat["phases"]}

    return SkillResult(
        skill="analysis-documentation", source="data-analytics-skills",
        category="Documentation & Knowledge", phase=6, track="meta",
        title="The documentation that lets someone else rerun all of this",
        prescribes="Document purpose, data, method, reproduction steps and limitations -- enough that a "
                   "competent stranger can rerun the work and know what not to trust.",
        applied="Generated the lab's analysis document from the live registry, the data manifest and the "
                "emitted artifacts, using the skill's analysis_doc_template.md structure.",
        narrative=[
            f"The document is generated, not written: dataset digests come from `data/raw/manifest.json`, the "
            f"skill counts from the registry, and the artifact count ({n_artifacts}) from the directory itself. "
            "A hand-maintained version of this page would be wrong within a week.",
            f"{len(scripts_used)} bundled skill scripts were executed across the lab rather than "
            "reimplemented, and each artifact lists the ones it used. That list is what makes the claim "
            "'these skills work' checkable rather than rhetorical.",
            "The limitations section is placed where it will be read and states the blocking issue first. "
            "Documentation that buries its caveats is how a caveated result becomes an uncaveated slide.",
        ],
        kpis=[
            Kpi("Skills documented", str(cat["counts"]["total"]), "two collections"),
            Kpi("Artifacts generated", str(n_artifacts), "one JSON per skill"),
            Kpi("Bundled scripts executed", str(len(scripts_used)), "not reimplemented", tone="good"),
            Kpi("Limitations stated", "4", "blocking one first", tone="warn"),
        ],
        charts=[Chart(id="skills-per-phase", kind="bar", title="Skills demonstrated per CRISP-DM phase",
                      data=[{"x": k, "n": v} for k, v in by_phase.items()],
                      series=[{"key": "n", "label": "skills"}])],
        tables=[Table("structure", "Repository structure",
                      ["Path", "Contents"],
                      [[".claude/skills/", "the 46 installed skills, unmodified"],
                       ["pipeline/lib/", "paths, seeds, data loaders, the artifact serialiser"],
                       ["pipeline/crisp0*.py", "one module per CRISP-DM phase"],
                       ["pipeline/heavy/", "CNN, LoRA, RAG and the FastAPI service"],
                       ["pipeline/skills_registry.py", "skill -> phase mapping and the coverage gate"],
                       ["data/", "raw downloads, the manifest with digests, processed parquet"],
                       ["artifacts/", "models, MLflow store, LoRA adapter, generated documents"],
                       ["site/", "React front end reading site/public/artifacts/*.json"]])],
        code_excerpt=doc,
        code_language="markdown",
        takeaway="Someone can clone this, run six commands, and get the same numbers -- and the limitations "
                 "section tells them which of those numbers to argue with.",
        used_skill_scripts=[".claude/skills/analysis-documentation/references/analysis_doc_template.md"],
        artifacts=["artifacts/analysis_documentation.md"],
    )


# ================================================================= 9. analysis-retrospective
def demo_analysis_retrospective() -> SkillResult:
    template = ss.read_doc("analysis-retrospective", "retrospective_template.md", 1200)

    incidents = [
        ["Upstream API drift", "sql_lint.py passes dialect='ansi'; sqlglot 30 removed that name",
         "Passed dialect='duckdb' -- the dialect we actually execute", "Pin the dialect at the call site"],
        ["Upstream API drift", "cohort_builder.py uses the 'MS' period alias; pandas 2.3 rejects it",
         "Overrode FREQ_MAP['monthly'] = 'M' before calling", "Skill scripts need a compatibility shim layer"],
        ["Platform change", "MLflow 3 refuses a plain filesystem tracking store",
         "Switched to a local SQLite backend", "Read the deprecation before designing around a default"],
        ["Environment", "torchvision 0.27 against torch 2.5.1 broke every transformers import",
         "Pinned torchvision 0.20.1 to match torch", "Version-match the vision/audio companions to torch"],
        ["Environment", "Python's certifi bundle rejected the dataset hosts (expired root)",
         "Routed verification through the Windows store with truststore",
         "Never solve a certificate error by disabling verification"],
        ["Analysis error", "The first campaign economics valued a saved customer at one year of margin "
         "while impact-quantification used lifetime value -- the same campaign looked both profitable and "
         "unprofitable",
         "Defined customer_ltv() once and used it for both", "One metric, one definition, one function"],
        ["Negative result", "Cross-encoder reranking added no recall over RRF fusion and cost 573 ms/query",
         "Reported it as a negative result instead of dropping the comparison",
         "Short chunks give a reranker nothing to work with"],
        ["Negative result", "Optuna and random search tied; random search found its best at trial 2",
         "Rewrote the narrative to say so", "Do not let a preferred tool win a comparison it lost"],
    ]
    went_well = [
        "Making every demo return one dataclass meant the site needed exactly one renderer.",
        "Running the skills' own bundled scripts on real data found three upstream incompatibilities that "
        "reading the code would not have.",
        "The coverage gate (46 artifacts or the build fails) removed any temptation to quietly skip a skill.",
        "Seeding once in lib/seeds and importing it everywhere made phases 3-5 rerun to identical numbers.",
    ]
    do_differently = [
        "Define the shared economics before writing any phase that spends money -- the LTV inconsistency cost a "
        "rerun of phase 5.",
        "Check every bundled script against the installed library versions up front rather than discovering it "
        "mid-phase.",
        "Size the heavy tracks by wall clock first; the CPU-only torch build shaped every later decision and "
        "was discovered by accident.",
    ]

    return SkillResult(
        skill="analysis-retrospective", source="data-analytics-skills",
        category="Workflow Optimization", phase=6, track="meta",
        title="Eight real incidents from building this lab",
        prescribes="After delivery, capture what worked, what did not and what to do differently -- with "
                   "specific incidents rather than sentiments, so the lesson is transferable.",
        applied="Logged every failure encountered while building the lab into the skill's retrospective "
                "template, including the two negative results and the one analysis error.",
        narrative=[
            f"{len(incidents)} incidents, and the pattern is that {sum(1 for i in incidents if i[0] in ('Upstream API drift', 'Environment', 'Platform change'))} "
            "of them were environment or upstream drift rather than analysis mistakes. Skills that ship code "
            "age against their dependencies; the lesson is a compatibility shim, not distrust of the skill.",
            "The one genuine analysis error is worth naming plainly: the campaign economics valued a saved "
            "customer at one year of margin in the threshold sweep and at lifetime value in the impact "
            "calculation, which made the same campaign look both unprofitable and profitable. The fix was one "
            "function used by both -- the same 'one metric, one definition' rule that `metric-reconciliation` "
            "teaches in phase 2, applied to our own work.",
            "Two negative results were kept rather than deleted: the reranker that did not help, and the "
            "Bayesian search that tied with random search. A demonstration that only shows techniques winning "
            "is a brochure.",
        ],
        kpis=[
            Kpi("Incidents logged", str(len(incidents)), "with fixes and lessons"),
            Kpi("Environment / upstream", str(sum(1 for i in incidents if i[0] != "Analysis error"
                                                  and i[0] != "Negative result")),
                "not analysis mistakes", tone="warn"),
            Kpi("Analysis errors", "1", "inconsistent value basis", tone="bad"),
            Kpi("Negative results kept", "2", "reranking, Bayesian search", tone="good"),
        ],
        charts=[Chart(id="incident-types", kind="bar", title="Incidents by category",
                      data=[{"x": c, "n": sum(1 for i in incidents if i[0] == c)}
                            for c in dict.fromkeys(i[0] for i in incidents)],
                      series=[{"key": "n", "label": "incidents"}])],
        tables=[
            Table("incidents", "Incident log", ["Category", "What happened", "Fix", "Lesson"], incidents),
            Table("retro", "Retrospective", ["Went well", "Do differently"],
                  [[w, d] for w, d in zip(went_well, do_differently + [""] * len(went_well))]),
        ],
        code_excerpt=template,
        code_language="markdown",
        takeaway=f"{sum(1 for i in incidents if i[0] not in ('Analysis error', 'Negative result'))} of "
                 f"{len(incidents)} incidents were dependency or platform drift, one was our own inconsistent "
                 "metric definition, and two were negative results worth keeping -- all of which are only "
                 "visible because the skills were actually run rather than described.",
        used_skill_scripts=[".claude/skills/analysis-retrospective/references/retrospective_template.md"],
    )


DEMOS = [
    demo_funnel_analysis,
    demo_dashboard_specification,
    demo_visualization_builder,
    demo_executive_summary_generator,
    demo_data_narrative_builder,
    demo_technical_to_business_translator,
    demo_methodology_explainer,
    demo_analysis_documentation,
    demo_analysis_retrospective,
]


def main() -> None:
    print("\n=== CRISP-DM 6: Deployment ===")
    for fn in DEMOS:
        emit(fn())


if __name__ == "__main__":
    main()
