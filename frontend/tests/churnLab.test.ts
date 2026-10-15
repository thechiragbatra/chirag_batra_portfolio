/// <reference types="vite/client" />
// The Churn Lab scoring layer: customer consistency, encoding, percentiles, segments.

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import {
  type Customer,
  encode,
  INTERNET_ADDONS,
  type LabBundle,
  percentileOf,
  score,
  segmentOf,
  withChange,
} from '../src/features/lab/churnLab.ts'

const lab = JSON.parse(readFileSync(new URL('../public/models/churn-lab.json', import.meta.url), 'utf8')) as LabBundle
const base: Customer = lab.presets[0].values

test('every preset is a valid, encodable customer', () => {
  assert.equal(lab.presets.length, 4)
  for (const p of lab.presets) assert.equal(encode(lab.features, p.values).length, lab.features.length)
})

test('presets land in the segment they were picked for', () => {
  for (const p of lab.presets) assert.equal(score(lab, p.values).segment, p.segment)
})

test('turning internet off forces every add-on to "No internet service", and back', () => {
  const off = withChange(base, 'InternetService', 'No', false)
  for (const addon of INTERNET_ADDONS) assert.equal(off[addon], 'No internet service')
  const on = withChange(off, 'InternetService', 'DSL', false)
  for (const addon of INTERNET_ADDONS) assert.equal(on[addon], 'No')
})

test('turning the phone off forces "No phone service" on multiple lines', () => {
  const off = withChange(base, 'PhoneService', 'No', false)
  assert.equal(off.MultipleLines, 'No phone service')
  assert.equal(withChange(off, 'PhoneService', 'Yes', false).MultipleLines, 'No')
})

test('total billed follows tenure × bill only when auto is on', () => {
  const auto = withChange({ ...base, MonthlyCharges: 50 }, 'tenure', 10, true)
  assert.equal(auto.TotalCharges, 500)
  const manual = withChange({ ...base, MonthlyCharges: 50 }, 'tenure', 10, false)
  assert.equal(manual.TotalCharges, base.TotalCharges)
})

test('encode uses the sorted label codes and rejects unknown categories', () => {
  const contract = lab.features.findIndex((f) => f.name === 'Contract')
  const x = encode(lab.features, { ...base, Contract: 'Two year' })
  assert.equal(x[contract], 2) // Month-to-month, One year, Two year
  assert.throws(() => encode(lab.features, { ...base, Contract: 'Lifetime' }), /unknown Contract/)
})

test('percentileOf interpolates and clamps', () => {
  const q = [0, 0.1, 0.2, 0.3, 0.4] // 4 steps -> 25 points each
  assert.equal(percentileOf(q, -1), 0)
  assert.equal(percentileOf(q, 9), 100)
  assert.equal(percentileOf(q, 0.2), 50)
  assert.ok(Math.abs(percentileOf(q, 0.25) - 62.5) < 1e-9)
})

test('segmentOf applies the exported thresholds', () => {
  const t = lab.uplift.thresholds
  assert.equal(segmentOf(0.2, t.persuadable, t), 'persuadable')
  assert.equal(segmentOf(0.2, t.sleepingDog, t), 'sleeping_dog')
  assert.equal(segmentOf(t.lostCause, 0, t), 'lost_cause')
  assert.equal(segmentOf(t.lostCause - 0.01, 0, t), 'sure_thing')
})

test('score is consistent: SHAP sums to the risk, uplift is the gap between arms', () => {
  const s = score(lab, base)
  const margin = s.base + s.contributions.reduce((a, c) => a + c.shap, 0)
  assert.ok(Math.abs(1 / (1 + Math.exp(-margin)) - s.risk) < 1e-9)
  assert.ok(Math.abs(s.churnWithout - s.churnWith - s.uplift) < 1e-12)
  assert.ok(s.percentile >= 0 && s.percentile <= 100)
  // Sorted by magnitude, most influential first.
  for (let i = 1; i < s.contributions.length; i++) {
    assert.ok(Math.abs(s.contributions[i - 1].shap) >= Math.abs(s.contributions[i].shap))
  }
})

test('a two-year contract lowers risk versus month-to-month, all else equal', () => {
  const monthly = score(lab, { ...base, Contract: 'Month-to-month' })
  const twoYear = score(lab, { ...base, Contract: 'Two year' })
  assert.ok(twoYear.risk < monthly.risk)
})
