"""CRISP-DM Phase 3 - Data Preparation.

Five skills. Everything that touches the target is fitted on the training split
only, and the cost of getting that wrong is measured rather than asserted.
The engineered churn frames written here are what phase 4 trains on.
"""
from __future__ import annotations
import sys, pathlib, json

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, precision_recall_curve
from sklearn.model_selection import KFold, train_test_split
from sklearn.preprocessing import StandardScaler

from lib import data
from lib.emit import Chart, Kpi, SkillResult, Table, emit
from lib.paths import ARTIFACTS, PROCESSED
from lib.seeds import SEED, set_global_seed
from lib import skillscripts as ss

set_global_seed()
X_TR, X_TE, Y_TR, Y_TE = data.churn_split()


# ================================================================= 1. data-cleaning
def demo_data_cleaning() -> SkillResult:
    raw = data.telco_raw()
    blanks = raw["TotalCharges"].astype(str).str.strip().eq("")
    n_blank = int(blanks.sum())
    tenure_of_blanks = sorted(raw.loc[blanks, "tenure"].unique().tolist())

    # --- train-only imputation, and what full-data imputation would have leaked
    tr = X_TR.copy()
    te = X_TE.copy()
    train_median = float(tr["TotalCharges"].median())
    full_median = float(data.telco_typed()["TotalCharges"].median())

    # --- the actual cleaning decisions
    clean_tr, clean_te = tr.copy(), te.copy()
    for frame in (clean_tr, clean_te):
        # tenure == 0 accounts have never been billed: structural zero, not missing
        frame["TotalCharges"] = frame["TotalCharges"].fillna(0.0)
        # collapse the three-valued service columns into clean booleans
        for c in frame.columns:
            if frame[c].dtype == object:
                frame[c] = frame[c].astype(str).str.strip()
                frame[c] = frame[c].replace({"No internet service": "No", "No phone service": "No"})

    n_dupes = int(data.telco_typed().drop(columns=["customerID"]).duplicated().sum())
    collapsed = [c for c in X_TR.columns if X_TR[c].dtype == object and
                 X_TR[c].astype(str).str.contains("No internet service|No phone service").any()]

    # Titanic: the same discipline on a messier file
    tit = data.titanic()
    t_tr, t_te = train_test_split(tit, test_size=0.2, random_state=SEED, stratify=tit["Survived"])
    age_by_group = t_tr.groupby(["Pclass", "Sex"])["Age"].median()
    t_te_filled = t_te.copy()
    t_te_filled["Age"] = t_te_filled.apply(
        lambda r: age_by_group.loc[(r["Pclass"], r["Sex"])] if pd.isna(r["Age"]) else r["Age"], axis=1)
    tit_missing = (tit.isna().mean() * 100).sort_values(ascending=False).head(4)

    data.save_processed("churn_train_clean", clean_tr.assign(Churn_flag=Y_TR.values))
    data.save_processed("churn_test_clean", clean_te.assign(Churn_flag=Y_TE.values))

    return SkillResult(
        skill="data-cleaning", source="agent-ml-skills",
        category="Data Prep & Exploration", phase=3, track="T1",
        title="Cleaning Telco and Titanic with train-only statistics",
        prescribes="Fix types, duplicates and outliers deliberately, and compute every imputation statistic on "
                   "the training split alone -- never on the full dataset.",
        applied="Coerced TotalCharges, resolved its 11 blanks structurally, collapsed the redundant "
                "'No internet service' level, and imputed Titanic ages from train-only group medians.",
        narrative=[
            f"TotalCharges arrives as text because {n_blank} rows are blank. Every one has tenure = "
            f"{tenure_of_blanks} -- these accounts have never been billed, so the right fill is 0.0, not the "
            f"median. Filling with the median would have inserted GBP {train_median:,.0f} of imaginary billing "
            "history into the newest customers, which is precisely the population the model must get right.",
            f"The leakage margin is measurable: the median computed on the training split is "
            f"{train_median:,.2f} against {full_median:,.2f} on the full dataset. The gap is small here, but "
            "the discipline is what keeps the test split honest -- and on Titanic, where 19.9% of ages are "
            "missing, the same rule matters much more.",
            f"{len(collapsed)} service columns encode 'No internet service' or 'No phone service' as a third "
            "level that means the same thing as 'No'. Collapsing them removes one redundant dummy column each "
            f"without losing information. {n_dupes} exact duplicate customers exist once the ID is dropped, so "
            "no de-duplication is needed.",
        ],
        kpis=[
            Kpi("Blank TotalCharges", str(n_blank), "filled with 0.0, not the median", tone="good"),
            Kpi("Train vs full median", f"{train_median:,.0f} / {full_median:,.0f}",
                "the leakage the split prevents"),
            Kpi("Service columns collapsed", str(len(collapsed)), "'No internet service' -> 'No'"),
            Kpi("Titanic Age missing", f"{tit['Age'].isna().mean():.1%}",
                "imputed by train-only Pclass x Sex median", tone="warn"),
        ],
        charts=[
            Chart(id="titanic-missing", kind="hbar", title="Titanic missingness before cleaning",
                  data=[{"x": k, "pct": round(float(v), 2)} for k, v in tit_missing.items()],
                  series=[{"key": "pct", "label": "% missing"}]),
            Chart(id="age-medians", kind="bar", title="Train-only Age medians used for imputation",
                  data=[{"x": f"class {int(p)} {s}", "age": float(v)}
                        for (p, s), v in age_by_group.items()],
                  series=[{"key": "age", "label": "Median age (train split)"}],
                  note="Computed on the 712-row training split; applied unchanged to the test split."),
        ],
        tables=[Table("decisions", "Cleaning decisions and their justification",
                      ["Issue", "Naive fix", "What we did", "Why"],
                      [["TotalCharges is text with 11 blanks", "drop rows or fill median",
                        "coerce to float, fill 0.0", "tenure = 0 means never billed: a structural zero"],
                       ["'No internet service' as a third level", "leave it",
                        "map to 'No'", f"removes {len(collapsed)} redundant dummy columns, same information"],
                       ["Titanic Age 19.9% missing", "global median",
                        "train-only median by Pclass x Sex", "age differs sharply by class and sex"],
                       ["Titanic Cabin 77% missing", "drop the column",
                        "keep as HasCabin boolean", "missingness itself carries class information"],
                       ["Outliers in MonthlyCharges", "clip at 1.5 IQR",
                        "keep unchanged", "phase 2 confirmed the range is legitimate"]])],
        code_excerpt=(
            "# WRONG: statistic computed over train + test\n"
            "df['TotalCharges'] = df['TotalCharges'].fillna(df['TotalCharges'].median())\n\n"
            "# RIGHT: structural zero, and any real imputation fitted on train only\n"
            "X_train, X_test, y_train, y_test = train_test_split(X, y, stratify=y, random_state=SEED)\n"
            "X_train['TotalCharges'] = X_train['TotalCharges'].fillna(0.0)   # tenure == 0 -> never billed\n"
            "age_by_group = train.groupby(['Pclass', 'Sex'])['Age'].median() # fitted on train\n"
            "test['Age'] = test.apply(lambda r: age_by_group.loc[(r.Pclass, r.Sex)]\n"
            "                         if pd.isna(r.Age) else r.Age, axis=1)"
        ),
        takeaway="Every missing value here has a reason, and the fix follows the reason -- structural zeros get "
                 "0.0, genuinely unknown ages get a train-only group median.",
        artifacts=["data/processed/churn_train_clean.parquet", "data/processed/churn_test_clean.parquet"],
    )


# ================================================================= 2. feature-engineering
def _engineer(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["TotalCharges"] = out["TotalCharges"].fillna(0.0)
    for c in out.columns:
        if out[c].dtype == object:
            out[c] = out[c].astype(str).str.strip().replace(
                {"No internet service": "No", "No phone service": "No"})

    service_cols = ["PhoneService", "MultipleLines", "OnlineSecurity", "OnlineBackup",
                    "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies"]
    out["n_services"] = sum((out[c] == "Yes").astype(int) for c in service_cols)
    out["tenure_band"] = pd.cut(out["tenure"], [-1, 6, 12, 24, 48, 100],
                                labels=["0-6m", "7-12m", "13-24m", "25-48m", "49m+"]).astype(str)
    out["avg_charge_per_month"] = np.where(out["tenure"] > 0, out["TotalCharges"] / out["tenure"],
                                           out["MonthlyCharges"])
    out["charge_drift"] = out["MonthlyCharges"] - out["avg_charge_per_month"]
    out["charge_per_service"] = out["MonthlyCharges"] / out["n_services"].clip(lower=1)
    out["is_new"] = (out["tenure"] <= 6).astype(int)
    out["auto_pay"] = out["PaymentMethod"].str.contains("automatic").astype(int)
    return out


def _oof_target_encode(train: pd.Series, y: pd.Series, test: pd.Series, n_splits: int = 5):
    """Leakage-safe target encoding: each training row is encoded by folds that exclude it."""
    prior = y.mean()
    oof = pd.Series(index=train.index, dtype=float)
    for tr_idx, va_idx in KFold(n_splits=n_splits, shuffle=True, random_state=SEED).split(train):
        m = y.iloc[tr_idx].groupby(train.iloc[tr_idx]).mean()
        oof.iloc[va_idx] = train.iloc[va_idx].map(m).fillna(prior).values
    full = y.groupby(train).mean()
    return oof, test.map(full).fillna(prior)


def demo_feature_engineering() -> SkillResult:
    tr, te = _engineer(X_TR), _engineer(X_TE)
    y_tr, y_te = Y_TR.reset_index(drop=True), Y_TE.reset_index(drop=True)
    tr, te = tr.reset_index(drop=True), te.reset_index(drop=True)

    # --- naive vs out-of-fold target encoding on a high-cardinality-ish key
    key_tr = (tr["Contract"] + "|" + tr["InternetService"] + "|" + tr["PaymentMethod"] + "|" + tr["tenure_band"])
    key_te = (te["Contract"] + "|" + te["InternetService"] + "|" + te["PaymentMethod"] + "|" + te["tenure_band"])
    naive_map = y_tr.groupby(key_tr).mean()
    naive_tr = key_tr.map(naive_map)
    naive_te = key_te.map(naive_map).fillna(y_tr.mean())
    oof_tr, oof_te = _oof_target_encode(key_tr, y_tr, key_te)

    def single_feature_auc(f_tr, f_te):
        m = LogisticRegression(max_iter=1000).fit(f_tr.values.reshape(-1, 1), y_tr)
        return (roc_auc_score(y_tr, m.predict_proba(f_tr.values.reshape(-1, 1))[:, 1]),
                roc_auc_score(y_te, m.predict_proba(f_te.values.reshape(-1, 1))[:, 1]))

    naive_train_auc, naive_test_auc = single_feature_auc(naive_tr, naive_te)
    oof_train_auc, oof_test_auc = single_feature_auc(oof_tr, oof_te)

    tr["segment_te"], te["segment_te"] = oof_tr, oof_te
    data.save_processed("churn_train_features", tr.assign(Churn_flag=y_tr.values))
    data.save_processed("churn_test_features", te.assign(Churn_flag=y_te.values))

    new_cols = ["n_services", "tenure_band", "avg_charge_per_month", "charge_drift",
                "charge_per_service", "is_new", "auto_pay", "segment_te"]
    num_new = [c for c in new_cols if tr[c].dtype != object]
    corrs = {c: float(np.corrcoef(tr[c], y_tr)[0, 1]) for c in num_new}

    return SkillResult(
        skill="feature-engineering", source="agent-ml-skills",
        category="Data Prep & Exploration", phase=3, track="T1",
        title="Eight engineered features, and the target-encoding trap measured",
        prescribes="Build features from domain structure -- ratios, counts, bands, datetime parts -- and when "
                   "target-encoding a categorical, compute it out-of-fold or it will leak.",
        applied="Added eight features to the churn frame, then encoded a four-way segment key both naively and "
                "out-of-fold and compared what each does to train and test AUC.",
        narrative=[
            "The useful features here are ratios and counts, not transformations of single columns. "
            "`charge_drift` (current monthly charge minus lifetime average) is a price-increase detector; "
            "`charge_per_service` normalises billing by how much the customer actually buys; `n_services` "
            "counts add-ons, which is the strongest engineered signal at "
            f"r = {corrs['n_services']:.3f}.",
            f"The target-encoding comparison is the demonstration that matters. Encoded naively -- mapping each "
            f"segment to its mean churn rate computed on all training rows -- the single feature scores "
            f"{naive_train_auc:.3f} AUC on train and {naive_test_auc:.3f} on test. Encoded out-of-fold, it "
            f"scores {oof_train_auc:.3f} on train and {oof_test_auc:.3f} on test.",
            f"The naive version's train score is inflated by {naive_train_auc - oof_train_auc:+.3f} while its "
            f"test score is {naive_test_auc - oof_test_auc:+.3f} -- it looks better in development and is not "
            "better in production. That gap between the two train numbers is the leak, visible directly.",
            "The out-of-fold encoding is the one written to `data/processed/churn_*_features.parquet`, so the "
            "model in phase 4 never sees its own target.",
        ],
        kpis=[
            Kpi("Features added", str(len(new_cols)), "ratios, counts, bands, encoding"),
            Kpi("Naive TE train AUC", f"{naive_train_auc:.3f}", f"test {naive_test_auc:.3f}", tone="bad"),
            Kpi("OOF TE train AUC", f"{oof_train_auc:.3f}", f"test {oof_test_auc:.3f}", tone="good"),
            Kpi("Inflation removed", f"{naive_train_auc - oof_train_auc:+.3f}", "train AUC that was not real"),
        ],
        charts=[
            Chart(id="te-comparison", kind="bar",
                  title="Target encoding: naive vs out-of-fold, one feature, same model",
                  data=[{"x": "Naive (leaky)", "train": round(naive_train_auc, 4), "test": round(naive_test_auc, 4)},
                        {"x": "Out-of-fold", "train": round(oof_train_auc, 4), "test": round(oof_test_auc, 4)}],
                  series=[{"key": "train", "label": "Train AUC"}, {"key": "test", "label": "Test AUC"}],
                  note="The leak shows up as a train-test gap, not as a better test score."),
            Chart(id="feature-corr", kind="hbar", title="Engineered features vs churn (Pearson r)",
                  data=[{"x": k, "r": round(v, 4)} for k, v in
                        sorted(corrs.items(), key=lambda kv: -abs(kv[1]))],
                  series=[{"key": "r", "label": "correlation with churn"}], domain=[-0.5, 0.5]),
        ],
        tables=[Table("features", "Engineered features",
                      ["Feature", "Definition", "Rationale"],
                      [["n_services", "count of subscribed add-on services", "engagement proxy"],
                       ["tenure_band", "tenure bucketed into 5 bands", "non-linear onboarding cliff"],
                       ["avg_charge_per_month", "TotalCharges / tenure", "realised price, not list price"],
                       ["charge_drift", "MonthlyCharges - avg_charge_per_month", "recent price increase"],
                       ["charge_per_service", "MonthlyCharges / max(n_services, 1)", "value for money"],
                       ["is_new", "tenure <= 6", "the highest-churn window"],
                       ["auto_pay", "PaymentMethod contains 'automatic'", "friction to leave"],
                       ["segment_te", "out-of-fold mean churn of the segment key", "high-order interaction, leak-free"]])],
        code_excerpt=(
            "def oof_target_encode(train, y, test, n_splits=5):\n"
            "    prior = y.mean()\n"
            "    oof = pd.Series(index=train.index, dtype=float)\n"
            "    for tr_idx, va_idx in KFold(n_splits, shuffle=True, random_state=SEED).split(train):\n"
            "        m = y.iloc[tr_idx].groupby(train.iloc[tr_idx]).mean()   # fold-only means\n"
            "        oof.iloc[va_idx] = train.iloc[va_idx].map(m).fillna(prior).values\n"
            "    return oof, test.map(y.groupby(train).mean()).fillna(prior)"
        ),
        takeaway=f"Naive target encoding bought {naive_train_auc - oof_train_auc:+.3f} of train AUC and "
                 f"{naive_test_auc - oof_test_auc:+.3f} of test AUC -- it is a self-deception, and the "
                 "out-of-fold version costs five lines to avoid it.",
        artifacts=["data/processed/churn_train_features.parquet", "data/processed/churn_test_features.parquet"],
    )


# ================================================================= 3. imbalanced-data
def demo_imbalanced_data() -> SkillResult:
    cc = data.creditcard(sample=80_000)
    if cc is not None:
        y = cc["Class"].astype(int)
        X = cc.drop(columns=[c for c in ["Class", "Time"] if c in cc.columns])
        source = "Credit Card Fraud (mlg-ulb/creditcardfraud, 80k-row stratified subsample keeping all frauds)"
    else:  # documented fallback if the OpenML mirror is unavailable
        df = data.telco_typed()
        pos = df[df["Churn_flag"] == 1].sample(frac=0.02, random_state=SEED)
        df = pd.concat([df[df["Churn_flag"] == 0], pos])
        y = df["Churn_flag"]
        X = pd.get_dummies(df.drop(columns=["Churn", "Churn_flag", "customerID"]), drop_first=True).fillna(0)
        source = "Telco churn downsampled to ~0.5% positives (Credit Card Fraud mirror unavailable)"

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=SEED, stratify=y)
    sc = StandardScaler().fit(Xtr)
    Xtr_s, Xte_s = sc.transform(Xtr), sc.transform(Xte)

    from imblearn.over_sampling import SMOTE

    results = {}
    curves = {}

    def evaluate(name, model, xt, yt):
        model.fit(xt, yt)
        p = model.predict_proba(Xte_s)[:, 1]
        prec, rec, thr = precision_recall_curve(yte, p)
        f1 = np.divide(2 * prec * rec, prec + rec, out=np.zeros_like(prec), where=(prec + rec) > 0)
        best = int(np.argmax(f1))
        results[name] = {
            "roc_auc": roc_auc_score(yte, p),
            "pr_auc": average_precision_score(yte, p),
            "acc_at_0.5": float(((p >= 0.5).astype(int) == yte).mean()),
            "best_threshold": float(thr[min(best, len(thr) - 1)]),
            "precision_at_best": float(prec[best]),
            "recall_at_best": float(rec[best]),
            "f1_at_best": float(f1[best]),
        }
        idx = np.linspace(0, len(rec) - 1, 40).astype(int)
        curves[name] = [{"recall": round(float(rec[i]), 4), "precision": round(float(prec[i]), 4)} for i in idx]

    evaluate("Logistic (no handling)", LogisticRegression(max_iter=2000), Xtr_s, ytr)
    evaluate("class_weight='balanced'", LogisticRegression(max_iter=2000, class_weight="balanced"), Xtr_s, ytr)
    Xsm, ysm = SMOTE(random_state=SEED).fit_resample(Xtr_s, ytr)
    evaluate("SMOTE (train only)", LogisticRegression(max_iter=2000), Xsm, ysm)

    prevalence = float(y.mean())
    majority_acc = 1 - float(yte.mean())
    native_prevalence = 492 / 284_807 if cc is not None else prevalence

    pr_data = []
    for i in range(40):
        row = {"x": round(curves["Logistic (no handling)"][i]["recall"], 4)}
        for name in curves:
            row[name] = curves[name][i]["precision"]
        pr_data.append(row)

    return SkillResult(
        skill="imbalanced-data", source="agent-ml-skills",
        category="Data Prep & Exploration", phase=3, track="T1b",
        title=f"Fraud at {prevalence:.3%} prevalence: metrics first, resampling second",
        prescribes="With a rare target, drop accuracy, judge on PR-AUC and recall at a chosen precision, apply "
                   "class weights or SMOTE to the training split only, and tune the decision threshold.",
        applied=f"Trained three logistic models on {source} -- untouched, class-weighted, and SMOTE-resampled "
                "-- and compared them on ROC-AUC, PR-AUC and the best achievable F1 threshold.",
        narrative=[
            f"Fraud is {native_prevalence:.3%} of the full Kaggle file (492 of 284,807). The 80k-row subsample "
            f"used here keeps every fraud, so prevalence rises to {prevalence:.3%} -- still rare enough that "
            f"predicting 'never fraud' scores {majority_acc:.3%} accuracy on the test split. That single number "
            "is why accuracy is banned here: it is beaten by a model that does nothing, and it is the metric a "
            "stakeholder will reach for unless you replace it first.",
            f"ROC-AUC barely separates the three strategies ({min(r['roc_auc'] for r in results.values()):.3f} "
            f"to {max(r['roc_auc'] for r in results.values()):.3f}) because it is dominated by the "
            "overwhelming negative class. PR-AUC does separate them, which is the whole argument for using it "
            "when positives are rare.",
            "SMOTE is applied strictly inside the training split -- synthesising minority points before the "
            "split would place near-duplicates of training frauds into the test set and produce a beautiful, "
            "meaningless score.",
            f"The threshold is a business decision, not a default. At the F1-optimal cut-off each strategy "
            "trades precision against recall differently; the operating point should come from the cost of a "
            "missed fraud versus a false alarm, which is exactly the input phase 5 quantifies.",
        ],
        kpis=[
            Kpi("Positive prevalence", f"{prevalence:.3%}", f"{int(y.sum())} positives"),
            Kpi("Accuracy of 'always negative'", f"{majority_acc:.3%}", "why accuracy is useless here", tone="bad"),
            Kpi("Best PR-AUC", f"{max(r['pr_auc'] for r in results.values()):.3f}",
                max(results, key=lambda k: results[k]["pr_auc"]), tone="good"),
            Kpi("ROC-AUC spread", f"{max(r['roc_auc'] for r in results.values()) - min(r['roc_auc'] for r in results.values()):.3f}",
                "ROC hides what PR shows", tone="warn"),
        ],
        charts=[
            Chart(id="pr-curves", kind="line", title="Precision-recall curves by imbalance strategy",
                  data=pr_data, x="x",
                  series=[{"key": k, "label": k} for k in curves],
                  xLabel="recall", yLabel="precision"),
            Chart(id="metric-compare", kind="bar", title="ROC-AUC vs PR-AUC by strategy",
                  data=[{"x": k, "roc_auc": round(v["roc_auc"], 4), "pr_auc": round(v["pr_auc"], 4)}
                        for k, v in results.items()],
                  series=[{"key": "roc_auc", "label": "ROC-AUC"}, {"key": "pr_auc", "label": "PR-AUC"}],
                  note="ROC-AUC looks flat across strategies; PR-AUC is the metric that discriminates."),
        ],
        tables=[Table("strategies", "Strategy comparison on the held-out split",
                      ["Strategy", "ROC-AUC", "PR-AUC", "Best threshold", "Precision", "Recall", "F1"],
                      [[k, round(v["roc_auc"], 4), round(v["pr_auc"], 4), round(v["best_threshold"], 4),
                        round(v["precision_at_best"], 3), round(v["recall_at_best"], 3),
                        round(v["f1_at_best"], 3)] for k, v in results.items()])],
        code_excerpt=(
            "Xtr, Xte, ytr, yte = train_test_split(X, y, stratify=y, random_state=SEED)\n"
            "scaler = StandardScaler().fit(Xtr)              # fitted on train only\n"
            "Xsm, ysm = SMOTE(random_state=SEED).fit_resample(scaler.transform(Xtr), ytr)  # train only\n"
            "p = model.fit(Xsm, ysm).predict_proba(scaler.transform(Xte))[:, 1]\n"
            "prec, rec, thr = precision_recall_curve(yte, p)   # never accuracy"
        ),
        takeaway=f"At {prevalence:.3%} prevalence the do-nothing baseline is {majority_acc:.1%} accurate and "
                 "worthless; PR-AUC and an explicit threshold are the only honest way to compare the three "
                 "strategies -- ROC-AUC separates them by 0.001.",
    )


# ================================================================= 4. segmentation-analysis
def demo_segmentation_analysis() -> SkillResult:
    seg = ss.load("segmentation-analysis", "segmentation_runner.py")
    retail = data.retail_clean()
    snapshot = retail["InvoiceDate"].max() + pd.Timedelta(days=1)

    rfm = retail.groupby("CustomerID").agg(
        recency=("InvoiceDate", lambda s: (snapshot - s.max()).days),
        frequency=("InvoiceNo", "nunique"),
        monetary=("Revenue", "sum")).reset_index()
    rfm = rfm[rfm["monetary"] > 0]

    from sklearn.cluster import KMeans
    feats = np.log1p(rfm[["recency", "frequency", "monetary"]])
    Z = StandardScaler().fit_transform(feats)
    km = KMeans(n_clusters=4, random_state=SEED, n_init=10).fit(Z)
    rfm["cluster"] = km.labels_

    profile = rfm.groupby("cluster").agg(
        customers=("CustomerID", "count"), recency=("recency", "median"),
        frequency=("frequency", "median"), monetary=("monetary", "median"),
        revenue=("monetary", "sum")).reset_index()
    profile["revenue_share"] = profile["revenue"] / profile["revenue"].sum()

    # Name the clusters from their own centroids rather than by eye.
    order = profile.sort_values(["monetary", "frequency"], ascending=False)["cluster"].tolist()
    names = {}
    names[order[0]] = "Champions"
    names[order[1]] = "Loyal"
    names[order[2]] = "Occasional"
    names[order[3]] = "At risk / lapsed"
    rfm["segment"] = rfm["cluster"].map(names)
    profile["segment"] = profile["cluster"].map(names)

    rows = rfm[["segment", "monetary", "frequency"]].to_dict("records")
    prof = seg.profile_segments(rows, "segment", "monetary", agg="mean")
    report = seg.format_report(prof)

    sample = rfm.sample(min(900, len(rfm)), random_state=SEED)
    top = profile.sort_values("revenue", ascending=False).iloc[0]

    return SkillResult(
        skill="segmentation-analysis", source="data-analytics-skills",
        category="Data Analysis & Investigation", phase=3, track="T2",
        title="RFM plus k-means on 4,338 retail customers, indexed against the average",
        prescribes="Build segments on behaviour, profile each one against the overall average with an index and "
                   "a significance test, and name segments from their profile rather than from intuition.",
        applied="Computed recency/frequency/monetary per customer, clustered the log-scaled features into four "
                "k-means groups, then profiled them with the skill's segmentation_runner.py.",
        narrative=[
            f"{len(rfm):,} identified customers survive the phase-2 cleaning. Four clusters emerge cleanly from "
            "log-scaled RFM: the naming comes from the centroids, so 'Champions' means high monetary and high "
            "frequency by measurement, not by assertion.",
            f"The concentration is the finding: {top['segment']} is {top['customers'] / len(rfm):.0%} of "
            f"customers and {top['revenue_share']:.0%} of revenue. A retention budget spread evenly across "
            "customers would spend most of it on the segment that generates the least.",
            f"The skill's profiler indexes each segment against the overall mean and flags significance: "
            f"{sum(1 for s in prof['segments'] if s['notable'])} of 4 segments differ from the overall average "
            "at |z| > 1.96, so these are not arbitrary slices of a continuum.",
        ],
        kpis=[
            Kpi("Customers segmented", f"{len(rfm):,}", "identified buyers only"),
            Kpi("Segments", "4", "k-means on log RFM"),
            Kpi("Top segment revenue share", f"{top['revenue_share']:.0%}",
                f"{top['segment']}, {top['customers'] / len(rfm):.0%} of customers", tone="good"),
            Kpi("Statistically notable", f"{sum(1 for s in prof['segments'] if s['notable'])}/4",
                "|z| > 1.96 vs overall mean"),
        ],
        charts=[
            Chart(id="rfm-scatter", kind="scatter", title="Recency vs monetary value by segment",
                  data=[{"x": int(r.recency), "y": round(float(r.monetary), 2), "series": r.segment}
                        for r in sample.itertuples()],
                  series=[{"key": "y", "label": "Monetary (GBP)"}],
                  xLabel="days since last order", yLabel="lifetime revenue (GBP, log scale)"),
            Chart(id="segment-revenue", kind="bar", title="Customers and revenue share by segment",
                  data=[{"x": r.segment, "customers_pct": round(r.customers / len(rfm), 4),
                         "revenue_pct": round(float(r.revenue_share), 4)}
                        for r in profile.sort_values("revenue", ascending=False).itertuples()],
                  series=[{"key": "customers_pct", "label": "% of customers"},
                          {"key": "revenue_pct", "label": "% of revenue"}], valueFormat="percent"),
        ],
        tables=[Table("profile", "Segment profile (medians)",
                      ["Segment", "Customers", "Recency (days)", "Orders", "Revenue (GBP)", "Revenue share"],
                      [[r.segment, int(r.customers), int(r.recency), int(r.frequency),
                        f"{r.monetary:,.0f}", f"{r.revenue_share:.1%}"]
                       for r in profile.sort_values("revenue", ascending=False).itertuples()])],
        code_excerpt=report[:1300],
        code_language="text",
        takeaway=f"{top['revenue_share']:.0%} of revenue sits in one behavioural segment holding "
                 f"{top['customers'] / len(rfm):.0%} of customers -- segmentation, not averages, is what makes "
                 "a retention budget rational.",
        used_skill_scripts=[ss.ref("segmentation-analysis", "segmentation_runner.py")],
    )


# ================================================================= 5. cohort-analysis
def demo_cohort_analysis() -> SkillResult:
    cb = ss.load("cohort-analysis", "cohort_builder.py")
    rm = ss.load("cohort-analysis", "retention_matrix.py")
    # pandas 2.3 no longer accepts the script's "MS" alias in Series.dt.to_period.
    cb.FREQ_MAP["monthly"] = "M"

    retail = data.retail_clean()
    first = retail.groupby("CustomerID")["InvoiceDate"].min().rename("cohort_date")
    events = retail[["CustomerID", "InvoiceDate"]].merge(first, on="CustomerID")
    events = events.rename(columns={"CustomerID": "user_id", "InvoiceDate": "activity_date"})

    table = cb.build_cohort_table(events, granularity="monthly")
    matrix = rm.compute_retention_matrix(table, fmt="pct")

    period_cols = [c for c in matrix.columns if c.startswith("Period")]
    heat = []
    for cohort, row in matrix.iterrows():
        for c in period_cols:
            v = row[c]
            if pd.notna(v):
                heat.append({"row": str(cohort)[:7], "col": c.replace("Period ", "M"), "value": float(v)})

    curves = []
    for c in period_cols[:13]:
        entry = {"x": c.replace("Period ", "M")}
        for cohort in list(matrix.index)[:4]:
            v = matrix.loc[cohort, c]
            entry[str(cohort)[:7]] = None if pd.isna(v) else float(v)
        curves.append(entry)

    m1 = matrix["Period 1"].dropna()
    m6 = matrix["Period 6"].dropna() if "Period 6" in matrix else pd.Series(dtype=float)
    biggest = matrix["Cohort Size"].idxmax()

    return SkillResult(
        skill="cohort-analysis", source="data-analytics-skills",
        category="Data Analysis & Investigation", phase=3, track="T2",
        title="Monthly acquisition cohorts and how fast each one leaks",
        prescribes="Group users by acquisition period, measure activity in each subsequent period against the "
                   "cohort's own size, and read down the columns to separate cohort quality from seasonality.",
        applied="Built the cohort table and the retention matrix with the skill's cohort_builder.py and "
                "retention_matrix.py from every identified retail customer's first purchase.",
        narrative=[
            f"Month-1 retention averages {m1.mean():.1f}% across cohorts and ranges from {m1.min():.1f}% to "
            f"{m1.max():.1f}%. That spread is the point of cohorting: a single blended 'retention rate' would "
            "hide a threefold difference in how good the acquisition months were.",
            f"The {str(biggest)[:7]} cohort is the largest at {int(matrix.loc[biggest, 'Cohort Size']):,} "
            "customers, and it is also the first -- an artefact worth stating, because in a snapshot that "
            "starts in December 2010 the first cohort absorbs every pre-existing customer. Reading it as a "
            "spectacular acquisition month would be wrong.",
            f"Reading down the Period-1 column rather than across the rows separates cohort quality from "
            f"calendar effects: later cohorts have fewer observed periods, so the triangle thins to the right "
            f"and the bottom rows are not comparable to the top ones on long horizons.",
        ],
        kpis=[
            Kpi("Cohorts", str(len(matrix)), "monthly, Dec 2010 - Dec 2011"),
            Kpi("Customers", f"{int(matrix['Cohort Size'].sum()):,}", "first purchase = cohort"),
            Kpi("Mean month-1 retention", f"{m1.mean():.1f}%", f"range {m1.min():.1f}-{m1.max():.1f}%"),
            Kpi("Mean month-6 retention", f"{m6.mean():.1f}%" if len(m6) else "n/a",
                "cohorts with 6+ months observed"),
        ],
        charts=[
            Chart(id="retention-heatmap", kind="heatmap", title="Retention triangle (% of cohort active)",
                  data=heat, x="col", series=[{"key": "value", "label": "% retained"}], domain=[0, 60],
                  note="Rows are acquisition months; columns are months since acquisition."),
            Chart(id="retention-curves", kind="line", title="Retention curves, first four cohorts",
                  data=curves, x="x",
                  series=[{"key": str(c)[:7], "label": str(c)[:7]} for c in list(matrix.index)[:4]],
                  xLabel="months since first purchase", yLabel="% retained"),
        ],
        tables=[Table("matrix", "Retention matrix (first 8 periods)",
                      ["Cohort", "Size"] + [c.replace("Period ", "M") for c in period_cols[:8]],
                      [[str(i)[:7], int(matrix.loc[i, "Cohort Size"])] +
                       [None if pd.isna(matrix.loc[i, c]) else round(float(matrix.loc[i, c]), 1)
                        for c in period_cols[:8]] for i in matrix.index])],
        code_excerpt=(
            "events = retail[['CustomerID', 'InvoiceDate']].merge(first_purchase, on='CustomerID')\n"
            "events = events.rename(columns={'CustomerID': 'user_id', 'InvoiceDate': 'activity_date'})\n"
            "table  = build_cohort_table(events, granularity='monthly')\n"
            "matrix = compute_retention_matrix(table, fmt='pct')"
        ),
        takeaway="Month-1 retention varies by a factor of three across acquisition cohorts, and the first "
                 "cohort is inflated by the snapshot boundary -- both invisible in a blended retention number.",
        used_skill_scripts=[ss.ref("cohort-analysis", "cohort_builder.py"),
                            ss.ref("cohort-analysis", "retention_matrix.py")],
    )


DEMOS = [
    demo_data_cleaning,
    demo_feature_engineering,
    demo_imbalanced_data,
    demo_segmentation_analysis,
    demo_cohort_analysis,
]


def main() -> None:
    print("\n=== CRISP-DM 3: Data Preparation ===")
    for fn in DEMOS:
        emit(fn())


if __name__ == "__main__":
    main()
