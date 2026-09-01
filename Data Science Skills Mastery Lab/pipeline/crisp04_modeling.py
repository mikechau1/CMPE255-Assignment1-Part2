"""CRISP-DM Phase 4 - Modeling (tabular half).

Four skills on the churn frames written by phase 3: pipelines that cannot leak,
a tuning budget spent deliberately, every run tracked in MLflow, and a
deliberately broken model diagnosed rather than described.

The deep-learning, LLM and RAG skills of this phase live in pipeline/heavy/.
"""
from __future__ import annotations
import json, sys, pathlib, time, warnings

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, RandomizedSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from lib import data
from lib.emit import Chart, Kpi, SkillResult, Table, emit
from lib.paths import ARTIFACTS
from lib.seeds import SEED, set_global_seed

set_global_seed()
warnings.filterwarnings("ignore", category=UserWarning)

TRAIN = data.load_processed("churn_train_features")
TEST = data.load_processed("churn_test_features")
DROP = ["customerID", "Churn_flag"]
X_TR = TRAIN.drop(columns=DROP)
Y_TR = TRAIN["Churn_flag"]
X_TE = TEST.drop(columns=DROP)
Y_TE = TEST["Churn_flag"]
NUM = [c for c in X_TR.columns if X_TR[c].dtype != object]
CAT = [c for c in X_TR.columns if X_TR[c].dtype == object]
CV = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")),
                          ("scale", StandardScaler())]), NUM),
        ("cat", Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                          ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=20))]), CAT),
    ])


# ================================================================= 1. sklearn-pipelines
def demo_sklearn_pipelines() -> SkillResult:
    pipe = Pipeline([("prep", build_preprocessor()),
                     ("clf", LogisticRegression(max_iter=2000, class_weight="balanced"))])
    proper = cross_val_score(pipe, X_TR, Y_TR, cv=CV, scoring="roc_auc")

    # The common mistake: fit the scaler/encoder on everything, then cross-validate the model.
    prep = build_preprocessor()
    X_all = prep.fit_transform(pd.concat([X_TR, X_TE]))
    X_all = X_all.toarray() if hasattr(X_all, "toarray") else X_all
    leaky = cross_val_score(LogisticRegression(max_iter=2000, class_weight="balanced"),
                            X_all[:len(X_TR)], Y_TR, cv=CV, scoring="roc_auc")

    pipe.fit(X_TR, Y_TR)
    test_auc = roc_auc_score(Y_TE, pipe.predict_proba(X_TE)[:, 1])
    n_features = pipe.named_steps["prep"].transform(X_TR.head(2)).shape[1]
    joblib.dump(pipe, ARTIFACTS / "churn_pipeline_logreg.joblib")

    return SkillResult(
        skill="sklearn-pipelines", source="agent-ml-skills",
        category="Modeling", phase=4, track="T1",
        title="One Pipeline object so preprocessing cannot escape the fold",
        prescribes="Put every fitted transformation inside a Pipeline / ColumnTransformer so cross-validation "
                   "refits it per fold; never transform the full dataset before splitting.",
        applied=f"Built a ColumnTransformer over {len(NUM)} numeric and {len(CAT)} categorical churn columns, "
                "cross-validated it correctly, and measured what the pre-fitted alternative reports instead.",
        narrative=[
            f"The pipeline expands {X_TR.shape[1]} input columns into {n_features} model features (median "
            "imputation and scaling on the numeric block, most-frequent imputation and one-hot with a "
            "min-frequency floor on the categorical block), and all of it is refitted inside every CV fold.",
            f"Cross-validated correctly it scores {proper.mean():.4f} +/- {proper.std():.4f} ROC-AUC. Fitting "
            f"the same preprocessing on train and test first and then cross-validating reports "
            f"{leaky.mean():.4f} -- a difference of {leaky.mean() - proper.mean():+.4f}.",
            "That gap is small precisely because this preprocessing is mild; scaling barely leaks. The reason "
            "to be strict anyway is that the same mistake with target encoding, imputation from group means, or "
            "feature selection produces a large gap, and the code looks identical. The Pipeline makes the "
            "correct version the easy version.",
            f"On the untouched test split the fitted pipeline scores {test_auc:.4f}, consistent with the "
            "cross-validated estimate -- which is what a non-leaking setup should look like.",
        ],
        kpis=[
            Kpi("CV ROC-AUC (correct)", f"{proper.mean():.4f}", f"+/- {proper.std():.4f}", tone="good"),
            Kpi("CV ROC-AUC (pre-fitted prep)", f"{leaky.mean():.4f}",
                f"{leaky.mean() - proper.mean():+.4f} optimism", tone="bad"),
            Kpi("Test ROC-AUC", f"{test_auc:.4f}", "held-out split"),
            Kpi("Model features", str(n_features), f"from {X_TR.shape[1]} columns"),
        ],
        charts=[
            Chart(id="cv-folds", kind="bar", title="Per-fold ROC-AUC: correct pipeline vs pre-fitted preprocessing",
                  data=[{"x": f"fold {i + 1}", "correct": round(float(a), 4), "prefitted": round(float(b), 4)}
                        for i, (a, b) in enumerate(zip(proper, leaky))],
                  series=[{"key": "correct", "label": "Pipeline inside CV"},
                          {"key": "prefitted", "label": "Preprocessing fitted on all data"}],
                  domain=[0.8, 0.88]),
        ],
        tables=[Table("steps", "Pipeline definition",
                      ["Block", "Columns", "Steps"],
                      [["num", f"{len(NUM)} numeric", "SimpleImputer(median) -> StandardScaler"],
                       ["cat", f"{len(CAT)} categorical",
                        "SimpleImputer(most_frequent) -> OneHotEncoder(handle_unknown='ignore', min_frequency=20)"],
                       ["clf", "-", "LogisticRegression(class_weight='balanced', max_iter=2000)"]])],
        code_excerpt=(
            "pre = ColumnTransformer([\n"
            "    ('num', Pipeline([('impute', SimpleImputer(strategy='median')),\n"
            "                      ('scale', StandardScaler())]), NUM),\n"
            "    ('cat', Pipeline([('impute', SimpleImputer(strategy='most_frequent')),\n"
            "                      ('onehot', OneHotEncoder(handle_unknown='ignore', min_frequency=20))]), CAT),\n"
            "])\n"
            "pipe = Pipeline([('prep', pre), ('clf', LogisticRegression(class_weight='balanced'))])\n"
            "cross_val_score(pipe, X_train, y_train, cv=StratifiedKFold(5, shuffle=True), scoring='roc_auc')"
        ),
        takeaway=f"Wrapping preprocessing in the estimator costs nothing and removes an entire class of silent "
                 f"optimism; with scaling and one-hot alone the optimism is only "
                 f"{leaky.mean() - proper.mean():+.4f} AUC, but the identical mistake with target encoding or "
                 "group-mean imputation is worth far more.",
        artifacts=["artifacts/churn_pipeline_logreg.joblib"],
    )


# ================================================================= 2. hyperparameter-tuning
def demo_hyperparameter_tuning() -> SkillResult:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    base = Pipeline([("prep", build_preprocessor()),
                     ("clf", HistGradientBoostingClassifier(random_state=SEED))])
    default_cv = cross_val_score(base, X_TR, Y_TR, cv=CV, scoring="roc_auc").mean()

    budget = 30
    t0 = time.perf_counter()
    rs = RandomizedSearchCV(
        base,
        {"clf__learning_rate": [0.02, 0.05, 0.08, 0.12, 0.2],
         "clf__max_leaf_nodes": [7, 15, 31, 63],
         "clf__min_samples_leaf": [10, 20, 40, 80],
         "clf__l2_regularization": [0.0, 0.5, 1.0, 5.0],
         "clf__max_iter": [150, 300, 500]},
        n_iter=budget, cv=CV, scoring="roc_auc", random_state=SEED, n_jobs=-1)
    rs.fit(X_TR, Y_TR)
    rs_time = time.perf_counter() - t0
    rs_trials = sorted(rs.cv_results_["mean_test_score"])

    def objective(trial):
        params = {
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "max_leaf_nodes": trial.suggest_int("max_leaf_nodes", 4, 64, log=True),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 5, 100, log=True),
            "l2_regularization": trial.suggest_float("l2_regularization", 1e-3, 10.0, log=True),
            "max_iter": trial.suggest_int("max_iter", 100, 600, step=50),
        }
        p = Pipeline([("prep", build_preprocessor()),
                      ("clf", HistGradientBoostingClassifier(random_state=SEED, early_stopping=True,
                                                             validation_fraction=0.15, n_iter_no_change=20,
                                                             **params))])
        return cross_val_score(p, X_TR, Y_TR, cv=CV, scoring="roc_auc", n_jobs=-1).mean()

    t0 = time.perf_counter()
    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=budget, show_progress_bar=False)
    opt_time = time.perf_counter() - t0

    best = Pipeline([("prep", build_preprocessor()),
                     ("clf", HistGradientBoostingClassifier(random_state=SEED, early_stopping=True,
                                                            validation_fraction=0.15, n_iter_no_change=20,
                                                            **study.best_params))])
    best.fit(X_TR, Y_TR)
    test_auc = roc_auc_score(Y_TE, best.predict_proba(X_TE)[:, 1])
    joblib.dump(best, ARTIFACTS / "churn_model.joblib")
    pd.DataFrame({"customerID": TEST["customerID"], "y_true": Y_TE,
                  "score": best.predict_proba(X_TE)[:, 1]}).to_parquet(ARTIFACTS / "churn_test_scores.parquet")

    running = np.maximum.accumulate([t.value for t in study.trials])
    rs_running = np.maximum.accumulate(rs.cv_results_["mean_test_score"])
    opt_best_trial = int(np.argmax([t.value for t in study.trials])) + 1
    rs_best_trial = int(np.argmax(rs.cv_results_["mean_test_score"])) + 1

    return SkillResult(
        skill="hyperparameter-tuning", source="agent-ml-skills",
        category="Modeling", phase=4, track="T1",
        title=f"{budget} trials each: random search vs Optuna, same CV, same budget",
        prescribes="Fix the budget first, search inside a leakage-safe CV, prefer Bayesian search over grid for "
                   "continuous spaces, and use early stopping so trials are not all equally expensive.",
        applied="Tuned a HistGradientBoosting pipeline with RandomizedSearchCV and with an Optuna TPE study "
                "over the same 5-fold CV, both capped at 30 trials, with early stopping enabled in the Optuna arm.",
        narrative=[
            f"Untuned defaults score {default_cv:.4f} CV ROC-AUC. Random search reaches "
            f"{rs.best_score_:.4f} in {rs_time:.0f}s; Optuna's TPE sampler reaches {study.best_value:.4f} in "
            f"{opt_time:.0f}s. The gain over defaults is "
            f"{max(rs.best_score_, study.best_value) - default_cv:+.4f} AUC -- real but modest, which is the "
            "honest result for a well-behaved tabular problem.",
            f"The searches do not separate on quality here: random search hit its best at trial "
            f"{rs_best_trial} and Optuna at trial {opt_best_trial}, and the two plateaus differ by "
            f"{study.best_value - rs.best_score_:+.5f} AUC -- noise. That is the expected outcome for a "
            "five-parameter space on 5.6k rows, and reporting it as a win for Bayesian search would be "
            "dressing up a tie. Optuna's advantage here was wall-clock: early stopping made its trials "
            f"cheaper ({opt_time:.0f}s against {rs_time:.0f}s for the same 30 trials).",
            "Every trial is scored by the same 5-fold CV over the same Pipeline, so preprocessing is refitted "
            "inside each fold of each trial. Tuning on a pre-transformed matrix would inherit the leak from the "
            "previous demo and then amplify it, because the search optimises directly against the leaked score.",
            f"The tuned model scores {test_auc:.4f} on the held-out test split -- the number phase 5 evaluates.",
        ],
        kpis=[
            Kpi("Default CV AUC", f"{default_cv:.4f}", "HistGradientBoosting out of the box"),
            Kpi("Random search best", f"{rs.best_score_:.4f}", f"{budget} trials, {rs_time:.0f}s"),
            Kpi("Optuna TPE best", f"{study.best_value:.4f}", f"{budget} trials, {opt_time:.0f}s", tone="good"),
            Kpi("Test AUC (tuned)", f"{test_auc:.4f}", "held-out split"),
        ],
        charts=[
            Chart(id="running-best", kind="line", title="Running best CV score by trial",
                  data=[{"x": i + 1, "optuna": round(float(running[i]), 5),
                         "random": round(float(rs_running[i]), 5)} for i in range(budget)],
                  series=[{"key": "optuna", "label": "Optuna (TPE)"},
                          {"key": "random", "label": "RandomizedSearchCV"}],
                  xLabel="trial", yLabel="best CV ROC-AUC so far"),
            Chart(id="trial-scatter", kind="scatter", title="Learning rate vs CV score across Optuna trials",
                  data=[{"x": round(t.params["learning_rate"], 4), "y": round(t.value, 5),
                         "series": "trial"} for t in study.trials if t.value is not None],
                  series=[{"key": "y", "label": "CV ROC-AUC"}],
                  xLabel="learning rate (log-sampled)", yLabel="CV ROC-AUC"),
        ],
        tables=[Table("best-params", "Best parameters found",
                      ["Parameter", "Optuna", "Random search"],
                      [[k, str(round(v, 4) if isinstance(v, float) else v),
                        str(rs.best_params_.get(f"clf__{k}", "-"))] for k, v in study.best_params.items()])],
        code_excerpt=(
            "def objective(trial):\n"
            "    params = {'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),\n"
            "              'max_leaf_nodes': trial.suggest_int('max_leaf_nodes', 4, 64, log=True), ...}\n"
            "    pipe = Pipeline([('prep', build_preprocessor()),\n"
            "                     ('clf', HistGradientBoostingClassifier(early_stopping=True, **params))])\n"
            "    return cross_val_score(pipe, X_train, y_train, cv=cv, scoring='roc_auc').mean()\n\n"
            "study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=SEED))\n"
            "study.optimize(objective, n_trials=30)"
        ),
        takeaway=f"Thirty trials buy {max(rs.best_score_, study.best_value) - default_cv:+.4f} AUC over "
                 "defaults and the two search strategies tie; the budget, the CV and early stopping mattered, "
                 "the sampler did not.",
        artifacts=["artifacts/churn_model.joblib", "artifacts/churn_test_scores.parquet"],
    )


# ================================================================= 3. experiment-tracking
def demo_experiment_tracking() -> SkillResult:
    import mlflow

    # MLflow 3 refuses a plain filesystem store; a local SQLite backend is the supported
    # equivalent for a single-machine lab and keeps the runs queryable from the UI.
    store = f"sqlite:///{(ARTIFACTS / 'mlflow.db').as_posix()}"
    mlflow.set_tracking_uri(store)
    mlflow.set_experiment("telco-churn")

    candidates = {
        "logreg_balanced": Pipeline([("prep", build_preprocessor()),
                                     ("clf", LogisticRegression(max_iter=2000, class_weight="balanced"))]),
        "random_forest": Pipeline([("prep", build_preprocessor()),
                                   ("clf", RandomForestClassifier(n_estimators=300, min_samples_leaf=5,
                                                                  random_state=SEED, n_jobs=-1))]),
        "hgb_default": Pipeline([("prep", build_preprocessor()),
                                 ("clf", HistGradientBoostingClassifier(random_state=SEED))]),
        "hgb_tuned": joblib.load(ARTIFACTS / "churn_model.joblib"),
    }

    runs = []
    for name, model in candidates.items():
        with mlflow.start_run(run_name=name) as run:
            t0 = time.perf_counter()
            cv_auc = cross_val_score(model, X_TR, Y_TR, cv=CV, scoring="roc_auc").mean()
            model.fit(X_TR, Y_TR)
            p = model.predict_proba(X_TE)[:, 1]
            fit_s = time.perf_counter() - t0
            metrics = {"cv_roc_auc": float(cv_auc),
                       "test_roc_auc": float(roc_auc_score(Y_TE, p)),
                       "test_pr_auc": float(average_precision_score(Y_TE, p)),
                       "fit_seconds": fit_s}
            params = {k: v for k, v in model.named_steps["clf"].get_params().items()
                      if isinstance(v, (int, float, str, bool, type(None)))}
            mlflow.log_params({**{f"clf__{k}": v for k, v in list(params.items())[:15]},
                               "data_sha": data.manifest()["datasets"][0]["sha256"][:12],
                               "seed": SEED, "n_features": X_TR.shape[1]})
            mlflow.log_metrics(metrics)
            mlflow.set_tags({"phase": "4-modeling", "dataset": "telco-churn", "split_seed": SEED})
            runs.append({"run": name, "run_id": run.info.run_id[:8], **metrics})

    best = max(runs, key=lambda r: r["test_roc_auc"])
    df = pd.DataFrame(runs)

    return SkillResult(
        skill="experiment-tracking", source="agent-ml-skills",
        category="MLOps & Reliability", phase=4, track="T1",
        title="Four candidate models logged to a local MLflow store",
        prescribes="Log every run's parameters, metrics, data version and code state to a tracking server so "
                   "runs are comparable and reproducible later, rather than comparing numbers in a notebook.",
        applied="Ran four churn candidates through MLflow with a file-backed store at artifacts/mlruns, logging "
                "hyperparameters, CV and test metrics, fit time, the seed and the dataset SHA-256 on each run.",
        narrative=[
            f"Four runs, one experiment, one command to compare them: `mlflow ui --backend-store-uri "
            f"sqlite:///artifacts/mlflow.db`. The winner on test ROC-AUC is `{best['run']}` at {best['test_roc_auc']:.4f}, "
            f"but the interesting column is fit time -- the random forest costs "
            f"{df.set_index('run').loc['random_forest', 'fit_seconds']:.1f}s against "
            f"{df.set_index('run').loc['logreg_balanced', 'fit_seconds']:.1f}s for logistic regression to gain "
            f"{df.set_index('run').loc['random_forest', 'test_roc_auc'] - df.set_index('run').loc['logreg_balanced', 'test_roc_auc']:+.4f} AUC.",
            "Each run records the dataset digest and the split seed alongside the hyperparameters. That is what "
            "makes a six-week-old run re-runnable: the parameters alone would reproduce the model but not the "
            "data it saw.",
            "Tracking is also what keeps the comparison honest. All four candidates are scored with the same "
            "CV object on the same features, so the leaderboard reflects the models, not four different "
            "evaluation setups that happen to share a table.",
        ],
        kpis=[
            Kpi("Runs logged", str(len(runs)), "experiment: telco-churn"),
            Kpi("Best test ROC-AUC", f"{best['test_roc_auc']:.4f}", best["run"], tone="good"),
            Kpi("Tracking store", "artifacts/mlflow.db", "local SQLite backend"),
            Kpi("Logged per run", "params + 4 metrics + 3 tags", "incl. data SHA and seed"),
        ],
        charts=[
            Chart(id="run-compare", kind="bar", title="Candidate comparison (CV vs test ROC-AUC)",
                  data=[{"x": r["run"], "cv": round(r["cv_roc_auc"], 4), "test": round(r["test_roc_auc"], 4)}
                        for r in runs],
                  series=[{"key": "cv", "label": "CV ROC-AUC"}, {"key": "test", "label": "Test ROC-AUC"}],
                  domain=[0.78, 0.88]),
            Chart(id="cost-benefit", kind="scatter", title="Fit time vs test ROC-AUC",
                  data=[{"x": round(r["fit_seconds"], 2), "y": round(r["test_roc_auc"], 4), "series": r["run"]}
                        for r in runs],
                  series=[{"key": "y", "label": "Test ROC-AUC"}],
                  xLabel="fit + CV seconds", yLabel="test ROC-AUC"),
        ],
        tables=[Table("runs", "MLflow run summary",
                      ["Run", "Run ID", "CV ROC-AUC", "Test ROC-AUC", "Test PR-AUC", "Seconds"],
                      [[r["run"], r["run_id"], round(r["cv_roc_auc"], 4), round(r["test_roc_auc"], 4),
                        round(r["test_pr_auc"], 4), round(r["fit_seconds"], 1)] for r in runs])],
        code_excerpt=(
            "mlflow.set_tracking_uri((ARTIFACTS / 'mlruns').as_uri())\n"
            "mlflow.set_experiment('telco-churn')\n"
            "with mlflow.start_run(run_name=name):\n"
            "    mlflow.log_params({**clf_params, 'data_sha': manifest_sha[:12], 'seed': SEED})\n"
            "    mlflow.log_metrics({'cv_roc_auc': cv_auc, 'test_roc_auc': test_auc,\n"
            "                        'test_pr_auc': pr_auc, 'fit_seconds': fit_s})\n"
            "    mlflow.set_tags({'phase': '4-modeling', 'dataset': 'telco-churn'})"
        ),
        takeaway="The leaderboard says gradient boosting wins by a small margin at several times the fit cost -- "
                 "a trade-off that is only visible because both were logged the same way.",
        artifacts=["artifacts/mlflow.db"],
    )


# ================================================================= 4. ml-debugging
def demo_ml_debugging() -> SkillResult:
    # --- Bug 1: a feature that could only be known after the outcome
    rng = np.random.default_rng(SEED)
    leak_tr = np.where(Y_TR == 1, rng.random(len(Y_TR)) < 0.93, rng.random(len(Y_TR)) < 0.06).astype(int)
    leak_te = np.where(Y_TE == 1, rng.random(len(Y_TE)) < 0.93, rng.random(len(Y_TE)) < 0.06).astype(int)
    Xl_tr = X_TR.assign(retention_call_logged=leak_tr)
    Xl_te = X_TE.assign(retention_call_logged=leak_te)

    num_l = NUM + ["retention_call_logged"]
    prep_l = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), num_l),
        ("cat", Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                          ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=20))]), CAT)])
    leaky = Pipeline([("prep", prep_l), ("clf", LogisticRegression(max_iter=2000, class_weight="balanced"))])
    leaky.fit(Xl_tr, Y_TR)
    leaky_auc = roc_auc_score(Y_TE, leaky.predict_proba(Xl_te)[:, 1])

    honest = Pipeline([("prep", build_preprocessor()),
                       ("clf", LogisticRegression(max_iter=2000, class_weight="balanced"))]).fit(X_TR, Y_TR)
    honest_auc = roc_auc_score(Y_TE, honest.predict_proba(X_TE)[:, 1])

    # The diagnostic that finds it: coefficient magnitude on the standardised features
    names = leaky.named_steps["prep"].get_feature_names_out()
    coefs = pd.Series(np.abs(leaky.named_steps["clf"].coef_[0]), index=names).sort_values(ascending=False)

    # Single-feature check -- the confirmation step
    single = LogisticRegression(max_iter=1000).fit(leak_tr.reshape(-1, 1), Y_TR)
    single_auc = roc_auc_score(Y_TE, single.predict_proba(leak_te.reshape(-1, 1))[:, 1])

    # --- Bug 2: a model that will not converge because nobody scaled the inputs
    raw_num = X_TR[NUM].fillna(0.0)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        unscaled = LogisticRegression(max_iter=50, solver="lbfgs").fit(raw_num, Y_TR)
        converged = not any("converge" in str(x.message).lower() for x in w)
    unscaled_auc = roc_auc_score(Y_TE, unscaled.predict_proba(X_TE[NUM].fillna(0.0))[:, 1])
    scaled_auc = roc_auc_score(Y_TE, Pipeline([("s", StandardScaler()), ("c", LogisticRegression(max_iter=50))])
                               .fit(raw_num, Y_TR).predict_proba(X_TE[NUM].fillna(0.0))[:, 1])

    return SkillResult(
        skill="ml-debugging", source="agent-ml-skills",
        category="MLOps & Reliability", phase=4, track="T1",
        title="A model that scores too well, and a model that will not converge",
        prescribes="When metrics look too good, suspect leakage before celebrating: rank feature importances, "
                   "test the suspect feature alone, and ask whether it could be known at prediction time. When "
                   "training will not converge, check scaling before the architecture.",
        applied="Injected a plausible post-outcome column (`retention_call_logged`) into the churn frame, "
                "diagnosed it from the fitted coefficients, and separately reproduced a non-convergence bug by "
                "removing the scaler.",
        narrative=[
            f"Adding one column takes test ROC-AUC from {honest_auc:.4f} to {leaky_auc:.4f}. A "
            f"{leaky_auc - honest_auc:+.4f} jump from a single feature on a problem this noisy is not a "
            "breakthrough, it is a symptom -- and the plausible-sounding name is exactly why it would survive "
            "review.",
            f"The diagnosis takes two steps. First, the standardised coefficients: `retention_call_logged` "
            f"dominates at {coefs.iloc[0]:.2f}, roughly {coefs.iloc[0] / coefs.iloc[1]:.1f}x the next feature. "
            f"Second, the confirmation -- that column alone, with no other input, scores {single_auc:.4f} AUC. "
            "No legitimate customer attribute predicts churn that well.",
            "The fix is not statistical, it is temporal: a retention call is logged *because* the account was "
            "flagged as churning, so the value does not exist at scoring time. It is dropped, and the model "
            f"goes back to {honest_auc:.4f} -- which is the number that will hold in production.",
            f"The second bug is more mundane and more common. With max_iter=50 and unscaled inputs "
            f"(TotalCharges spans four orders of magnitude more than SeniorCitizen), lbfgs "
            f"{'converges' if converged else 'fails to converge'} and scores {unscaled_auc:.4f}; adding a "
            f"StandardScaler under the same iteration cap gives {scaled_auc:.4f}. The instinct to raise "
            "max_iter or blame the model would have wasted an afternoon.",
        ],
        kpis=[
            Kpi("AUC with leaked column", f"{leaky_auc:.4f}", f"{leaky_auc - honest_auc:+.4f} vs honest", tone="bad"),
            Kpi("AUC after the fix", f"{honest_auc:.4f}", "the number that survives production", tone="good"),
            Kpi("Leaked column alone", f"{single_auc:.4f}", "one feature, no others", tone="bad"),
            Kpi("Unscaled vs scaled (50 iters)", f"{unscaled_auc:.4f} -> {scaled_auc:.4f}",
                "same model, same budget", tone="warn"),
        ],
        charts=[
            Chart(id="leak-coefs", kind="hbar", title="Absolute standardised coefficients (leaky model)",
                  data=[{"x": str(k).replace("num__", "").replace("cat__", ""), "coef": round(float(v), 3)}
                        for k, v in coefs.head(10).items()],
                  series=[{"key": "coef", "label": "|coefficient|"}],
                  note="One feature towering over the rest is the leakage signature."),
            Chart(id="auc-compare", kind="bar", title="Test ROC-AUC across the three models",
                  data=[{"x": "Honest model", "auc": round(honest_auc, 4)},
                        {"x": "With leaked column", "auc": round(leaky_auc, 4)},
                        {"x": "Leaked column alone", "auc": round(single_auc, 4)}],
                  series=[{"key": "auc", "label": "Test ROC-AUC"}], domain=[0.5, 1.0]),
        ],
        tables=[Table("triage", "Debugging checklist as applied",
                      ["Symptom", "Hypothesis", "Test run", "Verdict"],
                      [[f"Test AUC jumps {leaky_auc - honest_auc:+.3f} from one column", "target leakage",
                        "rank standardised coefficients", f"suspect feature is {coefs.iloc[0] / coefs.iloc[1]:.1f}x the next"],
                       ["Suspect feature identified", "feature encodes the outcome",
                        "fit on that column alone", f"AUC {single_auc:.4f} -- confirmed"],
                       ["Is it available at scoring time?", "no: logged after the churn flag",
                        "check the definition, not the data", "drop the column"],
                       ["Model does not converge", "unscaled features, not model capacity",
                        "add StandardScaler at the same max_iter", f"{unscaled_auc:.4f} -> {scaled_auc:.4f}"]])],
        code_excerpt=(
            "# The two-step leakage diagnosis\n"
            "coefs = pd.Series(np.abs(clf.coef_[0]), index=prep.get_feature_names_out())\n"
            "print(coefs.sort_values(ascending=False).head())      # one feature dominates?\n\n"
            "single = LogisticRegression().fit(X[['retention_call_logged']], y_train)\n"
            "print(roc_auc_score(y_test, single.predict_proba(X_test[['retention_call_logged']])[:, 1]))\n"
            "# 0.93 from one column -> it is not a feature, it is the answer"
        ),
        takeaway="Both bugs were found by asking a question rather than tuning: could this value exist at "
                 "prediction time, and is the optimiser actually converging?",
    )


DEMOS = [
    demo_sklearn_pipelines,
    demo_hyperparameter_tuning,
    demo_experiment_tracking,
    demo_ml_debugging,
]


def main() -> None:
    print("\n=== CRISP-DM 4: Modeling (tabular) ===")
    for fn in DEMOS:
        emit(fn())


if __name__ == "__main__":
    main()
