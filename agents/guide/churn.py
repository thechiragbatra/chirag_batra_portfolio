"""The Churn Lab models, server side, so the guide can answer what-if questions.

A port of frontend/src/features/lab/trees.ts and churnLab.ts (tree walk + exact TreeSHAP over
the compact format ml/churn/trees.py exports). Pure Python: the backend needs no numpy.
Checked against XGBoost's own margins and SHAP values by backend/tests/test_guide_churn.py.
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from agents.guide.corpus import portfolio_dir

Segment = Literal["persuadable", "sure_thing", "lost_cause", "sleeping_dog"]
Customer = dict[str, str | float]

INTERNET_ADDONS = (
    "OnlineSecurity",
    "OnlineBackup",
    "DeviceProtection",
    "TechSupport",
    "StreamingTV",
    "StreamingMovies",
)


def fround(value: float) -> float:
    """Round to float32, like Math.fround and XGBoost's comparisons."""
    return float(struct.unpack("f", struct.pack("f", value))[0])


def sigmoid(margin: float) -> float:
    return 1.0 / (1.0 + math.exp(-margin))


@dataclass(frozen=True)
class Tree:
    f: list[int]
    t: list[float]
    l: list[int]  # noqa: E741 (compact JSON key)
    r: list[int]
    c: list[float]


@dataclass(frozen=True)
class Model:
    base_margin: float
    trees: list[Tree]

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Model:
        trees = [
            Tree(f=t["f"], t=[fround(v) for v in t["t"]], l=t["l"], r=t["r"], c=t["c"])
            for t in raw["trees"]
        ]
        return cls(base_margin=raw["baseMargin"], trees=trees)


def predict_margin(model: Model, x: list[float]) -> float:
    total = model.base_margin
    for tree in model.trees:
        node = 0
        while tree.f[node] != -1:
            node = tree.l[node] if fround(x[tree.f[node]]) < tree.t[node] else tree.r[node]
        total += tree.t[node]
    return total


# ---- TreeSHAP (Lundberg et al. 2018, Algorithm 2), mirroring trees.ts ----


@dataclass
class _Elem:
    feature: int
    zero: float
    one: float
    weight: float


def _extend(path: list[_Elem], depth: int, zero: float, one: float, feature: int) -> None:
    path.append(_Elem(feature, zero, one, 1.0 if depth == 0 else 0.0))
    for i in range(depth - 1, -1, -1):
        path[i + 1].weight += one * path[i].weight * (i + 1) / (depth + 1)
        path[i].weight = zero * path[i].weight * (depth - i) / (depth + 1)


def _unwind(path: list[_Elem], depth: int, index: int) -> None:
    one, zero = path[index].one, path[index].zero
    nxt = path[depth].weight
    for i in range(depth - 1, -1, -1):
        if one != 0:
            tmp = path[i].weight
            path[i].weight = nxt * (depth + 1) / ((i + 1) * one)
            nxt = tmp - path[i].weight * zero * (depth - i) / (depth + 1)
        else:
            path[i].weight = path[i].weight * (depth + 1) / (zero * (depth - i))
    for i in range(index, depth):
        path[i].feature = path[i + 1].feature
        path[i].zero = path[i + 1].zero
        path[i].one = path[i + 1].one
    path.pop()


def _unwound_sum(path: list[_Elem], depth: int, index: int) -> float:
    one, zero = path[index].one, path[index].zero
    nxt = path[depth].weight
    total = 0.0
    for i in range(depth - 1, -1, -1):
        if one != 0:
            tmp = nxt * (depth + 1) / ((i + 1) * one)
            total += tmp
            nxt = path[i].weight - tmp * zero * ((depth - i) / (depth + 1))
        else:
            total += path[i].weight / zero / ((depth - i) / (depth + 1))
    return total


def _recurse(
    tree: Tree,
    x: list[float],
    phi: list[float],
    node: int,
    parent: list[_Elem],
    depth: int,
    zero: float,
    one: float,
    feature: int,
) -> None:
    path = [_Elem(e.feature, e.zero, e.one, e.weight) for e in parent[:depth]]
    _extend(path, depth, zero, one, feature)
    if tree.f[node] == -1:
        value = tree.t[node]
        for i in range(1, depth + 1):
            w = _unwound_sum(path, depth, i)
            phi[path[i].feature] += w * (path[i].one - path[i].zero) * value
        return
    split = tree.f[node]
    go_left = fround(x[split]) < tree.t[node]
    hot, cold = (tree.l[node], tree.r[node]) if go_left else (tree.r[node], tree.l[node])
    cover = tree.c[node]
    incoming_zero = incoming_one = 1.0
    index = next((i for i in range(depth + 1) if path[i].feature == split), None)
    if index is not None:
        incoming_zero, incoming_one = path[index].zero, path[index].one
        _unwind(path, depth, index)
        depth -= 1
    _recurse(
        tree, x, phi, hot, path, depth + 1, tree.c[hot] / cover * incoming_zero, incoming_one, split
    )
    _recurse(tree, x, phi, cold, path, depth + 1, tree.c[cold] / cover * incoming_zero, 0.0, split)


def _expected(tree: Tree, node: int = 0) -> float:
    if tree.f[node] == -1:
        return tree.t[node]
    left, right = tree.l[node], tree.r[node]
    return (tree.c[left] * _expected(tree, left) + tree.c[right] * _expected(tree, right)) / tree.c[
        node
    ]


def shap_values(model: Model, x: list[float]) -> list[float]:
    """Exact SHAP values in log-odds, one per feature plus the base value last."""
    phi = [0.0] * (len(x) + 1)
    for tree in model.trees:
        _recurse(tree, x, phi, 0, [], 0, 1.0, 1.0, -1)
    phi[-1] = model.base_margin + sum(_expected(t) for t in model.trees)
    return phi


# ---- The lab ----


class CustomerError(ValueError):
    """A what-if request named an unknown feature or value."""


@dataclass(frozen=True)
class Lab:
    features: list[dict[str, Any]]
    churn: Model
    control: Model
    treatment: Model
    quantiles: list[float]
    thresholds: dict[str, float]
    presets: dict[str, Customer]

    def spec(self, name: str) -> dict[str, Any]:
        for f in self.features:
            if f["name"] == name:
                return f
        raise CustomerError(f"unknown attribute {name!r}")

    def encode(self, customer: Customer) -> list[float]:
        out: list[float] = []
        for f in self.features:
            value = customer[f["name"]]
            if f["kind"] == "number":
                out.append(float(value))
            else:
                out.append(float(f["levels"].index(str(value))))
        return out


@lru_cache(maxsize=2)
def _load(path: str) -> Lab:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return Lab(
        features=raw["features"],
        churn=Model.from_json(raw["churn"]["model"]),
        control=Model.from_json(raw["uplift"]["control"]),
        treatment=Model.from_json(raw["uplift"]["treatment"]),
        quantiles=raw["churn"]["metrics"]["riskQuantiles"],
        thresholds=raw["uplift"]["thresholds"],
        presets={p["segment"]: p["values"] for p in raw["presets"]},
    )


def load_lab(path: Path | None = None) -> Lab:
    return _load(str(path or portfolio_dir() / "public" / "models" / "churn-lab.json"))


def apply_changes(lab: Lab, base: Customer, changes: dict[str, Any]) -> Customer:
    """Apply what-if changes, validated and kept consistent the way the dataset is."""
    customer = dict(base)
    for name, value in changes.items():
        spec = lab.spec(name)
        if spec["kind"] == "number":
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise CustomerError(f"{name} must be a number") from exc
            if not spec["min"] <= number <= spec["max"]:
                raise CustomerError(f"{name} must be between {spec['min']} and {spec['max']}")
            customer[name] = number
        else:
            if value not in spec["levels"]:
                raise CustomerError(f"{name} must be one of {spec['levels']}")
            customer[name] = value
    if customer["InternetService"] == "No":
        for addon in INTERNET_ADDONS:
            customer[addon] = "No internet service"
    else:
        for addon in INTERNET_ADDONS:
            if customer[addon] == "No internet service":
                customer[addon] = "No"
    if customer["PhoneService"] == "No":
        customer["MultipleLines"] = "No phone service"
    elif customer["MultipleLines"] == "No phone service":
        customer["MultipleLines"] = "No"
    if ("tenure" in changes or "MonthlyCharges" in changes) and "TotalCharges" not in changes:
        customer["TotalCharges"] = round(
            float(customer["tenure"]) * float(customer["MonthlyCharges"]), 2
        )
    return customer


def percentile_of(quantiles: list[float], value: float) -> float:
    if value <= quantiles[0]:
        return 0.0
    last = len(quantiles) - 1
    if value >= quantiles[last]:
        return 100.0
    i = 0
    while quantiles[i + 1] < value:
        i += 1
    span = quantiles[i + 1] - quantiles[i]
    frac = (value - quantiles[i]) / span if span > 0 else 0.0
    return (i + frac) / last * 100


def segment_of(churn_without: float, uplift: float, t: dict[str, float]) -> Segment:
    if uplift >= t["persuadable"]:
        return "persuadable"
    if uplift <= t["sleepingDog"]:
        return "sleeping_dog"
    return "lost_cause" if churn_without >= t["lostCause"] else "sure_thing"


def score(lab: Lab, customer: Customer, reasons: int = 5) -> dict[str, Any]:
    x = lab.encode(customer)
    phi = shap_values(lab.churn, x)
    risk = sigmoid(sum(phi))
    without = sigmoid(predict_margin(lab.control, x))
    with_offer = sigmoid(predict_margin(lab.treatment, x))
    ranked = sorted(
        ((f["name"], customer[f["name"]], phi[i]) for i, f in enumerate(lab.features)),
        key=lambda item: -abs(item[2]),
    )
    return {
        # Half-up like the page's Math.round, so Smith and the Lab quote the same percentile.
        "risk_percentile": math.floor(percentile_of(lab.quantiles, risk) + 0.5),
        "risk_score": round(risk, 3),
        "top_reasons": [
            {"feature": name, "value": value, "shap_log_odds": round(v, 3)}
            for name, value, v in ranked[:reasons]
        ],
        "churn_without_offer": round(without, 3),
        "churn_with_offer": round(with_offer, 3),
        "offer_effect_points": round((without - with_offer) * 100, 1),
        "segment": segment_of(without, without - with_offer, lab.thresholds),
    }
