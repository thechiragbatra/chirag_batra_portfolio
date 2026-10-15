"""The Python port of the Churn Lab models must match XGBoost exactly, like the browser."""

import json
from pathlib import Path

import pytest

from agents.guide import churn

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
FIXTURE = json.loads((FRONTEND / "tests" / "fixtures" / "churn-parity.json").read_text())


@pytest.fixture(scope="module")
def lab() -> churn.Lab:
    return churn.load_lab(FRONTEND / "public" / "models" / "churn-lab.json")


def test_margins_match_xgboost(lab: churn.Lab) -> None:
    for i, row in enumerate(FIXTURE["rows"]):
        assert abs(churn.predict_margin(lab.churn, row) - FIXTURE["churnMargin"][i]) < 1e-4
        assert abs(churn.predict_margin(lab.control, row) - FIXTURE["controlMargin"][i]) < 1e-4
        assert abs(churn.predict_margin(lab.treatment, row) - FIXTURE["treatmentMargin"][i]) < 1e-4


def test_shap_values_match_xgboost_pred_contribs(lab: churn.Lab) -> None:
    for i, row in enumerate(FIXTURE["rows"][:15]):
        phi = churn.shap_values(lab.churn, row)
        for j, expected in enumerate(FIXTURE["churnContribs"][i]):
            assert abs(phi[j] - expected) < 1e-4, (i, j)


def test_fround_rounds_to_float32() -> None:
    assert churn.fround(0.1) == 0.10000000149011612
    assert churn.fround(1.0) == 1.0


def test_apply_changes_keeps_the_customer_consistent(lab: churn.Lab) -> None:
    base = lab.presets["persuadable"]
    off = churn.apply_changes(lab, base, {"InternetService": "No"})
    assert all(off[a] == "No internet service" for a in churn.INTERNET_ADDONS)
    on = churn.apply_changes(lab, off, {"InternetService": "DSL"})
    assert all(on[a] == "No" for a in churn.INTERNET_ADDONS)
    no_phone = churn.apply_changes(lab, base, {"PhoneService": "No"})
    assert no_phone["MultipleLines"] == "No phone service"
    longer = churn.apply_changes(lab, base, {"tenure": 10, "MonthlyCharges": 50})
    assert longer["TotalCharges"] == 500.0
    assert base["tenure"] != 10  # the preset itself is untouched


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"Salary": 10}, "unknown attribute"),
        ({"Contract": "Lifetime"}, "must be one of"),
        ({"tenure": 500}, "between"),
        ({"MonthlyCharges": "lots"}, "must be a number"),
    ],
)
def test_apply_changes_rejects_bad_input(lab: churn.Lab, changes: dict, message: str) -> None:
    with pytest.raises(churn.CustomerError, match=message):
        churn.apply_changes(lab, lab.presets["persuadable"], changes)


def test_presets_score_into_their_own_segment(lab: churn.Lab) -> None:
    for segment, customer in lab.presets.items():
        assert churn.score(lab, customer)["segment"] == segment


def test_score_is_consistent(lab: churn.Lab) -> None:
    result = churn.score(lab, lab.presets["lost_cause"])
    assert 0 <= result["risk_percentile"] <= 100
    assert len(result["top_reasons"]) == 5
    effect = (result["churn_without_offer"] - result["churn_with_offer"]) * 100
    assert abs(effect - result["offer_effect_points"]) < 0.11
    two_year = churn.apply_changes(lab, lab.presets["lost_cause"], {"Contract": "Two year"})
    assert churn.score(lab, two_year)["risk_score"] < result["risk_score"]


def test_percentile_and_segment_helpers() -> None:
    q = [0.0, 0.1, 0.2, 0.3, 0.4]
    assert churn.percentile_of(q, -1) == 0
    assert churn.percentile_of(q, 1) == 100
    assert churn.percentile_of(q, 0.25) == pytest.approx(62.5)
    t = {"persuadable": 0.04, "sleepingDog": -0.03, "lostCause": 0.45}
    assert churn.segment_of(0.2, 0.05, t) == "persuadable"
    assert churn.segment_of(0.2, -0.05, t) == "sleeping_dog"
    assert churn.segment_of(0.6, 0.0, t) == "lost_cause"
    assert churn.segment_of(0.2, 0.0, t) == "sure_thing"
