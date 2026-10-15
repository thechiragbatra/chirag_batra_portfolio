// The Churn Lab bundle (public/models/churn-lab.json, written by ml/churn/train.py) and
// everything the page derives from it: encoding a customer, scoring, explanations.

import { type CompactModel, predictMargin, shapValues, sigmoid } from './trees.ts'

export type Segment = 'persuadable' | 'sure_thing' | 'lost_cause' | 'sleeping_dog'

export type FeatureSpec =
  | { name: string; kind: 'category'; levels: string[] }
  | { name: string; kind: 'number'; min: number; max: number }

export type Customer = Record<string, string | number>

interface Spread {
  mean: number
  sd: number
}

export interface LabBundle {
  version: number
  source: string
  features: FeatureSpec[]
  churn: {
    model: CompactModel
    params: Record<string, number>
    metrics: {
      auc: number
      aucSplits: Spread & { n: number }
      precision: number
      recall: number
      f1: number
      testSize: number
      churnRate: number
      roc: [number, number][]
      riskQuantiles: number[]
      importance: number[]
    }
  }
  uplift: {
    control: CompactModel
    treatment: CompactModel
    params: Record<string, number>
    thresholds: { persuadable: number; sleepingDog: number; lostCause: number }
    seeds: number[]
    budgets: number[]
    curves: Record<'uplift' | 'risk' | 'random' | 'oracle', number[]>
    correlation: Spread
    gainAt20: Spread
    offersSavedAt20: Spread
    plantedMean: number
    segments: Record<Segment, { share: number; trueEffect: number }>
    segmentAccuracy: number
    errorSd: number
  }
  presets: { segment: Segment; values: Customer }[]
}

let cached: Promise<LabBundle> | null = null

/** Fetches the bundle once per page load (about 200 KB gzipped). */
export function loadLab(): Promise<LabBundle> {
  cached ??= fetch(`${import.meta.env.BASE_URL}models/churn-lab.json`).then((res) => {
    if (!res.ok) throw new Error(`could not load the model (HTTP ${res.status})`)
    return res.json() as Promise<LabBundle>
  })
  cached.catch(() => {
    cached = null // let a retry fetch again
  })
  return cached
}

// ---- Customer shape and consistency ----

export const INTERNET_ADDONS = [
  'OnlineSecurity',
  'OnlineBackup',
  'DeviceProtection',
  'TechSupport',
  'StreamingTV',
  'StreamingMovies',
] as const

/**
 * Keep a customer internally consistent the way the dataset is: no internet means every
 * internet add-on reads "No internet service", no phone means "No phone service", and the
 * total billed follows tenure × monthly bill unless set by hand.
 */
export function withChange(customer: Customer, name: string, value: string | number, autoTotal: boolean): Customer {
  const next: Customer = { ...customer, [name]: value }
  if (name === 'InternetService') {
    for (const addon of INTERNET_ADDONS) {
      if (value === 'No') next[addon] = 'No internet service'
      else if (next[addon] === 'No internet service') next[addon] = 'No'
    }
  }
  if (name === 'PhoneService') {
    if (value === 'No') next.MultipleLines = 'No phone service'
    else if (next.MultipleLines === 'No phone service') next.MultipleLines = 'No'
  }
  if (autoTotal && (name === 'tenure' || name === 'MonthlyCharges')) {
    next.TotalCharges = Math.round(Number(next.tenure) * Number(next.MonthlyCharges) * 100) / 100
  }
  return next
}

export function encode(features: FeatureSpec[], customer: Customer): Float64Array {
  return Float64Array.from(features, (f) => {
    const value = customer[f.name]
    if (f.kind === 'number') return Number(value)
    const code = f.levels.indexOf(String(value))
    if (code < 0) throw new Error(`unknown ${f.name}: ${value}`)
    return code
  })
}

// ---- Scoring ----

export interface Contribution {
  name: string
  value: string | number
  /** Log-odds the feature adds to (positive: toward churn) the model's output. */
  shap: number
}

export interface Score {
  /** SMOTE-trained risk score, 0-1. Ranks customers well; not a calibrated probability. */
  risk: number
  /** Share of holdout customers with a lower risk score, 0-100. */
  percentile: number
  base: number
  contributions: Contribution[]
  /** Uplift model: churn probability without and with the offer. */
  churnWithout: number
  churnWith: number
  /** Points the offer takes off churn probability (negative: it backfires). */
  uplift: number
  segment: Segment
  millis: number
}

export function percentileOf(quantiles: number[], value: number): number {
  if (value <= quantiles[0]) return 0
  const last = quantiles.length - 1
  if (value >= quantiles[last]) return 100
  let i = 0
  while (quantiles[i + 1] < value) i++
  const span = quantiles[i + 1] - quantiles[i]
  const frac = span > 0 ? (value - quantiles[i]) / span : 0
  return ((i + frac) / last) * 100
}

export function segmentOf(
  churnWithout: number,
  uplift: number,
  t: LabBundle['uplift']['thresholds'],
): Segment {
  if (uplift >= t.persuadable) return 'persuadable'
  if (uplift <= t.sleepingDog) return 'sleeping_dog'
  return churnWithout >= t.lostCause ? 'lost_cause' : 'sure_thing'
}

export function score(lab: LabBundle, customer: Customer): Score {
  const start = performance.now()
  const x = encode(lab.features, customer)
  const n = lab.features.length
  const phi = shapValues(lab.churn.model, x, n)
  const risk = sigmoid(phi.reduce((a, b) => a + b, 0))
  const churnWithout = sigmoid(predictMargin(lab.uplift.control, x))
  const churnWith = sigmoid(predictMargin(lab.uplift.treatment, x))
  const uplift = churnWithout - churnWith
  const contributions = lab.features
    .map((f, i) => ({ name: f.name, value: customer[f.name], shap: phi[i] }))
    .sort((a, b) => Math.abs(b.shap) - Math.abs(a.shap))
  return {
    risk,
    percentile: percentileOf(lab.churn.metrics.riskQuantiles, risk),
    base: phi[n],
    contributions,
    churnWithout,
    churnWith,
    uplift,
    segment: segmentOf(churnWithout, uplift, lab.uplift.thresholds),
    millis: performance.now() - start,
  }
}

// ---- Display ----

export const FEATURE_LABELS: Record<string, string> = {
  gender: 'Gender',
  SeniorCitizen: 'Senior citizen',
  Partner: 'Partner',
  Dependents: 'Dependents',
  tenure: 'Tenure',
  PhoneService: 'Phone service',
  MultipleLines: 'Multiple lines',
  InternetService: 'Internet',
  OnlineSecurity: 'Online security',
  OnlineBackup: 'Online backup',
  DeviceProtection: 'Device protection',
  TechSupport: 'Tech support',
  StreamingTV: 'Streaming TV',
  StreamingMovies: 'Streaming movies',
  Contract: 'Contract',
  PaperlessBilling: 'Paperless billing',
  PaymentMethod: 'Payment',
  MonthlyCharges: 'Monthly bill',
  TotalCharges: 'Total billed',
}

const money = (n: number, digits = 2) =>
  `$${n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })}`

export function formatValue(name: string, value: string | number): string {
  if (name === 'tenure') return `${value} mo`
  if (name === 'MonthlyCharges') return money(Number(value))
  if (name === 'TotalCharges') return money(Number(value), 0)
  if (name === 'SeniorCitizen') return Number(value) === 1 ? 'Yes' : 'No'
  return String(value).replace(' (automatic)', ' (auto)')
}

export const SEGMENTS: Record<Segment, { label: string; verdict: string; detail: string }> = {
  persuadable: {
    label: 'Persuadable',
    verdict: 'Send the offer',
    detail: 'The offer meaningfully lowers this customer’s chance of leaving. This is where retention budget pays off.',
  },
  sure_thing: {
    label: 'Sure thing',
    verdict: 'Skip the offer',
    detail: 'Likely to stay either way. A discount here is money spent on someone who was not leaving.',
  },
  lost_cause: {
    label: 'Lost cause',
    verdict: 'Fix the root cause',
    detail: 'Likely to leave whatever we offer. A discount will not help; the underlying problem needs fixing.',
  },
  sleeping_dog: {
    label: 'Sleeping dog',
    verdict: 'Do not contact',
    detail: 'The offer is predicted to raise churn: contacting them prompts a rethink. Let them be.',
  },
}
