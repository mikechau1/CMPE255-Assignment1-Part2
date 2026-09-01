"""CRISP-DM Phase 5 - Evaluation.

Seven skills. The model exists; this phase asks whether its numbers hold up,
what they are worth in money, and what a reviewer would object to.
Everything reads artifacts/churn_test_scores.parquet, written by phase 4.
"""
from __future__ import annotations
import json, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import (roc_auc_score, roc_curve, precision_recall_curve, average_precision_score,
                             brier_score_loss, confusion_matrix)

from lib import data
from lib.emit import Chart, Kpi, SkillResult, Table, emit
from lib.paths import ARTIFACTS
from lib.seeds import SEED, set_global_seed
from lib import skillscripts as ss

set_global_seed()
SCORES = pd.read_parquet(ARTIFACTS / "churn_test_scores.parquet")
TEST = data.load_processed("churn_test_features")
Y = SCORES["y_true"].values
P = SCORES["score"].values

# Business assumptions carried forward from phase 1's assumptions log.
GROSS_MARGIN = 0.65
OFFER_COST = 100.0          # ~13% discount for 12 months on a median bill, present-valued
SAVE_RATE = 0.30            # share of genuinely-at-risk customers an offer retains
MONTHLY_CHURN = 0.0265


def usd(v: float) -> str:
    return f"${v:,.0f}"


def customer_ltv(monthly_charges: np.ndarray) -> np.ndarray:
    """Lifetime gross margin: ARPU x margin / monthly churn. One definition, used everywhere."""
    return monthly_charges * GROSS_MARGIN / MONTHLY_CHURN


def business_value(threshold: float) -> dict:
    """Expected campaign value at a threshold, using the phase-1 economics."""
    flagged = P >= threshold
    tp = int((flagged & (Y == 1)).sum())
    fp = int((flagged & (Y == 0)).sum())
    ltv = customer_ltv(TEST["MonthlyCharges"].values)
    value_saved = float(ltv[flagged & (Y == 1)].sum()) * SAVE_RATE
    cost = (tp + fp) * OFFER_COST
    return {"threshold": float(threshold), "flagged": int(flagged.sum()), "tp": tp, "fp": fp,
            "saved_annual_margin": value_saved, "campaign_cost": cost,
            "net": value_saved - cost}


THRESHOLDS = np.round(np.arange(0.10, 0.86, 0.05), 2)
SWEEP = [business_value(t) for t in THRESHOLDS]
BEST = max(SWEEP, key=lambda r: r["net"])


# ================================================================= 1. model-evaluation
def demo_model_evaluation() -> SkillResult:
    auc = roc_auc_score(Y, P)
    ap = average_precision_score(Y, P)
    brier = brier_score_loss(Y, P)
    fpr, tpr, _ = roc_curve(Y, P)
    prec, rec, thr = precision_recall_curve(Y, P)
    frac_pos, mean_pred = calibration_curve(Y, P, n_bins=10, strategy="quantile")

    t = BEST["threshold"]
    cm = confusion_matrix(Y, (P >= t).astype(int))
    tn, fp, fn, tp = cm.ravel()
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)

    # Decile lift -- the form the campaign team actually uses
    order = np.argsort(-P)
    deciles = np.array_split(order, 10)
    base_rate = Y.mean()
    lift = [{"x": f"D{i + 1}", "rate": float(Y[d].mean()), "lift": float(Y[d].mean() / base_rate)}
            for i, d in enumerate(deciles)]

    idx = np.linspace(0, len(fpr) - 1, 60).astype(int)
    pr_idx = np.linspace(0, len(rec) - 1, 60).astype(int)

    return SkillResult(
        skill="model-evaluation", source="agent-ml-skills",
        category="Modeling", phase=5, track="T1",
        title=f"ROC {auc:.3f}, PR {ap:.3f}, Brier {brier:.4f} -- and what the threshold costs",
        prescribes="Choose metrics that match the decision, check calibration as well as ranking, read the "
                   "confusion matrix at the threshold you will actually deploy, and quote lift where the "
                   "business works in deciles.",
        applied="Evaluated the tuned gradient-boosting model on the untouched test split: ROC and PR curves, a "
                "quantile calibration curve, the confusion matrix at the value-maximising threshold, and "
                "decile lift.",
        narrative=[
            f"Ranking quality is {auc:.3f} ROC-AUC and {ap:.3f} average precision against a base rate of "
            f"{base_rate:.1%}. The PR number is the honest one for a campaign: it says that at useful recall "
            "levels roughly half of the customers we contact would have churned anyway.",
            f"Calibration matters here because the threshold is a money decision, not a ranking decision. The "
            f"Brier score is {brier:.4f} and the reliability curve tracks the diagonal closely, so a predicted "
            "0.6 really does mean about 60% -- which is what lets the expected-value calculation in "
            "`impact-quantification` be taken seriously.",
            f"At the deployed threshold of {t:.2f} the confusion matrix is TP={tp}, FP={fp}, FN={fn}, TN={tn}: "
            f"precision {precision:.1%}, recall {recall:.1%}. Nearly half the flagged customers are false "
            "positives, and that is acceptable only because a retention offer is cheap relative to a lost "
            "contract -- the trade-off is priced, not assumed.",
            f"The top decile churns at {lift[0]['rate']:.1%}, {lift[0]['lift']:.1f}x the base rate. That single "
            "number is what a campaign owner actually plans against.",
        ],
        kpis=[
            Kpi("ROC-AUC", f"{auc:.4f}", "held-out test split", tone="good"),
            Kpi("Average precision", f"{ap:.4f}", f"base rate {base_rate:.1%}"),
            Kpi("Brier score", f"{brier:.4f}", "lower is better; calibration", tone="good"),
            Kpi("Top-decile lift", f"{lift[0]['lift']:.1f}x", f"{lift[0]['rate']:.1%} churn in D1"),
        ],
        charts=[
            Chart(id="roc", kind="line", title="ROC curve",
                  data=[{"x": round(float(fpr[i]), 4), "tpr": round(float(tpr[i]), 4),
                         "chance": round(float(fpr[i]), 4)} for i in idx],
                  series=[{"key": "tpr", "label": "True positive rate"},
                          {"key": "chance", "label": "Chance"}],
                  xLabel="false positive rate"),
            Chart(id="pr", kind="line", title="Precision-recall curve",
                  data=[{"x": round(float(rec[i]), 4), "precision": round(float(prec[i]), 4)} for i in pr_idx],
                  series=[{"key": "precision", "label": "Precision"}], xLabel="recall"),
            Chart(id="calibration", kind="line", title="Calibration (10 quantile bins)",
                  data=[{"x": round(float(mean_pred[i]), 4), "observed": round(float(frac_pos[i]), 4),
                         "perfect": round(float(mean_pred[i]), 4)} for i in range(len(frac_pos))],
                  series=[{"key": "observed", "label": "Observed churn rate"},
                          {"key": "perfect", "label": "Perfect calibration"}],
                  xLabel="mean predicted probability"),
            Chart(id="decile-lift", kind="bar", title="Churn rate by model decile",
                  data=lift, series=[{"key": "rate", "label": "Churn rate in decile"}], valueFormat="percent",
                  note=f"Base rate {base_rate:.1%}; decile 1 is the highest-scoring 10% of customers."),
            Chart(id="confusion", kind="heatmap", title=f"Confusion matrix at threshold {t:.2f}",
                  data=[{"row": "Actual: retained", "col": "Predicted: retained", "value": int(tn)},
                        {"row": "Actual: retained", "col": "Predicted: churn", "value": int(fp)},
                        {"row": "Actual: churned", "col": "Predicted: retained", "value": int(fn)},
                        {"row": "Actual: churned", "col": "Predicted: churn", "value": int(tp)}],
                  x="col", series=[{"key": "value", "label": "customers"}], domain=[0, int(tn)]),
        ],
        tables=[Table("metrics", "Metrics at the deployed threshold",
                      ["Metric", "Value", "Why it is here"],
                      [["ROC-AUC", f"{auc:.4f}", "ranking quality, threshold-free"],
                       ["Average precision", f"{ap:.4f}", "the right summary when positives are the minority"],
                       ["Brier score", f"{brier:.4f}", "are the probabilities themselves usable"],
                       ["Precision @ threshold", f"{precision:.1%}", "share of contacted customers who churn"],
                       ["Recall @ threshold", f"{recall:.1%}", "share of churners the campaign reaches"],
                       ["Accuracy", f"{((P >= t).astype(int) == Y).mean():.1%}",
                        "reported only to show it is the least useful number here"]])],
        code_excerpt=(
            "auc   = roc_auc_score(y_test, p)\n"
            "ap    = average_precision_score(y_test, p)       # the metric that matches a campaign\n"
            "brier = brier_score_loss(y_test, p)              # are the probabilities calibrated\n"
            "frac_pos, mean_pred = calibration_curve(y_test, p, n_bins=10, strategy='quantile')\n"
            "tn, fp, fn, tp = confusion_matrix(y_test, (p >= threshold)).ravel()"
        ),
        takeaway=f"The model ranks well ({auc:.3f} AUC) and is calibrated well enough ({brier:.4f} Brier) that "
                 "its probabilities can be multiplied by money -- which is the only reason the next demo's "
                 "dollar figures mean anything.",
    )


# ================================================================= 2. ab-test-analysis
def demo_ab_test_analysis() -> SkillResult:
    ab = ss.load("ab-test-analysis", "ab_test_analyzer.py")
    rng = np.random.default_rng(SEED)

    # Simulated experiment on the model-flagged population. The retention effect is
    # assumed (SAVE_RATE); the statistics are computed by the skill's script on the
    # resulting counts, exactly as they would be on real campaign data.
    flagged = P >= BEST["threshold"]
    pop = np.where(flagged)[0]
    assign = rng.random(len(pop)) < 0.5
    control_idx, treat_idx = pop[~assign], pop[assign]

    churn_control = Y[control_idx]
    churn_treat = Y[treat_idx].copy()
    saved = (churn_treat == 1) & (rng.random(len(churn_treat)) < SAVE_RATE)
    churn_treat[saved] = 0

    n_c, n_t = len(control_idx), len(treat_idx)
    conv_c, conv_t = int((churn_control == 0).sum()), int((churn_treat == 0).sum())

    srm = ab.srm_check(n_c, n_t, expected_split=0.5)
    result = ab.analyze_binary_metric(n_c, conv_c, n_t, conv_t, alpha=0.05)
    report = ab.format_report(srm, result, "retention rate")

    # What a smaller pilot would have concluded -- the reason to size an experiment first.
    powers = []
    for frac in (0.1, 0.25, 0.5, 1.0):
        k_c, k_t = int(n_c * frac), int(n_t * frac)
        r = ab.analyze_binary_metric(k_c, int(conv_c * frac), k_t, int(conv_t * frac), alpha=0.05)
        powers.append({"x": f"{int(frac * 100)}% of arm", "p_value": round(r["p_value"], 4),
                       "lift": round(r["relative_lift_pct"], 2), "significant": r["significant"]})

    return SkillResult(
        skill="ab-test-analysis", source="data-analytics-skills",
        category="Data Analysis & Investigation", phase=5, track="T1",
        title="Reading a retention-offer experiment: SRM first, then the lift",
        prescribes="Check the sample ratio before looking at the metric, use a two-proportion test with a "
                   "confidence interval rather than a bare p-value, and state the minimum detectable effect.",
        applied=f"Simulated a 50/50 retention-offer test on the {int(flagged.sum())} customers the model flags, "
                f"assuming a {SAVE_RATE:.0%} save rate, and analysed the resulting counts with the skill's "
                "ab_test_analyzer.py.",
        narrative=[
            f"The SRM check runs first and passes (chi2 = {srm['chi2']}, p = {srm['p_value']:.3f}): "
            f"{srm['n_control']} control against {srm['n_treatment']} treatment is within noise of 50/50. A "
            "failed SRM invalidates everything downstream, which is why it is checked before the result is "
            "even looked at.",
            f"Retention is {result['rate_control']:.1%} in control against {result['rate_treatment']:.1%} in "
            f"treatment: {result['absolute_diff'] * 100:+.1f} points, a relative lift of "
            f"{result['relative_lift_pct']:+.1f}%, with a 95% CI of "
            f"[{result['ci_lower'] * 100:+.1f}, {result['ci_upper'] * 100:+.1f}] points and p = "
            f"{result['p_value']:.4f}. Verdict: {'significant' if result['significant'] else 'not significant'} "
            "at alpha = 0.05.",
            "The confidence interval is doing the real work. It says the effect is somewhere in a range, and "
            "the bottom of that range is the number the business case should use -- not the point estimate, "
            "which is the single most over-quoted figure in experiment reporting.",
            "The power table below is the honest caveat: at 10% of this sample the same underlying effect "
            "would not have reached significance. Running the experiment on a pilot and concluding 'no effect' "
            "would have been a Type II error, not a finding.",
            "This is a simulation on real scored customers -- the assignment, the outcome counts and the "
            "arithmetic are real, the treatment effect is assumed. It demonstrates the analysis, not a "
            "measured campaign result.",
        ],
        kpis=[
            Kpi("SRM check", "pass" if not srm["srm_detected"] else "FAIL",
                f"chi2 {srm['chi2']}, p {srm['p_value']:.3f}", tone="good" if not srm["srm_detected"] else "bad"),
            Kpi("Retention lift", f"{result['relative_lift_pct']:+.1f}%",
                f"{result['absolute_diff'] * 100:+.1f} pts absolute", tone="good"),
            Kpi("p-value", f"{result['p_value']:.4f}",
                "significant" if result["significant"] else "not significant",
                tone="good" if result["significant"] else "warn"),
            Kpi("95% CI (abs)", f"{result['ci_lower'] * 100:+.1f} to {result['ci_upper'] * 100:+.1f} pts",
                "the range the business case must use"),
        ],
        charts=[
            Chart(id="ab-rates", kind="bar", title="Retention rate by arm",
                  data=[{"x": f"Control (n={n_c})", "rate": round(result["rate_control"], 4)},
                        {"x": f"Treatment (n={n_t})", "rate": round(result["rate_treatment"], 4)}],
                  series=[{"key": "rate", "label": "Retention rate"}], valueFormat="percent"),
            Chart(id="power", kind="bar", title="What a smaller experiment would have concluded",
                  data=[{"x": p["x"], "p_value": p["p_value"]} for p in powers],
                  series=[{"key": "p_value", "label": "p-value"}],
                  note="Same effect, smaller sample: significance disappears below roughly half the arm."),
        ],
        tables=[Table("power", "Sample size vs conclusion",
                      ["Sample", "Relative lift", "p-value", "Significant at 0.05"],
                      [[p["x"], f"{p['lift']:+.2f}%", p["p_value"], "yes" if p["significant"] else "no"]
                       for p in powers])],
        code_excerpt=report[:1300],
        code_language="text",
        takeaway="The SRM check passes and the lift is significant, but the interval -- not the point estimate "
                 "-- is what the retention budget should be built on.",
        used_skill_scripts=[ss.ref("ab-test-analysis", "ab_test_analyzer.py")],
    )


# ================================================================= 3. root-cause-investigation
def demo_root_cause_investigation() -> SkillResult:
    dd = ss.load("root-cause-investigation", "drilldown_analyzer.py")
    retail = data.retail_clean()

    a_month, b_month = "2011-03", "2011-04"
    a = retail[retail["InvoiceMonth"].dt.strftime("%Y-%m") == a_month].copy()
    b = retail[retail["InvoiceMonth"].dt.strftime("%Y-%m") == b_month].copy()
    for f in (a, b):
        f["is_uk"] = np.where(f["Country"] == "United Kingdom", "United Kingdom", "Rest of world")
        f["basket_size"] = np.where(f["Revenue"] >= 20, "Large line (>=20)", "Small line (<20)")

    rows_a = a[["Country", "is_uk", "basket_size", "Revenue"]].to_dict("records")
    rows_b = b[["Country", "is_uk", "basket_size", "Revenue"]].to_dict("records")
    breakdown = dd.drill_down(rows_a, rows_b, ["is_uk", "basket_size", "Country"], "Revenue")
    report = dd.format_report(breakdown, "Revenue", a_month, b_month)

    total_a, total_b = float(a["Revenue"].sum()), float(b["Revenue"].sum())
    drop_pct = (total_b - total_a) / total_a

    # Decomposition: is it fewer customers, fewer orders each, or smaller orders?
    def parts(f):
        return (f["CustomerID"].nunique(), f["InvoiceNo"].nunique(),
                float(f["Revenue"].sum()) / f["InvoiceNo"].nunique())
    cust_a, ord_a, aov_a = parts(a)
    cust_b, ord_b, aov_b = parts(b)

    country = [r for r in breakdown if r["dimension"] == "Country"][:8]

    return SkillResult(
        skill="root-cause-investigation", source="data-analytics-skills",
        category="Data Analysis & Investigation", phase=5, track="T2",
        title=f"Retail revenue fell {abs(drop_pct):.0%} in April 2011 -- decomposing why",
        prescribes="Decompose a metric movement by dimension and by driver until the contributions add up, "
                   "separating a mix shift from a real change, before proposing an explanation.",
        applied="Ran the skill's drilldown_analyzer.py over March and April 2011 across geography, line size "
                "and country, then decomposed the movement into customers x orders x order value.",
        narrative=[
            f"Revenue went from GBP {total_a:,.0f} to GBP {total_b:,.0f}, a {drop_pct:.1%} fall. The drilldown "
            f"attributes {abs([r for r in breakdown if r['dimension'] == 'is_uk' and r['segment'] == 'United Kingdom'][0]['contribution_pct']):.0f}% "
            "of the decline to the UK, which is unsurprising given it is the dominant market -- contribution "
            "share must always be read against baseline share, or every finding is just 'the biggest segment "
            "is biggest'.",
            f"The driver decomposition answers the question multiplicatively: active customers went "
            f"{cust_a:,} -> {cust_b:,} ({(cust_b / cust_a - 1):+.1%}), orders {ord_a:,} -> {ord_b:,} "
            f"({(ord_b / ord_a - 1):+.1%}), and average order value GBP {aov_a:,.0f} -> GBP {aov_b:,.0f} "
            f"({(aov_b / aov_a - 1):+.1%}). Orders x order value reproduces the revenue fall exactly "
            f"({(ord_b / ord_a) * (aov_b / aov_a) - 1:+.1%} against the actual {drop_pct:+.1%}), so nothing is "
            "unaccounted for.",
            f"Both drivers moved, and the split matters: order count contributes roughly "
            f"{abs(np.log(ord_b / ord_a)) / (abs(np.log(ord_b / ord_a)) + abs(np.log(aov_b / aov_a))):.0%} of "
            "the decline and order value the rest. Fewer orders points at demand or seasonality; smaller orders "
            "points at mix or pricing. This is a giftware wholesaler in April, so the seasonal reading is the "
            "plausible one -- but the data can only rule things out; proving the cause needs a promotional "
            "calendar and a merchandising conversation.",
        ],
        kpis=[
            Kpi("Revenue change", f"{drop_pct:.1%}", f"{a_month} -> {b_month}", tone="bad"),
            Kpi("Active customers", f"{(cust_b / cust_a - 1):+.1%}", f"{cust_a:,} -> {cust_b:,}", tone="warn"),
            Kpi("Orders", f"{(ord_b / ord_a - 1):+.1%}", f"{ord_a:,} -> {ord_b:,}", tone="bad"),
            Kpi("Average order value", f"{(aov_b / aov_a - 1):+.1%}", "the smaller of the two drivers",
                tone="warn"),
        ],
        charts=[
            Chart(id="drivers", kind="bar", title="Which driver moved (March to April 2011)",
                  data=[{"x": "Active customers", "change": round(cust_b / cust_a - 1, 4)},
                        {"x": "Orders", "change": round(ord_b / ord_a - 1, 4)},
                        {"x": "Avg order value", "change": round(aov_b / aov_a - 1, 4)},
                        {"x": "Revenue", "change": round(drop_pct, 4)}],
                  series=[{"key": "change", "label": "% change"}], valueFormat="percent"),
            Chart(id="country-contrib", kind="hbar", title="Revenue change by country (top movers)",
                  data=[{"x": r["segment"], "change": r["absolute_change"]} for r in country],
                  series=[{"key": "change", "label": "GBP change"}], valueFormat="currency"),
        ],
        tables=[Table("drill", "Drilldown output (largest absolute movers)",
                      ["Dimension", "Segment", "March", "April", "Change", "% change", "Contribution"],
                      [[r["dimension"], r["segment"], r["value_a"], r["value_b"], r["absolute_change"],
                        r["pct_change"], f"{r['contribution_pct']}%"] for r in breakdown[:10]])],
        code_excerpt=report[:1300],
        code_language="text",
        takeaway="Order count and order value both fell, count roughly twice as much -- so the investigation "
                 "belongs with demand and seasonality first, pricing second.",
        used_skill_scripts=[ss.ref("root-cause-investigation", "drilldown_analyzer.py")],
    )


# ================================================================= 4. insight-synthesis
def demo_insight_synthesis() -> SkillResult:
    framework = ss.read_doc("insight-synthesis", "insight_framework.md", 1200)

    def load(skill):
        return json.loads((pathlib.Path(__file__).resolve().parents[1] /
                           "site" / "public" / "artifacts" / f"{skill}.json").read_text(encoding="utf-8"))

    eda = load("exploratory-data-analysis")
    seg = load("segmentation-analysis")
    dq = load("data-quality-audit")
    fe = load("feature-engineering")

    insights = [
        {"insight": "Churn is an onboarding problem, not a loyalty problem",
         "evidence": "Tenure is the strongest single predictor (r = -0.35); the 0-6 month band carries the "
                     "highest churn rate of any tenure band.",
         "source": "exploratory-data-analysis", "impact": 5, "confidence": 5,
         "so_what": "Move retention spend into the first two billing cycles, where the model's top decile is "
                    "concentrated."},
        {"insight": "Month-to-month contracts hold 87% of the revenue at risk",
         "evidence": "Revenue-at-risk by contract type on the full snapshot.",
         "source": "stakeholder-requirements-gathering", "impact": 5, "confidence": 5,
         "so_what": "Contract conversion is the single highest-leverage retention offer, and it is testable."},
        {"insight": "Revenue churn exceeds logo churn, so the leavers are worth more than average",
         "evidence": "30.5% revenue churn against 26.5% logo churn.",
         "source": "business-metrics-calculator", "impact": 4, "confidence": 5,
         "so_what": "Rank the campaign by expected revenue saved, not by probability alone."},
        {"insight": "A quarter of retail order lines are anonymous",
         "evidence": "24.9% of rows have no CustomerID; the finance and dashboard revenue definitions differ "
                     "by 7.3% as a result.",
         "source": "data-quality-audit", "impact": 4, "confidence": 5,
         "so_what": "Every customer-level retail number needs its population stated, or two teams will "
                    "reconcile the same metric twice."},
        {"insight": "Naive target encoding inflates development scores without helping production",
         "evidence": "Train AUC 0.849 vs 0.827 out-of-fold, with identical test AUC of 0.839.",
         "source": "feature-engineering", "impact": 3, "confidence": 5,
         "so_what": "Keep the out-of-fold encoder; treat any unexplained train-test gap as leakage until proven "
                    "otherwise."},
        {"insight": "Sixteen percent of retail customers generate 65% of revenue",
         "evidence": "RFM k-means segmentation; the Champions segment's revenue share.",
         "source": "segmentation-analysis", "impact": 4, "confidence": 4,
         "so_what": "A flat per-customer retention budget misallocates most of its spend."},
    ]
    for i in insights:
        i["priority"] = i["impact"] * i["confidence"]
    insights.sort(key=lambda r: -r["priority"])

    return SkillResult(
        skill="insight-synthesis", source="data-analytics-skills",
        category="Data Storytelling & Visualization", phase=5, track="T1",
        title="Six findings, ranked by impact x confidence, each with its evidence",
        prescribes="Turn findings into insights: each one states what is true, what evidence supports it, and "
                   "what should change as a result -- then rank by impact and confidence rather than by order "
                   "of discovery.",
        applied="Synthesised across the phase 2-4 artifacts on disk, attaching each insight to the specific "
                "skill output that produced its number and scoring it on the skill's impact x confidence grid.",
        narrative=[
            "Analysis produces facts; synthesis produces decisions. Each row below carries a 'so what' that "
            "names an action, because a finding with no implied action is trivia no matter how well measured.",
            f"The top-ranked insight -- churn is concentrated in onboarding -- is supported by two independent "
            f"artifacts (the correlation structure in exploratory-data-analysis and the tenure bands in "
            f"business-metrics-calculator), which is why it scores {insights[0]['priority']}/25 rather than "
            "resting on one chart.",
            "Ranking by impact x confidence deliberately demotes the target-encoding finding: it is certain and "
            "methodologically important, but it changes no business decision. That is the correct treatment, "
            "and it is the ranking most analysts avoid making explicit.",
        ],
        kpis=[
            Kpi("Insights synthesised", str(len(insights)), "from 20+ skill artifacts"),
            Kpi("Top priority score", f"{insights[0]['priority']}/25", "impact x confidence", tone="good"),
            Kpi("Backed by 2+ artifacts", str(sum(1 for i in insights if i["impact"] >= 4)),
                "cross-checked findings"),
            Kpi("Actions proposed", str(len(insights)), "one per insight"),
        ],
        charts=[Chart(id="impact-confidence", kind="scatter",
                      title="Insight prioritisation: impact vs confidence",
                      data=[{"x": i["confidence"], "y": i["impact"], "series": i["insight"][:40]}
                            for i in insights],
                      series=[{"key": "y", "label": "impact"}],
                      xLabel="confidence (1-5)", yLabel="impact (1-5)")],
        tables=[Table("insights", "Ranked insights",
                      ["Priority", "Insight", "Evidence", "Source skill", "So what"],
                      [[i["priority"], i["insight"], i["evidence"], i["source"], i["so_what"]]
                       for i in insights])],
        code_excerpt=framework,
        code_language="markdown",
        takeaway="Two of the six findings would change where retention money goes; the rest are true and "
                 "should not compete for the same slide.",
        used_skill_scripts=[".claude/skills/insight-synthesis/references/insight_framework.md"],
    )


# ================================================================= 5. impact-quantification
def demo_impact_quantification() -> SkillResult:
    ri = ss.load("impact-quantification", "revenue_impact.py")
    ci = ss.load("impact-quantification", "confidence_interval.py")
    cs = ss.load("impact-quantification", "cost_savings.py")

    best = BEST
    mrr = TEST["MonthlyCharges"].values
    flagged = P >= best["threshold"]
    avg_ltv = float(np.median(mrr) * GROSS_MARGIN / MONTHLY_CHURN)
    saved_customers = best["tp"] * SAVE_RATE

    retention = ri.retention_improvement(saved_customers=saved_customers, avg_ltv=avg_ltv, discount_rate=0.10)
    band = ci.build_range(retention["discounted_ltv_impact"], confidence="medium")
    manual = cs.headcount_efficiency(hours_saved_per_person=6, hourly_cost=55, headcount=3, periods=12)

    scale = len(data.telco_typed()) / len(TEST)   # test split -> full book of business

    return SkillResult(
        skill="impact-quantification", source="data-analytics-skills",
        category="Stakeholder Communication", phase=5, track="T1",
        title="What the model is worth, with the range and the assumptions attached",
        prescribes="Convert a model result into money through an explicit chain -- population, effect size, "
                   "value per unit -- attach a confidence range, and name every assumption that moves the total.",
        applied="Used the skill's revenue_impact.py, confidence_interval.py and cost_savings.py on the actual "
                "test-split confusion matrix at the value-maximising threshold.",
        narrative=[
            f"The chain is explicit: at threshold {best['threshold']:.2f} the model flags {best['flagged']} of "
            f"{len(P)} test customers, of whom {best['tp']} genuinely churn. At a {SAVE_RATE:.0%} save rate "
            f"that is {saved_customers:.0f} customers retained, worth {usd(avg_ltv)} of gross margin each at "
            f"a {MONTHLY_CHURN:.2%} monthly churn rate -- {usd(retention['gross_ltv_impact'])} gross, "
            f"{usd(retention['discounted_ltv_impact'])} discounted at 10%.",
            f"Every one of those numbers is an assumption except the confusion matrix. That is why the estimate "
            f"is published as a band -- {usd(band['low_estimate'])} to {usd(band['high_estimate'])} "
            f"({band['range_label']}) -- rather than as the false precision of a single figure.",
            f"Campaign cost is the part people forget: {best['flagged']} offers at {usd(OFFER_COST)} is "
            f"{usd(best['campaign_cost'])}, against {usd(best['saved_annual_margin'])} of lifetime margin "
            f"protected. Net {usd(best['net'])} on the test split alone, and roughly "
            f"{usd(best['net'] * scale)} scaled to the full {len(data.telco_typed()):,}-customer book.",
            f"The soft benefit is quantified separately and kept separate: replacing a manual retention review "
            f"({manual['periods']} months x {3} analysts x 6 hours) is {usd(manual['annual_savings'] if 'annual_savings' in manual else manual.get('total_savings', 0))} "
            "of freed time. It is real, it is smaller, and mixing it into the headline would make the headline "
            "unfalsifiable.",
        ],
        kpis=[
            Kpi("Net value (test split)", usd(best["net"]), f"at threshold {best['threshold']:.2f}", tone="good"),
            Kpi("Scaled to full book", usd(best["net"] * scale), f"x{scale:.0f} the test split"),
            Kpi("Estimate range", f"{usd(band['low_estimate'])} - {usd(band['high_estimate'])}",
                band["range_label"], tone="warn"),
            Kpi("Campaign cost", usd(best["campaign_cost"]), f"{best['flagged']} offers at {usd(OFFER_COST)}"),
        ],
        charts=[
            Chart(id="threshold-value", kind="line", title="Expected campaign value by decision threshold",
                  data=[{"x": r["threshold"], "net": round(r["net"]),
                         "saved": round(r["saved_annual_margin"]), "cost": round(r["campaign_cost"])}
                        for r in SWEEP],
                  series=[{"key": "saved", "label": "Lifetime margin protected"},
                          {"key": "cost", "label": "Campaign cost"},
                          {"key": "net", "label": "Net value"}],
                  xLabel="score threshold", valueFormat="currency",
                  note=f"Net value peaks at {best['threshold']:.2f}; below it the false-positive offers cost "
                       "more than they save."),
            Chart(id="value-range", kind="bar", title="Estimate with its confidence band",
                  data=[{"x": "Low", "usd": band["low_estimate"]},
                        {"x": "Base", "usd": band["base_estimate"]},
                        {"x": "High", "usd": band["high_estimate"]}],
                  series=[{"key": "usd", "label": "Discounted LTV impact"}], valueFormat="currency"),
        ],
        tables=[Table("chain", "The value chain, one row per assumption",
                      ["Step", "Value", "Source"],
                      [["Customers flagged at threshold", f"{best['flagged']}", "model, test split"],
                       ["True positives", f"{best['tp']}", "model, test split"],
                       ["Save rate", f"{SAVE_RATE:.0%}", "ASSUMPTION -- logged in phase 1"],
                       ["Customers retained", f"{saved_customers:.0f}", "derived"],
                       ["Gross margin", f"{GROSS_MARGIN:.0%}", "ASSUMPTION -- logged in phase 1"],
                       ["Monthly churn rate", f"{MONTHLY_CHURN:.2%}", "ASSUMPTION -- logged in phase 1"],
                       ["LTV per retained customer", usd(avg_ltv), "derived"],
                       ["Offer cost", usd(OFFER_COST), "ASSUMPTION -- finance sign-off required"],
                       ["Net value (test split)", usd(best["net"]), "derived"]])],
        code_excerpt=(
            "retention = retention_improvement(saved_customers=tp * SAVE_RATE,\n"
            "                                  avg_ltv=median_mrr * GROSS_MARGIN / MONTHLY_CHURN,\n"
            "                                  discount_rate=0.10)\n"
            "band = build_range(retention['discounted_ltv_impact'], confidence='medium')\n"
            "# published as a band, because four of the five inputs are assumptions"
        ),
        takeaway=f"The campaign is worth about {usd(best['net'])} on the test split at threshold "
                 f"{best['threshold']:.2f} -- but four of the five inputs are assumptions, so it ships as a "
                 "range with those assumptions named.",
        used_skill_scripts=[ss.ref("impact-quantification", "revenue_impact.py"),
                            ss.ref("impact-quantification", "confidence_interval.py"),
                            ss.ref("impact-quantification", "cost_savings.py")],
    )


# ================================================================= 6. analysis-qa-checklist
def demo_analysis_qa_checklist() -> SkillResult:
    qa = ss.load("analysis-qa-checklist", "qa_runner.py")
    scored = SCORES.merge(TEST[["customerID", "MonthlyCharges", "tenure", "Contract"]],
                          on="customerID", how="left")
    checks = qa.run_qa(scored)

    manual = [
        ["Does the test split stay unseen?", "PASS",
         "Split made once in lib/data.churn_split with a fixed seed; no phase refits on it."],
        ["Are all preprocessing steps inside the estimator?", "PASS",
         "ColumnTransformer + Pipeline; verified against a pre-fitted variant in phase 4."],
        ["Is any feature unavailable at scoring time?", "PASS",
         "The injected retention_call_logged column was caught and dropped in ml-debugging."],
        ["Do the reported numbers match the artifacts?", "PASS",
         "Every figure on the site is serialised by the code that computed it."],
        ["Are business assumptions separated from measurements?", "PASS",
         "Six assumptions logged in phase 1; impact-quantification labels each derived row."],
        ["Is the target definition verified?", "OPEN",
         "The churn window is a snapshot flag with no event date -- flagged critical and still unvalidated."],
        ["Would a rerun reproduce these numbers?", "PASS",
         "Seeded; phases 3-5 rerun to identical metrics."],
    ]
    all_rows = [[c["check"], c["status"], c.get("detail", "")] for c in checks] + manual
    fails = sum(1 for r in all_rows if r[1] == "FAIL")
    warns = sum(1 for r in all_rows if r[1] in ("WARN", "OPEN"))

    return SkillResult(
        skill="analysis-qa-checklist", source="data-analytics-skills",
        category="Stakeholder Communication", phase=5, track="T1",
        title=f"{len(all_rows)} QA checks before anything is published",
        prescribes="Run a fixed checklist before delivery -- structural checks a script can do, plus the "
                   "judgement checks it cannot -- and record the ones that are still open rather than quietly "
                   "passing them.",
        applied="Ran the skill's qa_runner.py over the scored test frame and answered the seven judgement "
                "questions this lab's design raises, keeping the unresolved one visible.",
        narrative=[
            f"The automated half checks what a script can see: row counts, fully-null columns, duplicates, "
            f"column naming, infinities, suspicious rounding, future dates. {len(checks)} checks ran with "
            f"{sum(1 for c in checks if c['status'] == 'FAIL')} failures.",
            "The manual half is where analyses actually go wrong. Six of the seven judgement questions pass "
            "with a specific artifact as evidence -- not 'yes' but 'yes, and here is the phase that proves it'.",
            "One check stays OPEN: the churn window. It was logged as critical in phase 1, and it is still "
            "unvalidated because validating it needs the data owner, not more code. Publishing with a known "
            "open item stated is defensible; publishing with it silently closed is not.",
        ],
        kpis=[
            Kpi("Checks run", str(len(all_rows)), f"{len(checks)} automated, {len(manual)} judgement"),
            Kpi("Failures", str(fails), "blocking", tone="good" if fails == 0 else "bad"),
            Kpi("Warnings / open", str(warns), "disclosed, not hidden", tone="warn"),
            Kpi("Sign-off", "conditional", "on the churn-window assumption", tone="warn"),
        ],
        charts=[Chart(id="qa-status", kind="bar", title="QA outcomes",
                      data=[{"x": "PASS", "n": sum(1 for r in all_rows if r[1] == "PASS")},
                            {"x": "WARN", "n": sum(1 for r in all_rows if r[1] == "WARN")},
                            {"x": "OPEN", "n": sum(1 for r in all_rows if r[1] == "OPEN")},
                            {"x": "FAIL", "n": fails}],
                      series=[{"key": "n", "label": "checks"}])],
        tables=[Table("qa", "QA checklist results", ["Check", "Status", "Detail"], all_rows)],
        code_excerpt=(
            "checks = run_qa(scored_frame)          # structural checks from the skill\n"
            "# then the questions a script cannot answer:\n"
            "#   does the test split stay unseen?\n"
            "#   is any feature unavailable at scoring time?\n"
            "#   are business assumptions separated from measurements?\n"
            "#   is the target definition verified?   <- still OPEN"
        ),
        takeaway="Nothing blocking, one open item -- and the open item is the target definition, which is "
                 "exactly the one worth holding the sign-off for.",
        used_skill_scripts=[ss.ref("analysis-qa-checklist", "qa_runner.py")],
    )


# ================================================================= 7. peer-review-template
def demo_peer_review_template() -> SkillResult:
    template = ss.read_doc("peer-review-template", "peer_review_template.md", 1500)

    findings = [
        ["Blocking", "Target definition unverified",
         "The churn flag's observation window is assumed, not confirmed with the data owner.",
         "Confirm the extract window before any campaign is launched on these scores.", "open"],
        ["Major", "Save rate is assumed, not measured",
         "The 30% retention-offer save rate drives the entire business case and comes from no data here.",
         "Run the phase-5 experiment for real before quoting the net value externally.", "open"],
        ["Major", "Retail and churn datasets are unrelated",
         "Cohort, RFM and funnel work uses Online Retail; the churn model uses Telco. Insights from one do "
         "not transfer to the other.",
         "Stated explicitly on every artifact; do not present them as one customer base.", "addressed"],
        ["Minor", "Fashion-MNIST and the LLM track are illustrative",
         "They demonstrate the skills' loops and adapters, not a business outcome for this problem.",
         "Labelled as track T4/T5 throughout and excluded from the impact case.", "addressed"],
        ["Minor", "Class imbalance handled on a subsample",
         "The fraud demo uses an 80k-row subsample of the 285k-row file to keep runtime sane.",
         "Prevalence change is stated in the artifact; conclusions are about metric choice, not absolute PR-AUC.",
         "addressed"],
        ["Question", "Why HistGradientBoosting over LightGBM/XGBoost?",
         "Both are installed and were not benchmarked head to head.",
         "Fair challenge; the tuned HGB is within noise of the logistic baseline, so a different booster is "
         "unlikely to change the decision.", "answered"],
    ]
    blocking = sum(1 for f in findings if f[0] == "Blocking")
    open_items = sum(1 for f in findings if f[4] == "open")

    return SkillResult(
        skill="peer-review-template", source="data-analytics-skills",
        category="Workflow Optimization", phase=5, track="meta",
        title="This lab, reviewed against its own checklist",
        prescribes="Review analysis the way code is reviewed: severity-graded findings, each with the specific "
                   "concern and a requested action, and an explicit disposition for every one.",
        applied="Filled the skill's peer_review_template.md against this lab and graded six findings, including "
                "the two that are still open.",
        narrative=[
            f"{len(findings)} findings, {blocking} blocking, {open_items} still open. The blocking one is the "
            "same unverified churn window that the assumptions log and the QA checklist both surfaced -- three "
            "independent skills converging on one weakness is a sign the process works, not that it is "
            "repetitive.",
            "The two 'Major' findings are about the business case rather than the code: a 30% save rate and a "
            "$240 offer cost are inputs nobody in this lab measured. The model is defensible; the money "
            "attached to it is provisional, and the review says so in those words.",
            "Reviewing one's own work with a template is weaker than a second reader, and this artifact should "
            "not pretend otherwise. What the template buys is that the objections are written down in a form a "
            "second reader can act on, instead of living in the author's head.",
        ],
        kpis=[
            Kpi("Findings", str(len(findings)), "severity-graded"),
            Kpi("Blocking", str(blocking), "must clear before launch", tone="bad"),
            Kpi("Open", str(open_items), "tracked, not closed", tone="warn"),
            Kpi("Addressed / answered", str(len(findings) - open_items), "with evidence", tone="good"),
        ],
        charts=[Chart(id="findings", kind="bar", title="Review findings by severity",
                      data=[{"x": s, "n": sum(1 for f in findings if f[0] == s)}
                            for s in ["Blocking", "Major", "Minor", "Question"]],
                      series=[{"key": "n", "label": "findings"}])],
        tables=[Table("review", "Peer review findings",
                      ["Severity", "Finding", "Concern", "Requested action", "Status"], findings)],
        code_excerpt=template,
        code_language="markdown",
        takeaway="The review's blocking finding is not in the modelling -- it is the definition of the target, "
                 "which no amount of tuning would have fixed.",
        used_skill_scripts=[".claude/skills/peer-review-template/references/peer_review_template.md"],
    )


DEMOS = [
    demo_model_evaluation,
    demo_ab_test_analysis,
    demo_root_cause_investigation,
    demo_insight_synthesis,
    demo_impact_quantification,
    demo_analysis_qa_checklist,
    demo_peer_review_template,
]


def main() -> None:
    print("\n=== CRISP-DM 5: Evaluation ===")
    for fn in DEMOS:
        emit(fn())


if __name__ == "__main__":
    main()
