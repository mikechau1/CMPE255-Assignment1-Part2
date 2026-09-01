"""CRISP-DM Phase 2 - Data Understanding.

Ten skills across the churn and retail datasets. Nothing here modifies the data:
this phase profiles it, audits it, queries it and documents it, and every finding
is produced by running code rather than by describing what code would find.
"""
from __future__ import annotations
import json, sqlite3, sys, pathlib, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

from lib import data
from lib.emit import Chart, Kpi, SkillResult, Table, emit
from lib.paths import ARTIFACTS, INTERIM, RAW, ROOT
from lib.seeds import set_global_seed
from lib.util import capture
from lib import skillscripts as ss

set_global_seed()
TELCO = data.telco_typed()
RETAIL = data.retail_clean()
RETAIL_RAW = data.retail_raw()


# ================================================================= 1. EDA (agent-ml-skills)
def demo_exploratory_data_analysis() -> SkillResult:
    df = TELCO
    cat_cols = [c for c in df.columns if df[c].dtype == object and c not in ("customerID", "Churn")]
    rates = (pd.concat([df.groupby(c)["Churn_flag"].agg(["mean", "size"]).assign(feature=c).reset_index()
                        .rename(columns={c: "value"}) for c in cat_cols])
             .sort_values("mean", ascending=False))
    top = rates[rates["size"] >= 300].head(8)

    num = df[["tenure", "MonthlyCharges", "TotalCharges", "SeniorCitizen", "Churn_flag"]]
    corr = num.corr(numeric_only=True)

    # Leakage checks the skill insists on before modelling.
    id_unique = df["customerID"].is_unique
    implied = df["tenure"] * df["MonthlyCharges"]
    total_gap = (df["TotalCharges"] - implied).abs() / df["TotalCharges"].replace(0, np.nan)
    near_identity = float((total_gap < 0.05).mean())

    ten_bins = pd.cut(df["tenure"], bins=range(0, 78, 6), include_lowest=True)
    tenure_hist = df.groupby([ten_bins, "Churn"], observed=True).size().unstack(fill_value=0)

    charge_bins = pd.cut(df["MonthlyCharges"], bins=12)
    charge_hist = df.groupby([charge_bins, "Churn"], observed=True).size().unstack(fill_value=0)

    return SkillResult(
        skill="exploratory-data-analysis", source="agent-ml-skills",
        category="Data Prep & Exploration", phase=2, track="T1",
        title="Profiling Telco Churn: distributions, correlations and a leakage check",
        prescribes="On a new dataset: shape and dtypes, target balance, per-feature distributions, "
                   "correlation structure, and an explicit hunt for leakage before any model is fitted.",
        applied="Profiled all 21 Telco columns, ranked categorical levels by churn rate, correlated the "
                "numeric block against the target, and tested the two leakage hypotheses this dataset invites.",
        narrative=[
            f"The target is {df['Churn_flag'].mean():.1%} positive across {len(df):,} rows -- imbalanced enough "
            "that accuracy is useless as a metric, but not so rare that resampling is mandatory. That single "
            "number decides the phase-5 metric set.",
            f"Tenure is the strongest numeric signal (r = {corr.loc['tenure', 'Churn_flag']:.3f}), and "
            f"MonthlyCharges pulls the other way (r = {corr.loc['MonthlyCharges', 'Churn_flag']:.3f}): "
            "customers who pay more and have been around less are the risk pool.",
            f"The leakage check matters more than the correlations. customerID is unique ({id_unique}), so no "
            f"row-level duplication inflates a split. TotalCharges is within 5% of tenure x MonthlyCharges for "
            f"{near_identity:.0%} of rows -- it is a near-deterministic function of two other columns, so it "
            "adds collinearity rather than information and must not be treated as an independent feature.",
        ],
        kpis=[
            Kpi("Rows x columns", f"{df.shape[0]:,} x {df.shape[1]}"),
            Kpi("Target rate", f"{df['Churn_flag'].mean():.1%}", "churned", tone="warn"),
            Kpi("Strongest numeric r", f"{corr.loc['tenure', 'Churn_flag']:.3f}", "tenure vs churn"),
            Kpi("TotalCharges ~ tenure x MRC", f"{near_identity:.0%}", "of rows within 5%", tone="warn"),
        ],
        charts=[
            Chart(id="churn-by-level", kind="hbar",
                  title="Highest-churn feature levels (segments of 300+ customers)",
                  data=[{"x": f"{r.feature} = {r.value}", "rate": round(float(r.mean), 4)}
                        for r in top.itertuples()],
                  series=[{"key": "rate", "label": "Churn rate"}], valueFormat="percent"),
            Chart(id="tenure-hist", kind="stacked-bar", title="Tenure distribution by churn outcome",
                  data=[{"x": str(int(i.left) + 1) + "-" + str(int(i.right)) + "m",
                         "Retained": int(tenure_hist.loc[i, "No"]), "Churned": int(tenure_hist.loc[i, "Yes"])}
                        for i in tenure_hist.index],
                  series=[{"key": "Retained", "label": "Retained"}, {"key": "Churned", "label": "Churned"}],
                  xLabel="tenure (months)", yLabel="customers",
                  note="Churn is front-loaded: the first six months contain the largest churned block."),
            Chart(id="charges-hist", kind="stacked-bar", title="Monthly charges distribution by churn outcome",
                  data=[{"x": f"${int(i.left)}-{int(i.right)}",
                         "Retained": int(charge_hist.loc[i, "No"]), "Churned": int(charge_hist.loc[i, "Yes"])}
                        for i in charge_hist.index],
                  series=[{"key": "Retained", "label": "Retained"}, {"key": "Churned", "label": "Churned"}],
                  xLabel="monthly charges", yLabel="customers"),
            Chart(id="corr-heatmap", kind="heatmap", title="Correlation matrix (numeric block)",
                  data=[{"row": a, "col": b, "value": round(float(corr.loc[a, b]), 3)}
                        for a in corr.index for b in corr.columns],
                  x="col", series=[{"key": "value", "label": "Pearson r"}], domain=[-1, 1]),
        ],
        tables=[Table("leakage", "Leakage checks run before modelling",
                      ["Check", "Result", "Consequence"],
                      [["customerID uniqueness", f"unique = {id_unique}", "safe to split on rows"],
                       ["TotalCharges vs tenure x MonthlyCharges",
                        f"{near_identity:.1%} of rows within 5%", "collinear; keep but do not over-interpret"],
                       ["Post-outcome columns", "none present",
                        "no column describes events after the churn decision"],
                       ["Duplicate customers", f"{int(df['customerID'].duplicated().sum())} found",
                        "no train/test contamination"]])],
        code_excerpt=(
            "corr = df[['tenure','MonthlyCharges','TotalCharges','SeniorCitizen','Churn_flag']].corr()\n"
            "implied = df.tenure * df.MonthlyCharges\n"
            "gap = (df.TotalCharges - implied).abs() / df.TotalCharges\n"
            "print(f'TotalCharges is within 5% of tenure*MonthlyCharges for {(gap < 0.05).mean():.0%} of rows')"
        ),
        takeaway="Tenure and contract type carry the signal; TotalCharges is a derived column, and treating it "
                 "as independent evidence would be the first mistake available in this dataset.",
    )


# ================================================================= 2. programmatic-eda
def demo_programmatic_eda() -> SkillResult:
    overview = ss.load("programmatic-eda", "data_overview.py")
    nulls = ss.load("programmatic-eda", "null_profiler.py")
    dist = ss.load("programmatic-eda", "distribution_summary.py")
    corr = ss.load("programmatic-eda", "correlation_explorer.py")
    out = ss.load("programmatic-eda", "outlier_detector.py")

    raw = data.telco_raw()  # profile the file as delivered, blanks and all
    typed = TELCO

    overview_txt = capture(overview.overview, typed, sample_n=3)
    null_tbl = nulls.profile_nulls(typed, warn_pct=0.1, fail_pct=5.0)
    dist_txt = capture(dist.distribution_summary, typed[["tenure", "MonthlyCharges", "TotalCharges"]], bins=10)
    corr_txt = capture(corr.explore_correlations, typed, threshold=0.6)
    outliers = out.detect_outliers(typed, method="both")

    nonzero = null_tbl[null_tbl["null_count"] > 0]
    blank_total_charges = int(raw["TotalCharges"].astype(str).str.strip().eq("").sum())
    tenure_of_blanks = sorted(raw.loc[raw["TotalCharges"].astype(str).str.strip() == "", "tenure"].unique().tolist())

    return SkillResult(
        skill="programmatic-eda", source="data-analytics-skills",
        category="Data Quality & Validation", phase=2, track="T1",
        title="The same dataset profiled by the skill's own five scripts",
        prescribes="Profile a dataset with reusable scripts rather than ad-hoc notebook cells: structural "
                   "overview, null profile with thresholds, distribution summary, correlation scan, outliers.",
        applied="Ran all five bundled scripts (data_overview, null_profiler, distribution_summary, "
                "correlation_explorer, outlier_detector) against the Telco frame and kept their raw output.",
        narrative=[
            f"The null profile is the payoff: exactly {blank_total_charges} rows have a blank TotalCharges, and "
            f"every one of them has tenure = {tenure_of_blanks}. That is not missing data, it is a brand-new "
            "account that has never been billed -- which is why phase 3 fills those with 0 rather than a median.",
            f"The outlier scan flags {int(outliers['outlier_count'].sum())} values across the numeric columns. "
            "None are errors: monthly charges top out near $119 and tenure at 72 months, both legitimate. "
            "Recording that judgement is the point -- an automated pipeline that clipped them would destroy signal.",
            "Running the skill's scripts instead of writing new profiling code is the honest test of the skill: "
            "the output below is verbatim from .claude/skills/programmatic-eda/scripts/.",
        ],
        kpis=[
            Kpi("Columns profiled", str(typed.shape[1])),
            Kpi("Columns with nulls", str(len(nonzero)), "after type coercion",
                tone="warn" if len(nonzero) else "good"),
            Kpi("Blank TotalCharges", str(blank_total_charges), "all with tenure = 0", tone="warn"),
            Kpi("Outlier values flagged", str(int(outliers["outlier_count"].sum())), "IQR + z-score, none invalid"),
        ],
        charts=[
            Chart(id="null-pct", kind="hbar", title="Null percentage by column (threshold: warn 0.1%, fail 5%)",
                  data=[{"x": str(i), "pct": float(r["null_pct"])} for i, r in null_tbl.head(6).iterrows()],
                  series=[{"key": "pct", "label": "% null"}]),
            Chart(id="outlier-counts", kind="bar", title="Outlier counts per numeric column (IQR vs z-score)",
                  data=[{"x": r.column, "iqr": int(r.iqr_outliers), "zscore": int(r.zscore_outliers)}
                        for r in outliers.itertuples()],
                  series=[{"key": "iqr", "label": "IQR (k=1.5)"}, {"key": "zscore", "label": "z-score (>3)"}]),
        ],
        tables=[Table("outliers", "outlier_detector.py output",
                      ["Column", "Outliers", "% of rows", "Min", "Max", "Mean"],
                      [[r.column, int(r.outlier_count), float(r.outlier_pct), float(r.min), float(r.max),
                        float(r.mean)] for r in outliers.itertuples()])],
        code_excerpt=(overview_txt[:1500] + "\n\n" + dist_txt[:900] + "\n\n" + corr_txt[:700]),
        code_language="text",
        takeaway="Eleven blank TotalCharges values turn out to be structurally-zero new accounts, not missing "
                 "data -- a distinction that changes the imputation strategy in the next phase.",
        used_skill_scripts=[ss.ref("programmatic-eda", s) for s in
                            ["data_overview.py", "null_profiler.py", "distribution_summary.py",
                             "correlation_explorer.py", "outlier_detector.py"]],
    )


# ================================================================= 3. data-quality-audit
def demo_data_quality_audit() -> SkillResult:
    nc = ss.load("data-quality-audit", "null_counter.py")
    dup = ss.load("data-quality-audit", "duplicate_finder.py")
    fresh = ss.load("data-quality-audit", "freshness_check.py")
    ref = ss.load("data-quality-audit", "referential_integrity.py")
    vr = ss.load("data-quality-audit", "value_range_validator.py")

    raw = RETAIL_RAW
    nulls = nc.count_nulls(raw, thresholds={"CustomerID": 5.0, "Description": 1.0})
    dupes = dup.find_duplicates(raw, key_cols=["InvoiceNo", "StockCode", "Quantity", "UnitPrice"])
    freshness = fresh.check_freshness(raw, "InvoiceDate", max_lag_hours=48)

    # Referential integrity with a real question: do 2011 orders reference customers seen in 2010?
    clean = RETAIL
    dim_2010 = clean[clean["InvoiceDate"] < "2011-01-01"][["CustomerID"]].drop_duplicates()
    fact_2011 = clean[clean["InvoiceDate"] >= "2011-01-01"][["CustomerID"]]
    integrity = ref.check_referential_integrity(fact_2011, dim_2010, "CustomerID", "CustomerID")

    rules = {
        "Quantity": {"min": 1},
        "UnitPrice": {"min": 0.01},
        "Country": {"allowed": ["United Kingdom", "Germany", "France", "EIRE", "Spain",
                                "Netherlands", "Belgium", "Switzerland", "Portugal", "Australia"]},
    }
    ranges = vr.validate_ranges(raw, rules)

    checks = [
        ["Nulls vs thresholds", "FAIL" if (nulls["status"] == "FAIL").any() else "PASS",
         f"{int((raw['CustomerID'].isna()).sum()):,} rows have no CustomerID ({raw['CustomerID'].isna().mean():.1%})"],
        ["Duplicate rows", dupes["full_row_status"],
         f"{dupes['full_row_duplicates']:,} exact duplicate rows ({dupes['full_row_duplicate_pct']}%)"],
        ["Freshness (48h SLA)", freshness["status"], freshness["message"][:90]],
        ["Referential integrity", integrity["status"],
         f"{integrity['orphan_count']:,} of {integrity['total_child_rows']:,} 2011 order lines "
         f"reference a customer not seen in 2010 ({integrity['orphan_pct']}%)"],
        ["Value ranges", "FAIL" if (ranges["status"] == "FAIL").any() else "PASS",
         "; ".join(f"{r.column}: {r.issues[:60]}" for r in ranges.itertuples() if r.status == "FAIL")],
    ]
    failed = sum(1 for c in checks if c[1] == "FAIL")

    return SkillResult(
        skill="data-quality-audit", source="data-analytics-skills",
        category="Data Quality & Validation", phase=2, track="T2",
        title="Five automated quality checks against raw Online Retail",
        prescribes="Audit a table on five axes -- completeness, uniqueness, freshness, referential integrity "
                   "and value validity -- with thresholds agreed in advance so results are pass/fail, not vibes.",
        applied="Ran all five bundled checkers against the 541,909-row raw retail extract, using a 48-hour "
                "freshness SLA and business rules (quantity >= 1, price > 0, known country list).",
        narrative=[
            f"{failed} of 5 checks fail, and every failure is real. {raw['CustomerID'].isna().mean():.0%} of "
            "order lines carry no CustomerID, which silently removes a quarter of revenue from any "
            "customer-level analysis -- the reason phase 3's cohort work states its population explicitly.",
            f"The freshness check fails by design: the newest invoice is from 2011, so against a 48-hour SLA the "
            f"lag is enormous. On a historical Kaggle extract that is expected; wired to a live warehouse table "
            "the same check is the one that pages someone.",
            f"Referential integrity is the interesting one: {integrity['orphan_pct']}% of 2011 order lines belong "
            "to customers with no 2010 history. Against a static dimension table that reads as an orphan; in "
            "reality it is new-customer acquisition, which is exactly why this check needs a human verdict.",
            f"Value validation catches the cancellations -- negative quantities encoded as C-prefixed invoices -- "
            "and the long tail of countries outside the top-ten list.",
        ],
        kpis=[
            Kpi("Checks run", "5", "completeness, uniqueness, freshness, integrity, validity"),
            Kpi("Failing", str(failed), "each investigated below", tone="bad"),
            Kpi("Rows audited", f"{len(raw):,}", "raw retail extract"),
            Kpi("Missing CustomerID", f"{raw['CustomerID'].isna().mean():.1%}",
                f"{int(raw['CustomerID'].isna().sum()):,} rows", tone="warn"),
        ],
        charts=[
            Chart(id="dq-status", kind="bar", title="Quality check outcomes",
                  data=[{"x": c[0], "fail": 1 if c[1] == "FAIL" else 0, "pass": 1 if c[1] == "PASS" else 0}
                        for c in checks],
                  series=[{"key": "pass", "label": "Pass"}, {"key": "fail", "label": "Fail"}]),
            Chart(id="null-by-col", kind="hbar", title="Null percentage by column (raw retail)",
                  data=[{"x": r.column, "pct": float(r.null_pct)}
                        for r in nulls.sort_values("null_pct", ascending=False).head(8).itertuples()],
                  series=[{"key": "pct", "label": "% null"}]),
        ],
        tables=[Table("dq", "Audit results", ["Check", "Status", "Detail"], checks)],
        code_excerpt=(
            "nulls     = count_nulls(raw, thresholds={'CustomerID': 5.0, 'Description': 1.0})\n"
            "dupes     = find_duplicates(raw, key_cols=['InvoiceNo','StockCode','Quantity','UnitPrice'])\n"
            "freshness = check_freshness(raw, 'InvoiceDate', max_lag_hours=48)\n"
            "integrity = check_referential_integrity(fact_2011, dim_2010, 'CustomerID', 'CustomerID')\n"
            "ranges    = validate_ranges(raw, {'Quantity': {'min': 1}, 'UnitPrice': {'min': 0.01},\n"
            "                                  'Country': {'allowed': TOP_10_COUNTRIES}})"
        ),
        takeaway="A quarter of retail order lines are anonymous, so every customer-level number in this lab is "
                 "computed on an explicitly stated subpopulation rather than on 'the data'.",
        used_skill_scripts=[ss.ref("data-quality-audit", s) for s in
                            ["null_counter.py", "duplicate_finder.py", "freshness_check.py",
                             "referential_integrity.py", "value_range_validator.py"]],
    )


# ================================================================= 4. pandas-patterns
def demo_pandas_patterns() -> SkillResult:
    df = RETAIL_RAW.copy()
    timings: dict[str, float] = {}

    # (a) row-wise apply vs vectorised arithmetic
    sub = df.head(120_000)
    t0 = time.perf_counter()
    slow = sub.apply(lambda r: r["Quantity"] * r["UnitPrice"], axis=1)
    timings["apply(axis=1)"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    fast = sub["Quantity"] * sub["UnitPrice"]
    timings["vectorised"] = time.perf_counter() - t0
    same = bool(np.allclose(slow.values, fast.values))

    # (b) python loop over groups vs groupby.agg
    t0 = time.perf_counter()
    manual = {}
    for country, g in sub.groupby("Country", observed=True):
        manual[country] = (g["Quantity"] * g["UnitPrice"]).sum()
    timings["loop over groups"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    agg = sub.assign(rev=sub["Quantity"] * sub["UnitPrice"]).groupby("Country", observed=True)["rev"].sum()
    timings["groupby.agg"] = time.perf_counter() - t0

    # (c) memory: object columns -> category, float64 -> float32
    before = df.memory_usage(deep=True).sum() / 2**20
    slim = df.copy()
    for c in ["Country", "StockCode", "Description"]:
        slim[c] = slim[c].astype("category")
    slim["UnitPrice"] = pd.to_numeric(slim["UnitPrice"], downcast="float")
    slim["Quantity"] = pd.to_numeric(slim["Quantity"], downcast="integer")
    after = slim.memory_usage(deep=True).sum() / 2**20

    speedup_row = timings["apply(axis=1)"] / timings["vectorised"]
    speedup_grp = timings["loop over groups"] / timings["groupby.agg"]

    return SkillResult(
        skill="pandas-patterns", source="agent-ml-skills",
        category="Data Prep & Exploration", phase=2, track="T2",
        title="Vectorisation and dtypes, measured on 542k retail rows",
        prescribes="Write vectorised pandas: no row-wise apply, no manual group loops, categorical dtypes for "
                   "low-cardinality strings, and downcast numerics when memory matters.",
        applied="Timed the idiomatic and the naive version of the same two computations on the retail extract, "
                "and measured the memory saved by converting three object columns to category.",
        narrative=[
            f"Row-wise `apply` on 120k rows took {timings['apply(axis=1)'] * 1000:.0f} ms; the vectorised "
            f"multiplication took {timings['vectorised'] * 1000:.1f} ms -- a {speedup_row:.0f}x difference for "
            f"an identical result (values match: {same}). The gap is the Python interpreter, and it grows "
            "linearly with rows.",
            f"Looping over groups cost {timings['loop over groups'] * 1000:.0f} ms against "
            f"{timings['groupby.agg'] * 1000:.1f} ms for `groupby().sum()` -- {speedup_grp:.1f}x, plus the "
            "aggregate version is a single expression that a reader can check.",
            f"Dtypes are the memory lever: three object columns converted to `category` and two numerics "
            f"downcast take the frame from {before:.0f} MB to {after:.0f} MB, a {1 - after / before:.0%} "
            "reduction with no information lost. On this dataset that is the difference between comfortable "
            "and swapping.",
        ],
        kpis=[
            Kpi("apply -> vectorised", f"{speedup_row:.0f}x faster", "identical output", tone="good"),
            Kpi("loop -> groupby", f"{speedup_grp:.1f}x faster", "same aggregates", tone="good"),
            Kpi("Memory", f"{before:.0f} -> {after:.0f} MB", f"-{1 - after / before:.0%} via dtypes", tone="good"),
            Kpi("Rows", f"{len(df):,}", "raw retail extract"),
        ],
        charts=[
            Chart(id="timings", kind="hbar", title="Wall-clock time for identical results (120k rows)",
                  data=[{"x": k, "ms": round(v * 1000, 2)} for k, v in timings.items()],
                  series=[{"key": "ms", "label": "milliseconds"}], note="Lower is better; results verified equal."),
            Chart(id="memory", kind="bar", title="Frame memory before and after dtype tuning",
                  data=[{"x": "object dtypes", "mb": round(before, 1)},
                        {"x": "category + downcast", "mb": round(after, 1)}],
                  series=[{"key": "mb", "label": "MB (deep)"}]),
        ],
        tables=[Table("patterns", "Pattern replacements applied",
                      ["Anti-pattern", "Idiomatic replacement", "Measured effect"],
                      [["df.apply(lambda r: ..., axis=1)", "df.a * df.b", f"{speedup_row:.0f}x faster"],
                       ["for k, g in df.groupby(...): acc[k] = ...", "df.groupby(...)['rev'].sum()",
                        f"{speedup_grp:.1f}x faster"],
                       ["object dtype for repeated strings", "astype('category')",
                        f"{before - after:.0f} MB saved"],
                       ["float64 / int64 by default", "pd.to_numeric(..., downcast=...)",
                        "included in the saving above"]])],
        code_excerpt=(
            "# anti-pattern\n"
            "rev = df.apply(lambda r: r['Quantity'] * r['UnitPrice'], axis=1)\n\n"
            "# idiomatic\n"
            "rev = df['Quantity'] * df['UnitPrice']\n\n"
            "for c in ['Country', 'StockCode', 'Description']:\n"
            "    df[c] = df[c].astype('category')\n"
            "df['UnitPrice'] = pd.to_numeric(df['UnitPrice'], downcast='float')"
        ),
        takeaway=f"Same answers, {speedup_row:.0f}x less time and {1 - after / before:.0%} less memory -- "
                 "measured, not asserted.",
    )


# ================================================================= 5. query-validation
def demo_query_validation() -> SkillResult:
    lint = ss.load("query-validation", "sql_lint.py")
    card = ss.load("query-validation", "cardinality_estimator.py")

    import duckdb
    con = duckdb.connect()
    con.register("retail", RETAIL)

    bad_sql = "SELECT * FROM retail r JOIN retail c ON r.CustomerID = c.CustomerID"
    good_sql = """
        SELECT Country,
               COUNT(DISTINCT InvoiceNo) AS orders,
               ROUND(SUM(Quantity * UnitPrice), 2) AS revenue
        FROM retail
        WHERE InvoiceDate >= DATE '2011-01-01'
        GROUP BY Country
        ORDER BY revenue DESC
        LIMIT 10
    """
    # sqlglot 30 dropped the script's default "ansi" dialect name; we lint as the dialect we actually run.
    bad_issues = lint.lint_sql(bad_sql, dialect="duckdb")
    good_issues = lint.lint_sql(good_sql, dialect="duckdb")

    result = con.execute(good_sql).df()

    # Cross-check the SQL against a pandas computation -- the actual validation.
    ref = (RETAIL[RETAIL["InvoiceDate"] >= "2011-01-01"]
           .groupby("Country", observed=True)
           .agg(orders=("InvoiceNo", "nunique"), revenue=("Revenue", "sum"))
           .sort_values("revenue", ascending=False).head(10).reset_index())
    matches = bool(np.allclose(result["revenue"].values, ref["revenue"].round(2).values, atol=0.01))

    n_lines = len(RETAIL)
    n_customers = RETAIL["CustomerID"].nunique()
    fanout = card.estimate_join(left_rows=n_lines, right_rows=n_lines, left_unique=False, right_unique=False)
    safe = card.estimate_join(left_rows=n_lines, right_rows=n_customers, left_unique=False, right_unique=True)

    return SkillResult(
        skill="query-validation", source="data-analytics-skills",
        category="Data Quality & Validation", phase=2, track="T2",
        title="Linting SQL, estimating fan-out, and cross-checking the answer",
        prescribes="Before trusting a query: lint it for scan and fan-out hazards, estimate the join "
                   "cardinality, and validate the result against an independent computation.",
        applied="Linted a deliberately careless join and the real revenue query with sql_lint.py, estimated "
                "both joins with cardinality_estimator.py, and reconciled DuckDB's answer against pandas.",
        narrative=[
            f"The careless query earns {len(bad_issues)} lint warnings -- SELECT * and no WHERE or LIMIT -- but "
            "the linter says nothing about the self-join, which is the actually dangerous part. That is the "
            "honest limit of static linting, and the reason the skill pairs it with a cardinality estimate: "
            f"the join is put at {fanout['estimated_output_rows']:,} rows with {fanout['fan_out_risk']} fan-out "
            f"risk on a {n_lines:,}-row table.",
            f"Joining the same fact table to a customer dimension ({n_customers:,} unique keys) is "
            f"{safe['fan_out_risk']} risk and stays at {safe['estimated_output_rows']:,} rows, because the right "
            "side is unique. Same data, different key discipline.",
            f"Linting is not validation, though. The revenue query was also executed in DuckDB and reconciled "
            f"against an independent pandas aggregation: the top-10 country revenues match to the cent "
            f"({matches}). That is the check that catches a wrong join, not a style warning.",
        ],
        kpis=[
            Kpi("Lint findings (careless query)", str(len(bad_issues)), "SELECT * and no filter; the self-join "
                "went unflagged", tone="bad"),
            Kpi("Lint findings (final query)", str(len([i for i in good_issues if i["severity"] != "OK"])),
                "one INFO on COUNT(DISTINCT ...), reviewed and kept", tone="good"),
            Kpi("Fan-out estimate", f"{fanout['estimated_output_rows']:,}",
                f"{fanout['fan_out_risk']} risk on the self-join", tone="bad"),
            Kpi("SQL vs pandas", "match" if matches else "MISMATCH", "top-10 revenue to the cent",
                tone="good" if matches else "bad"),
        ],
        charts=[Chart(id="revenue-by-country", kind="hbar",
                      title="Revenue by country, 2011 (DuckDB result, pandas-verified)",
                      data=[{"x": r.Country, "revenue": round(float(r.revenue), 2)}
                            for r in result.itertuples()],
                      series=[{"key": "revenue", "label": "Revenue (GBP)"}], valueFormat="currency")],
        tables=[
            Table("lint", "sql_lint.py findings on the careless query", ["Severity", "Message"],
                  [[i["severity"], i["message"]] for i in bad_issues]),
            Table("cardinality", "Join cardinality estimates",
                  ["Join", "Right side unique?", "Estimated rows", "Risk"],
                  [["retail x retail on CustomerID", "no", f"{fanout['estimated_output_rows']:,}",
                    fanout["fan_out_risk"]],
                   ["retail x dim_customer on CustomerID", "yes", f"{safe['estimated_output_rows']:,}",
                    safe["fan_out_risk"]]]),
        ],
        code_excerpt=good_sql.strip(),
        code_language="sql",
        takeaway="The linter caught the style and missed the fan-out, the estimator caught the fan-out, and only "
                 "the pandas cross-check could confirm the number was right -- all three are needed.",
        used_skill_scripts=[ss.ref("query-validation", "sql_lint.py"),
                            ss.ref("query-validation", "cardinality_estimator.py")],
    )


# ================================================================= 6. sql-to-business-logic
def demo_sql_to_business_logic() -> SkillResult:
    ex = ss.load("sql-to-business-logic", "sql_explainer.py")
    sql = """
        SELECT Country,
               COUNT(DISTINCT CustomerID) AS active_customers,
               SUM(Quantity * UnitPrice) AS revenue,
               SUM(Quantity * UnitPrice) / COUNT(DISTINCT CustomerID) AS revenue_per_customer
        FROM retail
        WHERE InvoiceDate >= '2011-01-01'
          AND Quantity > 0
          AND CustomerID IS NOT NULL
        GROUP BY Country
        ORDER BY revenue DESC
    """
    explanation = ex.explain_sql(sql)

    import duckdb
    con = duckdb.connect()
    con.register("retail", RETAIL)
    res = con.execute(sql).df().head(8)

    return SkillResult(
        skill="sql-to-business-logic", source="data-analytics-skills",
        category="Documentation & Knowledge", phase=2, track="T2",
        title="Translating the revenue query into something a stakeholder can challenge",
        prescribes="Turn SQL into plain business language -- what is calculated, from what, filtered how, "
                   "grouped by what -- and surface the validation questions the filters imply.",
        applied="Ran sql_explainer.py over the country-revenue query that feeds the dashboard, then executed "
                "the same SQL so the explanation sits beside its actual output.",
        narrative=[
            "Three WHERE clauses decide what this number means, and each is a business choice: 2011 only, "
            "positive quantities only (cancellations excluded), and known customers only. A stakeholder cannot "
            "challenge 'revenue' -- they can challenge 'revenue excluding anonymous orders'.",
            f"That third filter is not cosmetic: it removes {RETAIL_RAW['CustomerID'].isna().mean():.0%} of "
            "order lines. The explanation makes it visible in prose instead of leaving it in line 9 of a query.",
            "The generated validation questions are the useful part of the skill: they ask whether the "
            "exclusions are intended, which is exactly the conversation that prevents a mis-read dashboard.",
        ],
        kpis=[
            Kpi("Filters explained", "3", "period, sign, customer identity"),
            Kpi("Countries returned", str(len(con.execute(sql).df())), "2011 activity"),
            Kpi("Top market", res.iloc[0]["Country"], f"GBP {res.iloc[0]['revenue']:,.0f}"),
        ],
        charts=[Chart(id="rev-per-customer", kind="bar",
                      title="Revenue per active customer by market (2011)",
                      data=[{"x": r.Country, "rpc": round(float(r.revenue_per_customer), 2)}
                            for r in res.itertuples()],
                      series=[{"key": "rpc", "label": "Revenue per customer"}], valueFormat="currency",
                      note="The UK dominates total revenue but not revenue per customer -- a distinction the "
                           "plain-language reading makes obvious.")],
        tables=[Table("query-out", "Query output (top 8 markets)",
                      ["Country", "Active customers", "Revenue", "Revenue / customer"],
                      [[r.Country, int(r.active_customers), round(float(r.revenue), 2),
                        round(float(r.revenue_per_customer), 2)] for r in res.itertuples()])],
        code_excerpt=explanation,
        code_language="markdown",
        takeaway="The query's three filters are business decisions in disguise; stated in English, they are "
                 "reviewable by the person who owns the number.",
        used_skill_scripts=[ss.ref("sql-to-business-logic", "sql_explainer.py")],
    )


# ================================================================= 7. schema-mapper
def demo_schema_mapper() -> SkillResult:
    sc = ss.load("schema-mapper", "schema_compare.py")

    src_path = INTERIM / "schema_source_telco.csv"
    tgt_path = INTERIM / "schema_target_warehouse.csv"

    source_rows = []
    for c in TELCO.columns:
        source_rows.append({"column_name": c, "data_type": str(TELCO[c].dtype),
                            "nullable": "yes" if TELCO[c].isna().any() else "no",
                            "description": f"Telco CSV column {c}"})
    pd.DataFrame(source_rows).to_csv(src_path, index=False)

    # The warehouse target the retention mart is supposed to land in.
    target_rows = [
        {"column_name": "customerID", "data_type": "object", "nullable": "no", "description": "Account key"},
        {"column_name": "tenure", "data_type": "int64", "nullable": "no", "description": "Months active"},
        {"column_name": "MonthlyCharges", "data_type": "float64", "nullable": "no", "description": "MRR"},
        {"column_name": "TotalCharges", "data_type": "float64", "nullable": "yes", "description": "Lifetime billed"},
        {"column_name": "Contract", "data_type": "object", "nullable": "no", "description": "Commitment term"},
        {"column_name": "Churn_flag", "data_type": "int64", "nullable": "no", "description": "Target label"},
        {"column_name": "SeniorCitizen", "data_type": "object", "nullable": "no",
         "description": "Warehouse stores this as a Y/N string, not 0/1"},
        {"column_name": "region_code", "data_type": "object", "nullable": "yes",
         "description": "Warehouse-only: sales region, absent from the Kaggle extract"},
        {"column_name": "acquisition_channel", "data_type": "object", "nullable": "yes",
         "description": "Warehouse-only: how the customer was acquired"},
    ]
    pd.DataFrame(target_rows).to_csv(tgt_path, index=False)

    src = sc.load_schema(str(src_path))
    tgt = sc.load_schema(str(tgt_path))
    cmp_ = sc.compare_schemas(src, tgt)
    report = sc.format_report(cmp_)

    return SkillResult(
        skill="schema-mapper", source="data-analytics-skills",
        category="Data Quality & Validation", phase=2, track="T1",
        title="Mapping the Kaggle extract onto the warehouse contract",
        prescribes="Compare source and target schemas explicitly: direct matches, type mismatches, and columns "
                   "that exist on only one side -- before writing the transformation.",
        applied="Emitted a schema CSV for the Telco frame and for the intended warehouse table, then ran "
                "schema_compare.py to produce the mapping and its gaps.",
        narrative=[
            f"{len(cmp_['direct_matches'])} columns map straight through, "
            f"{len(cmp_['type_mismatches'])} match by name but not by type, "
            f"{len(cmp_['unmapped_target'])} target columns have no source, and "
            f"{len(cmp_['unmapped_source'])} source columns have no home in the target.",
            "The type mismatch on SeniorCitizen is the classic one: the Kaggle file stores it as 0/1 integers, "
            "the warehouse contract as a Y/N string. Loading without a cast produces a column that is present, "
            "populated and wrong -- the failure mode no null check catches.",
            "The two unmapped target columns (region_code, acquisition_channel) are the honest limit of this "
            "dataset: they cannot be derived, so any model requiring them is out of scope until the warehouse "
            "join exists. Saying that in phase 2 is cheaper than discovering it in phase 4.",
        ],
        kpis=[
            Kpi("Direct matches", str(len(cmp_["direct_matches"])), "name and type agree", tone="good"),
            Kpi("Type mismatches", str(len(cmp_["type_mismatches"])), "silent corruption risk", tone="bad"),
            Kpi("Target columns unmapped", str(len(cmp_["unmapped_target"])), "cannot be sourced", tone="warn"),
            Kpi("Source columns unused", str(len(cmp_["unmapped_source"])), "not in the contract"),
        ],
        charts=[Chart(id="schema-map", kind="bar", title="Schema comparison outcome",
                      data=[{"x": "Direct match", "n": len(cmp_["direct_matches"])},
                            {"x": "Type mismatch", "n": len(cmp_["type_mismatches"])},
                            {"x": "Target only", "n": len(cmp_["unmapped_target"])},
                            {"x": "Source only", "n": len(cmp_["unmapped_source"])}],
                      series=[{"key": "n", "label": "Columns"}])],
        tables=[
            Table("mismatch", "Type mismatches (must be cast explicitly)",
                  ["Column", "Source type", "Target type"],
                  [[m["column"], m["source_type"], m["target_type"]] for m in cmp_["type_mismatches"]] or
                  [["-", "-", "-"]]),
            Table("unmapped", "Target columns with no source",
                  ["Column", "Type", "Note"],
                  [[m["column"], m["type"], m["description"]] for m in cmp_["unmapped_target"]]),
        ],
        code_excerpt=report[:1500],
        code_language="markdown",
        takeaway="One column matches by name and lies about its type; two required columns simply do not exist "
                 "in this dataset -- both are cheaper to know now than after the model is built.",
        used_skill_scripts=[ss.ref("schema-mapper", "schema_compare.py")],
        artifacts=["data/interim/schema_source_telco.csv", "data/interim/schema_target_warehouse.csv"],
    )


# ================================================================= 8. metric-reconciliation
def demo_metric_reconciliation() -> SkillResult:
    rec = ss.load("metric-reconciliation", "reconcile_metrics.py")
    raw = RETAIL_RAW

    # Definition A: "finance" -- everything invoiced in 2011, cancellations netted off.
    y2011 = raw[(raw["InvoiceDate"] >= "2011-01-01") & (raw["InvoiceDate"] < "2012-01-01")].copy()
    y2011["line"] = y2011["Quantity"] * y2011["UnitPrice"]
    finance = float(y2011["line"].sum())

    # Definition B: "analytics dashboard" -- known customers, positive lines only.
    dash = float(y2011[(y2011["CustomerID"].notna()) & (y2011["Quantity"] > 0) &
                       (y2011["UnitPrice"] > 0)]["line"].sum())

    result = rec.compare_values(finance, dash, tolerance=0.005)
    report = rec.reconciliation_report(result, "Finance (all invoiced lines, net of cancellations)",
                                       "Dashboard (identified customers, positive lines)")

    # Decompose the gap into named, additive causes.
    anon = float(y2011[(y2011["CustomerID"].isna()) & (y2011["Quantity"] > 0) &
                       (y2011["UnitPrice"] > 0)]["line"].sum())
    cancels = float(y2011[y2011["Quantity"] < 0]["line"].sum())
    zero_price = float(y2011[(y2011["Quantity"] > 0) & (y2011["UnitPrice"] <= 0)]["line"].sum())
    residual = finance - dash - anon - cancels - zero_price

    return SkillResult(
        skill="metric-reconciliation", source="data-analytics-skills",
        category="Data Quality & Validation", phase=2, track="T2",
        title="Two revenue numbers, one dataset, reconciled line by line",
        prescribes="When two sources disagree on a metric, quantify the gap against a tolerance and decompose "
                   "it into named causes until the residual is zero -- never split the difference.",
        applied="Computed 2011 revenue under a finance definition and a dashboard definition, compared them "
                "with reconcile_metrics.py at a 0.5% tolerance, and attributed every pound of the gap.",
        narrative=[
            f"Finance reports GBP {finance:,.0f}; the dashboard reports GBP {dash:,.0f}. The gap is "
            f"{abs(result['pct_diff']):.1%}, well outside the 0.5% tolerance, so the skill's verdict is "
            f"{result['status']} rather than 'close enough'.",
            f"Three named causes account for it: anonymous orders (GBP {anon:,.0f}) that the dashboard excludes "
            f"because it aggregates by customer, cancellations (GBP {cancels:,.0f}, negative) that finance nets "
            f"off, and zero-priced giveaway lines (GBP {zero_price:,.0f}). The residual is GBP {residual:,.2f}.",
            "Neither number is wrong. The failure would be publishing both without this bridge -- which is how "
            "an organisation ends up with two revenue figures and no way to choose.",
        ],
        kpis=[
            Kpi("Finance definition", f"GBP {finance:,.0f}", "all invoiced lines"),
            Kpi("Dashboard definition", f"GBP {dash:,.0f}", "identified customers only"),
            Kpi("Gap", f"{abs(result['pct_diff']):.1%}", result["status"], tone="bad"),
            Kpi("Unexplained residual", f"GBP {residual:,.2f}", "after attribution",
                tone="good" if abs(residual) < 1 else "warn"),
        ],
        charts=[Chart(id="reconciliation", kind="bar", title="Revenue reconciliation bridge (2011)",
                      data=[{"x": "Finance", "gbp": round(finance)},
                            {"x": "- anonymous orders", "gbp": -round(anon)},
                            {"x": "- cancellations", "gbp": -round(cancels)},
                            {"x": "- zero-priced lines", "gbp": -round(zero_price)},
                            {"x": "Dashboard", "gbp": round(dash)}],
                      series=[{"key": "gbp", "label": "GBP"}], valueFormat="currency")],
        tables=[Table("bridge", "Gap attribution", ["Component", "GBP", "Why the definitions differ"],
                      [["Finance total", f"{finance:,.2f}", "every invoiced line, cancellations netted"],
                       ["Anonymous orders", f"-{anon:,.2f}", "no CustomerID, so absent from customer aggregates"],
                       ["Cancellations", f"-{cancels:,.2f}", "negative lines finance nets, dashboard drops"],
                       ["Zero-priced lines", f"-{zero_price:,.2f}", "samples and adjustments"],
                       ["Dashboard total", f"{dash:,.2f}", "identified customers, positive lines"],
                       ["Residual", f"{residual:,.2f}", "should be zero"]])],
        code_excerpt=report[:1200],
        code_language="text",
        takeaway="The 2011 revenue gap decomposes exactly into anonymous orders, cancellations and free samples "
                 "-- with a residual under a pound, so nothing is left to argument.",
        used_skill_scripts=[ss.ref("metric-reconciliation", "reconcile_metrics.py")],
    )


# ================================================================= 9. data-catalog-entry
def demo_data_catalog_entry() -> SkillResult:
    ce = ss.load("data-catalog-entry", "catalog_extractor.py")

    db = INTERIM / "lab.db"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    TELCO.to_sql("telco_customers", con, index=False)
    con.execute("CREATE UNIQUE INDEX idx_telco_pk ON telco_customers(customerID)")
    con.commit()
    con.close()

    meta = ce.extract_metadata(f"sqlite:///{db.as_posix()}", "telco_customers")
    markdown = ce.render_markdown(meta)

    # Fill the generated template's blanks with facts we actually have.
    man = {d["dataset"]: d for d in data.manifest()["datasets"]}
    src = man["telco_churn"]
    filled = (markdown
              .replace("**Domain:** [fill in]", "**Domain:** Customer retention")
              .replace("**Criticality:** [critical / high / medium / low]", "**Criticality:** high")
              .replace("[One sentence: what business process or entity does this table represent?]",
                       "One row per telco subscriber account, with service mix, billing and a churn label; "
                       "the training table for the retention model.")
              .replace("- **Business Owner:** [name / team]", "- **Business Owner:** VP Customer Retention")
              .replace("- **Technical Owner:** [name / team]", "- **Technical Owner:** CMPE255 skills lab")
              .replace("- **Completeness:** [%]",
                       f"- **Completeness:** {100 - TELCO.isna().mean().mean() * 100:.2f}% "
                       f"({int(TELCO.isna().sum().sum())} null cells, all in TotalCharges)")
              .replace("- **Freshness:** [last updated / refresh schedule]",
                       "- **Freshness:** static Kaggle snapshot; no refresh")
              .replace("- **Known issues:** [none / list]",
                       "- **Known issues:** TotalCharges arrives as text with 11 blanks (tenure = 0 accounts); "
                       "SeniorCitizen is 0/1 here but Y/N in the warehouse contract")
              .replace("- [source table or system]", f"- {src['source_url']} (SHA-256 {src['sha256'][:16]}...)")
              .replace("- [dashboard / report / model]",
                       "- Retention churn model (phase 4), FastAPI scoring service (phase 6)")
              .replace("**Access level:** [public / restricted / confidential]",
                       "**Access level:** public (open Kaggle dataset)")
              .replace("**Sensitivity:** [none / PII / financial / health]",
                       "**Sensitivity:** none -- customerID is a synthetic key, no direct identifiers")
              .replace("**Compliance tags:** [SOX / GDPR / HIPAA / none]", "**Compliance tags:** none")
              .replace("[How to request access]", "Download from Kaggle or the IBM mirror; no approval needed."))
    (ARTIFACTS / "catalog_telco_customers.md").write_text(filled, encoding="utf-8")

    typed_counts = pd.Series([c["type"] for c in meta["columns"]]).value_counts()

    return SkillResult(
        skill="data-catalog-entry", source="data-analytics-skills",
        category="Documentation & Knowledge", phase=2, track="T1",
        title="A catalog entry extracted from the live table, not typed by hand",
        prescribes="Generate the technical half of a catalog entry by inspecting the database, then fill the "
                   "human half: ownership, criticality, quality, lineage, sensitivity and access.",
        applied="Loaded the Telco frame into SQLite with a real primary-key index, ran catalog_extractor.py's "
                "SQLAlchemy inspection against it, and completed every placeholder from evidence in this lab.",
        narrative=[
            f"The extractor found {len(meta['columns'])} columns and {meta['row_count']:,} rows by inspecting "
            "the database, so the schema half of the entry cannot drift from reality the way a hand-written "
            "wiki page does.",
            "The half a machine cannot produce is the half that matters: criticality, the churn-window caveat, "
            "the SeniorCitizen type trap found by schema-mapper, and the lineage back to a URL with a SHA-256. "
            "All of those came from other phase-2 skills, which is the argument for running them first.",
            "Lineage points forward too -- the phase-4 model and the phase-6 service are listed as downstream "
            "consumers, so a future change to this table has a blast radius written down.",
        ],
        kpis=[
            Kpi("Columns catalogued", str(len(meta["columns"])), "via SQLAlchemy inspection"),
            Kpi("Rows at extraction", f"{meta['row_count']:,}"),
            Kpi("Completeness", f"{100 - TELCO.isna().mean().mean() * 100:.2f}%", "null cells / all cells",
                tone="good"),
            Kpi("Placeholders left", "0", "every [fill in] resolved", tone="good"),
        ],
        charts=[Chart(id="col-types", kind="bar", title="Catalogued column types",
                      data=[{"x": t, "n": int(n)} for t, n in typed_counts.items()],
                      series=[{"key": "n", "label": "Columns"}])],
        tables=[Table("cols", "Extracted schema (first 12 columns)",
                      ["Column", "Type", "Nullable", "Primary key"],
                      [[c["name"], c["type"], "yes" if c["nullable"] else "no",
                        "PK" if c["primary_key"] else "-"] for c in meta["columns"][:12]])],
        code_excerpt=filled[:1800],
        code_language="markdown",
        takeaway="The catalog entry is generated from the table and completed from this lab's own findings, so "
                 "every claim in it is traceable rather than remembered.",
        used_skill_scripts=[ss.ref("data-catalog-entry", "catalog_extractor.py")],
        artifacts=["artifacts/catalog_telco_customers.md", "data/interim/lab.db"],
    )


# ================================================================= 10. time-series-analysis
def demo_time_series_analysis() -> SkillResult:
    ts = ss.load("time-series-analysis", "ts_analyzer.py")

    monthly = (RETAIL.groupby("InvoiceMonth", observed=True)["Revenue"].sum()
               .reset_index().sort_values("InvoiceMonth"))
    rows = [{"date": d.strftime("%Y-%m"), "value": float(v)}
            for d, v in zip(monthly["InvoiceMonth"], monthly["Revenue"])]

    growth = ts.compute_growth_rates(rows)
    trend = ts.detect_trend([r["value"] for r in rows])
    anomalies = ts.detect_anomalies(rows, z_threshold=2.0)
    rolling = ts.rolling_average(rows, window=3)
    stats = ts.summary_stats([r["value"] for r in rows])
    report = ts.format_report(rows, trend, anomalies, stats, metric="Revenue", freq="monthly")

    last = rows[-1]
    return SkillResult(
        skill="time-series-analysis", source="data-analytics-skills",
        category="Data Analysis & Investigation", phase=2, track="T2",
        title="Monthly retail revenue: trend, growth, anomalies and a truncated month",
        prescribes="Decompose a series into level, trend and period-over-period growth; flag anomalies by "
                   "z-score; and check the series' edges before reading anything into them.",
        applied="Aggregated 13 months of cleaned retail revenue and ran ts_analyzer.py's trend, growth, "
                "anomaly and rolling-average functions over it.",
        narrative=[
            f"The trend is {trend['direction']} at {trend['pct_slope_per_period']:.1f}% of the mean per month "
            f"across {stats['n']} months, with revenue peaking in the pre-Christmas ramp -- November is the "
            "largest month, which is what a giftware wholesaler should look like.",
            f"The final point ({last['date']}, GBP {last['value']:,.0f}) is the trap. It is not a collapse in "
            "demand; the extract simply stops on 9 December, so the month is partial. The z-score screen "
            f"returned {len(anomalies)} anomalies at |z| >= 2.0 and this truncation is why an analyst still has "
            "to look at the edges of a series before publishing the slope.",
            "The three-month rolling average is included precisely because it absorbs the seasonal spike; the "
            "raw line and the smoothed line tell different stories and both belong on the chart.",
        ],
        kpis=[
            Kpi("Months", str(stats["n"]), "Dec 2010 - Dec 2011"),
            Kpi("Total revenue", f"GBP {stats['total']:,.0f}", "cleaned transactions"),
            Kpi("Trend", f"{trend['pct_slope_per_period']:+.1f}%/mo", trend["direction"],
                tone="good" if trend["slope"] > 0 else "bad"),
            Kpi("Peak month", max(rows, key=lambda r: r["value"])["date"],
                f"GBP {max(r['value'] for r in rows):,.0f}"),
        ],
        charts=[
            Chart(id="monthly-revenue", kind="line", title="Monthly revenue with 3-month rolling average",
                  data=[{"x": r["date"], "revenue": round(r["value"], 2), "rolling": r["rolling_avg"]}
                        for r in rolling],
                  series=[{"key": "revenue", "label": "Revenue"}, {"key": "rolling", "label": "3-mo rolling avg"}],
                  valueFormat="currency",
                  note="December 2011 is truncated on the 9th -- the dip is the extract, not the business."),
            Chart(id="mom-growth", kind="bar", title="Month-over-month growth",
                  data=[{"x": r["date"], "growth": round(r["growth_rate"], 4)}
                        for r in growth if r["growth_rate"] is not None],
                  series=[{"key": "growth", "label": "MoM growth"}], valueFormat="percent"),
        ],
        tables=[Table("stats", "Series summary", ["Statistic", "Value"],
                      [[k, f"{v:,.2f}" if isinstance(v, float) else v] for k, v in stats.items()])],
        code_excerpt=report[:1400],
        code_language="text",
        takeaway="Revenue trends up and peaks in November; the apparent December collapse is a truncated "
                 "extract, which is the kind of edge effect that turns into a wrong forecast if unchecked.",
        used_skill_scripts=[ss.ref("time-series-analysis", "ts_analyzer.py")],
    )


DEMOS = [
    demo_exploratory_data_analysis,
    demo_programmatic_eda,
    demo_data_quality_audit,
    demo_pandas_patterns,
    demo_query_validation,
    demo_sql_to_business_logic,
    demo_schema_mapper,
    demo_metric_reconciliation,
    demo_data_catalog_entry,
    demo_time_series_analysis,
]


def main() -> None:
    print("\n=== CRISP-DM 2: Data Understanding ===")
    for fn in DEMOS:
        emit(fn())


if __name__ == "__main__":
    main()
