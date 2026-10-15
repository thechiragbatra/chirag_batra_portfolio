import json

import numpy as np
import pytest
from xgboost import XGBClassifier, XGBRegressor

import trees


@pytest.fixture(scope="module")
def fitted() -> tuple[XGBClassifier, np.ndarray]:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(600, 5))
    X[:, 3] = rng.integers(0, 3, size=600)  # an integer-coded "category"
    y = ((X[:, 0] + 0.5 * X[:, 3] + rng.normal(size=600)) > 0.4).astype(int)
    model = XGBClassifier(n_estimators=30, max_depth=4, learning_rate=0.1, eval_metric="logloss")
    model.fit(X, y)
    return model, X


def test_compact_margins_match_xgboost(
    fitted: tuple[XGBClassifier, np.ndarray],
) -> None:
    model, X = fitted
    compact = trees.export(model.get_booster())
    expected = model.predict(X, output_margin=True)
    got = np.array([trees.predict_margin(compact, row) for row in X])
    assert np.max(np.abs(got - expected)) < 1e-5


def test_probabilities_match_predict_proba(
    fitted: tuple[XGBClassifier, np.ndarray],
) -> None:
    model, X = fitted
    compact = trees.export(model.get_booster())
    got = np.array([trees.sigmoid(trees.predict_margin(compact, row)) for row in X[:50]])
    assert np.allclose(got, model.predict_proba(X[:50])[:, 1], atol=1e-6)


def test_export_shape_and_json_round_trip(
    fitted: tuple[XGBClassifier, np.ndarray],
) -> None:
    model, X = fitted
    compact = json.loads(json.dumps(trees.export(model.get_booster())))
    assert len(compact["trees"]) == 30
    for tree in compact["trees"]:
        n = len(tree["f"])
        assert all(len(tree[k]) == n for k in ("t", "l", "r", "c"))
        leaves = [i for i in range(n) if tree["f"][i] == -1]
        assert all(tree["l"][i] == -1 and tree["r"][i] == -1 for i in leaves)
    # Still exact after the JSON round trip (thresholds are shortest float32 reprs).
    expected = model.predict(X, output_margin=True)
    got = np.array([trees.predict_margin(compact, row) for row in X])
    assert np.max(np.abs(got - expected)) < 1e-5


def test_thresholds_round_trip_to_float32() -> None:
    for value in (0.1, 1 / 3, 70.35, 1e-7):
        assert np.float32(trees._short(value)) == np.float32(value)


def test_export_rejects_other_objectives() -> None:
    rng = np.random.default_rng(1)
    reg = XGBRegressor(n_estimators=2).fit(rng.normal(size=(50, 2)), rng.normal(size=50))
    with pytest.raises(ValueError, match="binary:logistic"):
        trees.export(reg.get_booster())
