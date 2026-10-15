"""Train the Churn Lab models and export them for the browser.

    uv run python train.py

Writes frontend/public/models/churn-lab.json (models, metrics, presets) and the parity
fixture the frontend tests check the TypeScript evaluator against.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from xgboost import DMatrix, XGBClassifier

import trees
import uplift
from data import NUMERIC, Encoding, fit_encoding, load

ROOT = Path(__file__).resolve().parents[2]
MODEL_OUT = ROOT / "frontend" / "public" / "models" / "churn-lab.json"
FIXTURE_OUT = ROOT / "frontend" / "tests" / "fixtures" / "churn-parity.json"

# The customer-churn-mlops notebook's configuration (1.eda.ipynb, cell 5).
CHURN_PARAMS: dict[str, float | int] = {
    "n_estimators": 200,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
}
SEEDS = (
    42,
    7,
    13,
    99,
    2027,
)  # simulated experiments; the first one's model is exported
BUDGETS = np.round(np.arange(0, 1.0001, 0.05), 2)


def r(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def fit_churn(
    X: np.ndarray, y: np.ndarray, seed: int
) -> tuple[XGBClassifier, np.ndarray, np.ndarray]:
    """SMOTE + XGBoost, exactly as the project trains it. Returns the model and the
    holdout rows and labels."""
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=seed, stratify=y)
    # Integer columns (category codes, tenure) stay integers through SMOTE, as in the
    # notebook's DataFrame, so synthetic customers never get a fractional category.
    frame = pd.DataFrame(X_tr)
    whole = [j for j in frame.columns if np.all(X[:, j] == np.round(X[:, j]))]
    frame = frame.astype({j: "int64" for j in whole})
    X_sm, y_sm = SMOTE(random_state=seed).fit_resample(frame, y_tr)
    model = XGBClassifier(eval_metric="logloss", random_state=seed, **CHURN_PARAMS)
    model.fit(X_sm.to_numpy(dtype=np.float64), y_sm)
    return model, X_te, y_te


def train_churn(X: np.ndarray, y: np.ndarray) -> tuple[XGBClassifier, dict[str, Any], np.ndarray]:
    """The exported model (seed 42) with its holdout metrics, plus the AUC spread over
    repeated splits so one lucky split is not the headline."""
    model, X_te, y_te = fit_churn(X, y, seed=42)
    repeated = []
    for seed in SEEDS:
        m, xt, yt = fit_churn(X, y, seed)
        repeated.append(roc_auc_score(yt, m.predict_proba(xt)[:, 1]))

    prob = model.predict_proba(X_te)[:, 1]
    pred = (prob >= 0.5).astype(int)
    fpr, tpr, _ = roc_curve(y_te, prob)
    keep = np.unique(np.linspace(0, len(fpr) - 1, 60).round().astype(int))
    contribs = model.get_booster().predict(DMatrix(X_te), pred_contribs=True)
    metrics = {
        "auc": r(roc_auc_score(y_te, prob)),
        "aucSplits": {
            "mean": r(np.mean(repeated)),
            "sd": r(np.std(repeated)),
            "n": len(repeated),
        },
        "precision": r(precision_score(y_te, pred)),
        "recall": r(recall_score(y_te, pred)),
        "f1": r(f1_score(y_te, pred)),
        "testSize": len(y_te),
        "churnRate": r(y.mean()),
        "roc": [[r(fpr[i], 3), r(tpr[i], 3)] for i in keep],
        # Risk scores of the holdout customers at each percentile, so the page can say
        # "riskier than N% of customers" (SMOTE shifts raw probabilities upward).
        "riskQuantiles": [r(q) for q in np.quantile(prob, np.linspace(0, 1, 101))],
        # Mean |SHAP| per feature over the holdout (log-odds), the global importance.
        "importance": [r(v) for v in np.abs(contribs[:, :-1]).mean(axis=0)],
    }
    return model, metrics, X_te


def benchmark_uplift(
    df: pd.DataFrame, X: np.ndarray, y: np.ndarray
) -> tuple[uplift.TLearner, dict[str, Any], np.ndarray, np.ndarray, np.ndarray]:
    oracle = uplift.fit_oracle(df, y)
    p0 = oracle.predict_proba(df)[:, 1]
    tau = uplift.planted_effect(df, p0)

    curves: dict[str, list[np.ndarray]] = {
        "uplift": [],
        "risk": [],
        "random": [],
        "oracle": [],
    }
    corrs: list[float] = []
    saved: list[float] = []
    exported: tuple[uplift.TLearner, np.ndarray] | None = None
    idx = np.arange(len(df))
    for seed in SEEDS:
        exp = uplift.simulate(p0, tau, seed)
        tr, te = train_test_split(
            idx,
            test_size=0.3,
            random_state=seed,
            stratify=exp.treated * 2 + exp.churned,
        )
        learner = uplift.fit_t_learner(
            X[tr], uplift.Experiment(exp.treated[tr], exp.churned[tr]), seed
        )
        u = learner.uplift(X[te])
        risk = learner.churn_without(X[te])
        corrs.append(float(np.corrcoef(u, tau[te])[0, 1]))
        by_uplift = uplift.prevented_by_budget(tau[te], u, BUDGETS)
        by_risk = uplift.prevented_by_budget(tau[te], risk, BUDGETS)
        curves["uplift"].append(by_uplift)
        curves["risk"].append(by_risk)
        curves["random"].append(BUDGETS * tau[te].mean() * 1000)
        curves["oracle"].append(uplift.prevented_by_budget(tau[te], tau[te], BUDGETS))
        saved.append(uplift.offers_saved(by_uplift, by_risk, BUDGETS, at=0.2))
        if exported is None:
            exported = (learner, te)
    assert exported is not None
    learner, te = exported

    without = learner.churn_without(X[te])
    lift = learner.uplift(X[te])
    segments = np.array([uplift.segment(a, b) for a, b in zip(without, lift, strict=True)])
    truth = np.array([uplift.segment(a, b) for a, b in zip(p0[te], tau[te], strict=True)])
    by_segment = {
        s: {
            "share": r((segments == s).mean(), 3),
            "trueEffect": r(tau[te][segments == s].mean()),
        }
        for s in ("persuadable", "sure_thing", "lost_cause", "sleeping_dog")
    }

    i20 = int(np.flatnonzero(BUDGETS == 0.2)[0])
    gain20 = [c[i20] / k[i20] - 1 for c, k in zip(curves["uplift"], curves["risk"], strict=True)]
    report = {
        "params": uplift.T_LEARNER_PARAMS,
        "thresholds": {
            "persuadable": uplift.PERSUADABLE_UPLIFT,
            "sleepingDog": uplift.SLEEPING_DOG_UPLIFT,
            "lostCause": uplift.LOST_CAUSE_RISK,
        },
        "seeds": list(SEEDS),
        "budgets": BUDGETS.tolist(),
        "curves": {k: [r(v, 2) for v in np.mean(c, axis=0)] for k, c in curves.items()},
        "correlation": {"mean": r(np.mean(corrs), 3), "sd": r(np.std(corrs), 3)},
        "gainAt20": {"mean": r(np.mean(gain20), 3), "sd": r(np.std(gain20), 3)},
        "offersSavedAt20": {"mean": r(np.mean(saved), 3), "sd": r(np.std(saved), 3)},
        "plantedMean": r(tau.mean()),
        "segments": by_segment,
        # Share of holdout customers the model puts in their true (planted) segment.
        "segmentAccuracy": r((segments == truth).mean(), 3),
        "errorSd": r(np.std(lift - tau[te]), 3),
    }
    return learner, report, te, segments, truth


def presets(
    df: pd.DataFrame,
    X: np.ndarray,
    learner: uplift.TLearner,
    te: np.ndarray,
    segments: np.ndarray,
    truth: np.ndarray,
) -> list[dict[str, Any]]:
    """One typical holdout customer per segment: the median by uplift among customers the
    model places correctly, so each example agrees with the planted rules it illustrates."""
    out: list[dict[str, Any]] = []
    lift = learner.uplift(X[te])
    for seg in ("persuadable", "sure_thing", "lost_cause", "sleeping_dog"):
        rows = np.flatnonzero((segments == seg) & (truth == seg))
        if len(rows) == 0:
            continue
        pick = rows[np.argsort(lift[rows])[len(rows) // 2]]
        record = df.iloc[int(te[pick])]
        values = {c: (float(record[c]) if c in NUMERIC else str(record[c])) for c in df.columns}
        out.append({"segment": seg, "values": values})
    return out


def feature_spec(df: pd.DataFrame, enc: Encoding) -> list[dict[str, Any]]:
    spec: list[dict[str, Any]] = []
    for col in enc.columns:
        if col in enc.levels:
            spec.append({"name": col, "kind": "category", "levels": enc.levels[col]})
        else:
            spec.append(
                {
                    "name": col,
                    "kind": "number",
                    "min": r(df[col].min(), 2),
                    "max": r(df[col].max(), 2),
                }
            )
    return spec


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--csv", type=Path, help="local copy of the dataset (default: download)")
    parser.add_argument("--out", type=Path, default=MODEL_OUT)
    parser.add_argument("--fixture", type=Path, default=FIXTURE_OUT)
    args = parser.parse_args()

    df, y = load(args.csv)
    enc = fit_encoding(df)
    X = enc.transform(df)

    churn_model, churn_metrics, X_te = train_churn(X, y)
    learner, uplift_report, te, segments, truth = benchmark_uplift(df, X, y)

    payload = {
        "version": 1,
        "source": "https://github.com/thechiragbatra/customer-churn-mlops",
        "features": feature_spec(df, enc),
        "churn": {
            "model": trees.export(churn_model.get_booster()),
            "params": CHURN_PARAMS,
            "metrics": churn_metrics,
        },
        "uplift": {
            "control": trees.export(learner.control.get_booster()),
            "treatment": trees.export(learner.treatment.get_booster()),
            **uplift_report,
        },
        "presets": presets(df, X, learner, te, segments, truth),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, separators=(",", ":")))

    # Parity fixture: XGBoost's own margins and TreeSHAP values for 40 holdout rows.
    rows = X_te[:40]
    booster = churn_model.get_booster()
    fixture = {
        "rows": rows.tolist(),
        "churnMargin": booster.predict(DMatrix(rows), output_margin=True).tolist(),
        "churnContribs": booster.predict(DMatrix(rows), pred_contribs=True).tolist(),
        "controlMargin": learner.control.predict(rows, output_margin=True).tolist(),
        "treatmentMargin": learner.treatment.predict(rows, output_margin=True).tolist(),
    }
    args.fixture.parent.mkdir(parents=True, exist_ok=True)
    args.fixture.write_text(json.dumps(fixture))

    size = args.out.stat().st_size / 1024
    m, u = churn_metrics, uplift_report
    print(f"churn   AUC {m['auc']} (splits {m['aucSplits']})")
    print(f"        recall {m['recall']}  precision {m['precision']}")
    print(f"uplift  corr(pred, planted) {u['correlation']}  gain@20% {u['gainAt20']}")
    print(f"        offers saved@20% {u['offersSavedAt20']}")
    print(f"        segment accuracy {u['segmentAccuracy']}  error sd {u['errorSd']}")
    print(f"        segments {u['segments']}")
    print(f"wrote {args.out.relative_to(ROOT)} ({size:.0f} KiB), {args.fixture.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
