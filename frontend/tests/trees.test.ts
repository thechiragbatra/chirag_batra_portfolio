// Parity: the browser evaluator must reproduce XGBoost's own margins and TreeSHAP values
// for the exported Churn Lab models. Regenerate both files with ml/churn/train.py.
//   npm test

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { type CompactModel, expectedMargin, predictMargin, shapValues, sigmoid } from '../src/features/lab/trees.ts'

interface LabFile {
  features: unknown[]
  churn: { model: CompactModel }
  uplift: { control: CompactModel; treatment: CompactModel }
}

interface Fixture {
  rows: number[][]
  churnMargin: number[]
  churnContribs: number[][]
  controlMargin: number[]
  treatmentMargin: number[]
}

const read = <T>(path: string): T => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8')) as T
const lab = read<LabFile>('../public/models/churn-lab.json')
const fixture = read<Fixture>('./fixtures/churn-parity.json')
const numFeatures = lab.features.length
const TOLERANCE = 1e-4

function close(actual: number, expected: number, label: string) {
  assert.ok(Math.abs(actual - expected) <= TOLERANCE, `${label}: got ${actual}, expected ${expected}`)
}

test('churn margins match XGBoost', () => {
  fixture.rows.forEach((row, i) => close(predictMargin(lab.churn.model, row), fixture.churnMargin[i], `row ${i}`))
})

test('uplift arm margins match XGBoost', () => {
  fixture.rows.forEach((row, i) => {
    close(predictMargin(lab.uplift.control, row), fixture.controlMargin[i], `control row ${i}`)
    close(predictMargin(lab.uplift.treatment, row), fixture.treatmentMargin[i], `treatment row ${i}`)
  })
})

test('TreeSHAP values match XGBoost pred_contribs', () => {
  fixture.rows.forEach((row, i) => {
    const phi = shapValues(lab.churn.model, row, numFeatures)
    fixture.churnContribs[i].forEach((expected, j) => close(phi[j], expected, `row ${i} feature ${j}`))
  })
})

test('SHAP values sum to the prediction (local accuracy)', () => {
  for (const row of fixture.rows) {
    const phi = shapValues(lab.churn.model, row, numFeatures)
    close(
      phi.reduce((a, b) => a + b, 0),
      predictMargin(lab.churn.model, row),
      'sum',
    )
  }
})

test('tiny hand-built tree: prediction, base value and SHAP', () => {
  // x0 < 0.5 ? (x1 < 0.5 ? 1 : 3) : 5, every node with equal cover per leaf.
  const model: CompactModel = {
    baseMargin: 0,
    trees: [{ f: [0, 1, -1, -1, -1], t: [0.5, 0.5, 5, 1, 3], l: [1, 3, -1, -1, -1], r: [2, 4, -1, -1, -1], c: [4, 2, 2, 1, 1] }],
  }
  assert.equal(predictMargin(model, [0, 0]), 1)
  assert.equal(predictMargin(model, [1, 0]), 5)
  // Expected value = (2*5 + 1*1 + 1*3) / 4 = 3.5
  close(expectedMargin(model), 3.5, 'base')
  // For x = [0, 0]: output 1. Exact Shapley values of the two features:
  // phi0 = 0.5*[(v({0})-v({})) + (v({0,1})-v({1}))] = 0.5*[(2-3.5) + (1-3)] = -1.75
  // phi1 = 0.5*[(v({1})-v({})) + (v({0,1})-v({0}))] = 0.5*[(3-3.5) + (1-2)] = -0.75
  const phi = shapValues(model, [0, 0], 2)
  close(phi[0], -1.75, 'phi0')
  close(phi[1], -0.75, 'phi1')
  close(phi[2], 3.5, 'bias')
  assert.ok(Math.abs(sigmoid(0) - 0.5) < 1e-12)
})
