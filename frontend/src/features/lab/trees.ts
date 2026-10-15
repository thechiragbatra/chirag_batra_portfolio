// Gradient-boosted trees in the browser: prediction and exact TreeSHAP for the compact
// format ml/churn/trees.py exports. No runtime or WebAssembly needed; the parity test
// (trees.test.ts) checks both against XGBoost's own output.

export interface CompactTree {
  /** Split feature per node, -1 for a leaf. */
  f: number[]
  /** float32 threshold (go left when x < t), or the leaf value. */
  t: number[]
  l: number[]
  r: number[]
  /** Cover (sum of hessians) per node. */
  c: number[]
}

export interface CompactModel {
  baseMargin: number
  trees: CompactTree[]
}

const fround = Math.fround

export const sigmoid = (margin: number): number => 1 / (1 + Math.exp(-margin))

function leafOf(tree: CompactTree, x: ArrayLike<number>): number {
  let node = 0
  while (tree.f[node] !== -1) {
    // Both sides as float32, exactly as XGBoost compares them.
    node = fround(x[tree.f[node]]) < fround(tree.t[node]) ? tree.l[node] : tree.r[node]
  }
  return node
}

/** Log-odds for one row. */
export function predictMargin(model: CompactModel, x: ArrayLike<number>): number {
  let total = model.baseMargin
  for (const tree of model.trees) total += fround(tree.t[leafOf(tree, x)])
  return total
}

// ---- TreeSHAP (Lundberg et al. 2018, Algorithm 2; mirrors shap's tree_shap.h) ----

interface PathElement {
  feature: number
  zero: number
  one: number
  weight: number
}

function extendPath(path: PathElement[], depth: number, zero: number, one: number, feature: number) {
  path[depth] = { feature, zero, one, weight: depth === 0 ? 1 : 0 }
  for (let i = depth - 1; i >= 0; i--) {
    path[i + 1].weight += (one * path[i].weight * (i + 1)) / (depth + 1)
    path[i].weight = (zero * path[i].weight * (depth - i)) / (depth + 1)
  }
}

function unwindPath(path: PathElement[], depth: number, index: number) {
  const { one, zero } = path[index]
  let next = path[depth].weight
  for (let i = depth - 1; i >= 0; i--) {
    if (one !== 0) {
      const tmp = path[i].weight
      path[i].weight = (next * (depth + 1)) / ((i + 1) * one)
      next = tmp - (path[i].weight * zero * (depth - i)) / (depth + 1)
    } else {
      path[i].weight = (path[i].weight * (depth + 1)) / (zero * (depth - i))
    }
  }
  for (let i = index; i < depth; i++) {
    path[i].feature = path[i + 1].feature
    path[i].zero = path[i + 1].zero
    path[i].one = path[i + 1].one
  }
}

function unwoundPathSum(path: PathElement[], depth: number, index: number): number {
  const { one, zero } = path[index]
  let next = path[depth].weight
  let total = 0
  for (let i = depth - 1; i >= 0; i--) {
    if (one !== 0) {
      const tmp = (next * (depth + 1)) / ((i + 1) * one)
      total += tmp
      next = path[i].weight - tmp * zero * ((depth - i) / (depth + 1))
    } else {
      total += path[i].weight / zero / ((depth - i) / (depth + 1))
    }
  }
  return total
}

function recurse(
  tree: CompactTree,
  x: ArrayLike<number>,
  phi: Float64Array,
  node: number,
  parent: PathElement[],
  depth: number,
  zero: number,
  one: number,
  feature: number,
) {
  // Each call works on its own copy of the path so siblings do not see each other.
  const path = parent.slice(0, depth).map((e) => ({ ...e }))
  extendPath(path, depth, zero, one, feature)

  if (tree.f[node] === -1) {
    const value = fround(tree.t[node])
    for (let i = 1; i <= depth; i++) {
      const w = unwoundPathSum(path, depth, i)
      phi[path[i].feature] += w * (path[i].one - path[i].zero) * value
    }
    return
  }

  const split = tree.f[node]
  const goLeft = fround(x[split]) < fround(tree.t[node])
  const hot = goLeft ? tree.l[node] : tree.r[node]
  const cold = goLeft ? tree.r[node] : tree.l[node]
  const cover = tree.c[node]
  let incomingZero = 1
  let incomingOne = 1

  // A feature already on the path is undone first, so it is only counted once.
  let index = 0
  while (index <= depth && path[index].feature !== split) index++
  if (index <= depth) {
    incomingZero = path[index].zero
    incomingOne = path[index].one
    unwindPath(path, depth, index)
    depth -= 1
  }

  recurse(tree, x, phi, hot, path, depth + 1, (tree.c[hot] / cover) * incomingZero, incomingOne, split)
  recurse(tree, x, phi, cold, path, depth + 1, (tree.c[cold] / cover) * incomingZero, 0, split)
}

/** Expected output of one tree over its training data (the SHAP base value). */
function expectedValue(tree: CompactTree, node = 0): number {
  if (tree.f[node] === -1) return fround(tree.t[node])
  const { l, r, c } = tree
  return (c[l[node]] * expectedValue(tree, l[node]) + c[r[node]] * expectedValue(tree, r[node])) / c[node]
}

/** Base value of a model: what SHAP contributions are measured from (log-odds). */
export function expectedMargin(model: CompactModel): number {
  return model.trees.reduce((sum, tree) => sum + expectedValue(tree), model.baseMargin)
}

/**
 * Exact SHAP values in log-odds: one per feature, plus the base value last (the same
 * layout as XGBoost's pred_contribs). They sum to predictMargin(model, x).
 */
export function shapValues(model: CompactModel, x: ArrayLike<number>, numFeatures: number): Float64Array {
  const phi = new Float64Array(numFeatures + 1)
  for (const tree of model.trees) {
    recurse(tree, x, phi, 0, [], 0, 1, 1, -1)
  }
  phi[numFeatures] = expectedMargin(model)
  return phi
}
