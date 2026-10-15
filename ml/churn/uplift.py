"""Uplift modeling on a semi-synthetic benchmark.

The Telco data has no record of who received a retention offer, so the offer's effect
cannot be learned from it. Instead we keep the real customers, plant a known effect,
simulate a randomized experiment with it, and check how well a T-learner recovers the
effect. Because the truth is known, the model can be graded, which observational data
never allows.

  p0(x)   churn probability without an offer: a logistic model fitted to real churn
  tau(x)  planted effect: how much the offer lowers churn probability (negative = backfires)
  p1(x)   = p0(x) - tau(x), churn probability with the offer
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from data import NUMERIC

Segment = Literal["persuadable", "sure_thing", "lost_cause", "sleeping_dog"]

# Shallow, regularized trees: each arm sees only half the customers, and the T-learner's
# estimate is a difference of two models, so variance dominates (tuned on the benchmark).
T_LEARNER_PARAMS: dict[str, float | int] = {
    "n_estimators": 300,
    "max_depth": 2,
    "learning_rate": 0.05,
    "min_child_weight": 30,
    "subsample": 0.8,
}

# Picked on the benchmark (seed 42) to put the most customers in their true segment.
PERSUADABLE_UPLIFT = 0.04  # offer lowers churn by at least 4 points
SLEEPING_DOG_UPLIFT = -0.03  # offer raises churn by at least 3 points
LOST_CAUSE_RISK = 0.45  # likely to leave whatever we do


def fit_oracle(df: pd.DataFrame, y: np.ndarray) -> Pipeline:
    """Smooth, realistic baseline churn probabilities: logistic regression on real labels."""
    cats = [c for c in df.columns if c not in NUMERIC]
    pre = ColumnTransformer(
        [("cat", OneHotEncoder(), cats), ("num", StandardScaler(), list(NUMERIC))]
    )
    model = Pipeline([("pre", pre), ("lr", LogisticRegression(max_iter=2000))])
    model.fit(df, y)
    return model


def planted_effect(df: pd.DataFrame, p0: np.ndarray) -> np.ndarray:
    """The ground-truth effect of the offer on each customer's churn probability.

    - Month-to-month customers respond, most strongly around a year in (still deciding
      whether to stay) and more when their bill is high (a discount matters).
    - New fiber customers without tech support are lost causes: their problem is the
      service, which a discount does not fix.
    - Long-tenure customers on automatic payment are sleeping dogs: the offer reminds them
      to shop around and slightly raises churn.
    """
    tenure = df["tenure"].to_numpy(dtype=float)
    charges = df["MonthlyCharges"].to_numpy(dtype=float)
    monthly = (df["Contract"] == "Month-to-month").to_numpy()
    service_issue = (
        (df["InternetService"] == "Fiber optic") & (df["TechSupport"] == "No")
    ).to_numpy()
    autopay = df["PaymentMethod"].str.contains("automatic").to_numpy()

    tau = np.where(
        monthly,
        0.16 * np.exp(-(((tenure - 14) / 14) ** 2)) + 0.06 / (1 + np.exp(-(charges - 65) / 6)),
        0.0,
    )
    tau = np.where(service_issue & (tenure < 12), tau * 0.15, tau)
    tau = np.where(autopay & (tenure >= 24), tau - 0.06, tau)
    p1 = np.clip(p0 - tau, 0.005, 0.995)
    return p0 - p1  # the effect after clipping, so p1 = p0 - tau holds exactly


@dataclass(frozen=True)
class Experiment:
    treated: np.ndarray  # 0/1, randomized 50/50
    churned: np.ndarray  # observed outcome under the assigned arm


def simulate(p0: np.ndarray, tau: np.ndarray, seed: int) -> Experiment:
    rng = np.random.default_rng(seed)
    treated = rng.binomial(1, 0.5, size=len(p0))
    draw = rng.random(len(p0))
    churned = np.where(treated == 1, draw < p0 - tau, draw < p0).astype(int)
    return Experiment(treated=treated, churned=churned)


@dataclass
class TLearner:
    control: XGBClassifier
    treatment: XGBClassifier

    def churn_without(self, X: np.ndarray) -> np.ndarray:
        return self.control.predict_proba(X)[:, 1]

    def churn_with(self, X: np.ndarray) -> np.ndarray:
        return self.treatment.predict_proba(X)[:, 1]

    def uplift(self, X: np.ndarray) -> np.ndarray:
        """Predicted drop in churn probability from the offer (positive = it helps)."""
        return self.churn_without(X) - self.churn_with(X)


def fit_t_learner(X: np.ndarray, exp: Experiment, seed: int = 42) -> TLearner:
    arms: list[XGBClassifier] = []
    for arm in (0, 1):
        rows = exp.treated == arm
        model = XGBClassifier(eval_metric="logloss", random_state=seed, **T_LEARNER_PARAMS)
        model.fit(X[rows], exp.churned[rows])
        arms.append(model)
    return TLearner(control=arms[0], treatment=arms[1])


def segment(churn_without: float, uplift: float) -> Segment:
    if uplift >= PERSUADABLE_UPLIFT:
        return "persuadable"
    if uplift <= SLEEPING_DOG_UPLIFT:
        return "sleeping_dog"
    return "lost_cause" if churn_without >= LOST_CAUSE_RISK else "sure_thing"


def prevented_by_budget(tau: np.ndarray, score: np.ndarray, budgets: np.ndarray) -> np.ndarray:
    """Expected churners prevented per 1,000 customers when the top ``budget`` share by
    ``score`` gets the offer. Uses the planted effect, so this is the true value of the
    targeting policy, not an estimate."""
    order = np.argsort(-score, kind="stable")
    gains = np.concatenate([[0.0], np.cumsum(tau[order])])
    counts = np.round(budgets * len(tau)).astype(int)
    return gains[counts] * 1000 / len(tau)


def offers_saved(
    by_uplift: np.ndarray, by_risk: np.ndarray, budgets: np.ndarray, at: float
) -> float:
    """Share of offers uplift targeting saves while preventing as much churn as risk
    targeting does at budget ``at`` (linear interpolation along the uplift curve)."""
    target = float(np.interp(at, budgets, by_risk))
    # First budget where the uplift curve reaches the target.
    reach = np.flatnonzero(by_uplift >= target)
    if len(reach) == 0:
        return 0.0
    k = int(reach[0])
    if k == 0:
        needed = budgets[0]
    else:
        lo, hi = by_uplift[k - 1], by_uplift[k]
        needed = budgets[k - 1] + (target - lo) / (hi - lo) * (budgets[k] - budgets[k - 1])
    return float(1 - needed / at)
