import numpy as np
import pandas as pd

import uplift


def customers() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "tenure": [14, 14, 3, 60, 30, 14],
            "MonthlyCharges": [90.0, 90.0, 95.0, 50.0, 40.0, 30.0],
            "Contract": [
                "Month-to-month",
                "Two year",
                "Month-to-month",
                "Two year",
                "One year",
                "Month-to-month",
            ],
            "InternetService": ["DSL", "DSL", "Fiber optic", "DSL", "No", "DSL"],
            "TechSupport": ["Yes", "Yes", "No", "Yes", "No internet service", "No"],
            "PaymentMethod": [
                "Electronic check",
                "Electronic check",
                "Electronic check",
                "Credit card (automatic)",
                "Mailed check",
                "Mailed check",
            ],
        }
    )


def test_planted_effect_has_the_documented_structure() -> None:
    p0 = np.full(6, 0.5)
    tau = uplift.planted_effect(customers(), p0)
    monthly_mid, two_year, new_fiber_issue, long_autopay, one_year, monthly_cheap = tau
    assert monthly_mid > 0.15  # persuadable: month-to-month, ~a year in, high bill
    assert two_year == 0  # contracted customers are unaffected
    assert 0 < new_fiber_issue < 0.03  # lost cause: the problem is the service
    assert long_autopay < 0  # sleeping dog: the offer backfires
    assert one_year == 0
    assert monthly_mid > monthly_cheap > 0  # a discount matters more on a high bill


def test_planted_effect_keeps_probabilities_valid() -> None:
    p0 = np.array([0.01, 0.99, 0.5, 0.97, 0.3, 0.004])
    tau = uplift.planted_effect(customers(), p0)
    p1 = p0 - tau
    assert np.all((p1 >= 0.005 - 1e-12) & (p1 <= 0.995 + 1e-12))


def test_simulate_is_deterministic_and_randomized() -> None:
    p0 = np.full(4000, 0.3)
    tau = np.full(4000, 0.1)
    a = uplift.simulate(p0, tau, seed=3)
    b = uplift.simulate(p0, tau, seed=3)
    assert np.array_equal(a.treated, b.treated) and np.array_equal(a.churned, b.churned)
    assert 0.45 < a.treated.mean() < 0.55
    control = a.churned[a.treated == 0].mean()
    treated = a.churned[a.treated == 1].mean()
    assert abs(control - 0.3) < 0.03 and abs(treated - 0.2) < 0.03


def test_segments() -> None:
    assert uplift.segment(0.6, 0.10) == "persuadable"
    assert uplift.segment(0.1, -0.05) == "sleeping_dog"
    assert uplift.segment(0.7, 0.01) == "lost_cause"
    assert uplift.segment(0.1, 0.01) == "sure_thing"


def test_prevented_by_budget_counts_true_effects_in_score_order() -> None:
    tau = np.array([0.5, 0.0, 0.3, -0.2])
    score = np.array([4.0, 3.0, 2.0, 1.0])
    budgets = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    got = uplift.prevented_by_budget(tau, score, budgets)
    assert np.allclose(got, np.array([0, 0.5, 0.5, 0.8, 0.6]) * 1000 / 4)


def test_offers_saved_interpolates_along_the_uplift_curve() -> None:
    budgets = np.array([0.0, 0.1, 0.2, 0.3])
    by_uplift = np.array([0.0, 20.0, 30.0, 35.0])
    by_risk = np.array([0.0, 10.0, 20.0, 28.0])
    # Risk reaches 20 at a 20% budget; uplift reaches 20 at 10%: half the offers.
    assert abs(uplift.offers_saved(by_uplift, by_risk, budgets, at=0.2) - 0.5) < 1e-9
    # Never reached: no saving claimed.
    assert uplift.offers_saved(np.zeros(4), by_risk, budgets, at=0.2) == 0.0


def test_t_learner_recovers_a_strong_effect() -> None:
    rng = np.random.default_rng(0)
    n = 6000
    X = rng.normal(size=(n, 3))
    p0 = np.full(n, 0.4)
    tau = np.where(X[:, 0] > 0, 0.25, 0.0)
    exp = uplift.simulate(p0, tau, seed=1)
    learner = uplift.fit_t_learner(X, exp)
    u = learner.uplift(X)
    assert u[X[:, 0] > 0.5].mean() > 0.15
    assert abs(u[X[:, 0] < -0.5].mean()) < 0.07
