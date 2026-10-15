"""Export an XGBoost binary classifier as compact arrays the browser can evaluate.

The site's TypeScript evaluator (frontend/src/features/lab/trees.ts) walks these arrays and
computes exact TreeSHAP; ``predict_margin`` here is the Python reference for the tests.

Format, one object per tree (node i):
  f[i]  split feature index, or -1 for a leaf
  t[i]  float32 split threshold (go left when x < t), or the leaf value
  l[i], r[i]  child indices (-1 for a leaf)
  c[i]  cover (sum of hessians), the weights TreeSHAP needs
"""

from __future__ import annotations

import json
import math
from typing import Any, TypedDict

import numpy as np
from xgboost import Booster


class CompactTree(TypedDict):
    f: list[int]
    t: list[float]
    l: list[int]  # noqa: E741 (compact JSON key)
    r: list[int]
    c: list[float]


class CompactModel(TypedDict):
    baseMargin: float
    trees: list[CompactTree]


def f32(value: float) -> float:
    """The float32 nearest ``value``, as a Python float. Its shortest repr round-trips
    through JSON and Math.fround unchanged."""
    return float(np.float32(value))


def _short(value: float) -> float:
    # repr(np.float32) is the shortest string that round-trips float32 (~9 digits), so
    # the JSON stays small while still decoding to the exact float32.
    return float(repr(np.float32(value)).removeprefix("np.float32(").removesuffix(")"))


def export(booster: Booster) -> CompactModel:
    raw: dict[str, Any] = json.loads(bytes(booster.save_raw("json")))
    learner = raw["learner"]
    objective = learner["objective"]["name"]
    if objective != "binary:logistic":
        raise ValueError(f"only binary:logistic is supported, got {objective}")
    base_score = float(str(learner["learner_model_param"]["base_score"]).strip("[]"))
    trees: list[CompactTree] = []
    for tree in learner["gradient_booster"]["model"]["trees"]:
        if any(tree["split_type"]) or tree["categories"]:
            raise ValueError("categorical splits are not supported")
        left: list[int] = tree["left_children"]
        trees.append(
            CompactTree(
                f=[-1 if left[i] == -1 else int(s) for i, s in enumerate(tree["split_indices"])],
                t=[_short(v) for v in tree["split_conditions"]],
                l=list(left),
                r=list(tree["right_children"]),
                c=[_short(v) for v in tree["sum_hessian"]],
            )
        )
    return CompactModel(baseMargin=math.log(base_score / (1 - base_score)), trees=trees)


def predict_margin(model: CompactModel, x: np.ndarray) -> float:
    """Log-odds for one row, walking the compact trees exactly as the browser does."""
    total = model["baseMargin"]
    for tree in model["trees"]:
        node = 0
        while tree["f"][node] != -1:
            # Both sides as float32, like XGBoost (the JSON decimal can sit just past it).
            go_left = f32(float(x[tree["f"][node]])) < f32(tree["t"][node])
            node = tree["l"][node] if go_left else tree["r"][node]
        total += f32(tree["t"][node])
    return total


def sigmoid(margin: float) -> float:
    return 1.0 / (1.0 + math.exp(-margin))
