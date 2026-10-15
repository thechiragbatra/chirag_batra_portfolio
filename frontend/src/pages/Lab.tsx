import { ExternalLink, FlaskConical, FolderGit2, RotateCcw, ShieldCheck } from 'lucide-react'
import { type ReactNode, useEffect, useId, useMemo, useState } from 'react'
import { DecisionMap, RiskGauge, RocCurve, ShapBars, TargetingChart } from '../features/lab/charts'
import { segmentColor, STRATEGIES } from '../features/lab/palette'
import { Reveal } from '../components/fx/Reveal'
import { PageHeader } from '../components/ui/PageHeader'
import { onLabCustomer, setGuideView, takeLabCustomer } from '../features/guide/client'
import {
  type Customer,
  FEATURE_LABELS,
  INTERNET_ADDONS,
  type LabBundle,
  loadLab,
  score,
  type Segment,
  SEGMENTS,
  withChange,
} from '../features/lab/churnLab'

const TRAINING_CODE = 'https://github.com/thechiragbatra/deploysmith/tree/main/ml/churn'
const SHOWN_REASONS = 6

const pct = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`
const pts = (v: number) => `${v >= 0 ? '' : '−'}${Math.abs(v * 100).toFixed(1)} pts`
const ordinal = (n: number) => {
  const r = Math.round(n)
  const suffix = r % 100 >= 11 && r % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[r % 10] ?? 'th'
  return `${r}${suffix}`
}

// ---- Controls ----

function Field({ label, value, children }: { label: string; value?: ReactNode; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="font-medium text-zinc-700 dark:text-zinc-300">{label}</span>
        {value !== undefined && <span className="font-mono text-xs text-zinc-500 tabular-nums">{value}</span>}
      </div>
      {children}
    </div>
  )
}

function Segmented({
  name,
  options,
  value,
  onChange,
  disabled,
  label,
}: {
  name: string
  options: { value: string; label: string }[]
  value: string
  onChange: (value: string) => void
  disabled?: boolean
  label: string
}) {
  const id = useId()
  return (
    <fieldset disabled={disabled} className="disabled:opacity-45">
      <legend className="sr-only">{label}</legend>
      <div className="flex rounded-xl bg-zinc-900/[0.04] p-1 dark:bg-white/[0.05]">
        {options.map((o) => (
          <label
            key={o.value}
            className="relative flex-1 cursor-pointer rounded-lg px-2 py-1.5 text-center text-xs font-medium text-zinc-600 transition-colors has-[:checked]:bg-white has-[:checked]:text-zinc-950 has-[:checked]:shadow-sm has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-emerald-500 dark:text-zinc-400 dark:has-[:checked]:bg-white/15 dark:has-[:checked]:text-white"
          >
            <input
              type="radio"
              name={`${id}-${name}`}
              value={o.value}
              checked={value === o.value}
              onChange={() => onChange(o.value)}
              className="sr-only"
            />
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function Slider(props: { label: string; min: number; max: number; step: number; value: number; onChange: (v: number) => void }) {
  const { label, min, max, step, value, onChange } = props
  return (
    <input
      type="range"
      aria-label={label}
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      className="w-full accent-emerald-500"
    />
  )
}

const yesNo = [
  { value: 'Yes', label: 'Yes' },
  { value: 'No', label: 'No' },
]

function CustomerForm({
  lab,
  customer,
  autoTotal,
  set,
  setAutoTotal,
}: {
  lab: LabBundle
  customer: Customer
  autoTotal: boolean
  set: (name: string, value: string | number) => void
  setAutoTotal: (on: boolean) => void
}) {
  const spec = Object.fromEntries(lab.features.map((f) => [f.name, f]))
  const range = (name: string) => {
    const f = spec[name]
    return f.kind === 'number' ? f : { min: 0, max: 1 }
  }
  const noInternet = customer.InternetService === 'No'
  const noPhone = customer.PhoneService === 'No'
  const choice = (name: string, label = FEATURE_LABELS[name], disabled = false, short?: Record<string, string>) => {
    const f = spec[name]
    if (f.kind !== 'category') return null
    // "No internet service" / "No phone service" only appear (as n/a) when they are forced.
    const options = disabled ? [String(customer[name])] : f.levels.filter((l) => !/^No (internet|phone) service$/.test(l))
    return (
      <Field label={label}>
        <Segmented
          name={name}
          label={label}
          disabled={disabled}
          value={String(customer[name])}
          onChange={(v) => set(name, v)}
          options={options.map((l) => ({ value: l, label: short?.[l] ?? l }))}
        />
      </Field>
    )
  }

  const payment = spec.PaymentMethod
  return (
    <div className="space-y-5">
      <Field label="Tenure" value={`${customer.tenure} months`}>
        <Slider label="Tenure in months" {...range('tenure')} step={1} value={Number(customer.tenure)} onChange={(v) => set('tenure', v)} />
      </Field>
      <Field label="Monthly bill" value={`$${Number(customer.MonthlyCharges).toFixed(2)}`}>
        <Slider
          label="Monthly bill in dollars"
          min={Math.floor(range('MonthlyCharges').min)}
          max={Math.ceil(range('MonthlyCharges').max)}
          step={0.25}
          value={Number(customer.MonthlyCharges)}
          onChange={(v) => set('MonthlyCharges', v)}
        />
      </Field>
      {choice('Contract', 'Contract', false, { 'Month-to-month': 'Monthly', 'One year': '1 year', 'Two year': '2 years' })}
      {choice('InternetService', 'Internet', false, { 'Fiber optic': 'Fiber' })}
      <Field label="Payment">
        <select
          value={String(customer.PaymentMethod)}
          onChange={(e) => set('PaymentMethod', e.target.value)}
          className="w-full rounded-xl border border-[var(--glass-border)] bg-white/70 px-3 py-2 text-sm dark:bg-white/5"
        >
          {payment.kind === 'category' &&
            payment.levels.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
        </select>
      </Field>
      <div className="grid grid-cols-2 gap-4">
        {choice('TechSupport', 'Tech support', noInternet, { 'No internet service': 'n/a' })}
        {choice('OnlineSecurity', 'Online security', noInternet, { 'No internet service': 'n/a' })}
      </div>
      {choice('PaperlessBilling', 'Paperless billing')}

      <details className="group rounded-xl border border-[var(--glass-border)] p-3">
        <summary className="cursor-pointer text-sm font-medium text-zinc-700 select-none dark:text-zinc-300">
          More attributes <span className="text-zinc-500">(11)</span>
        </summary>
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            {choice('gender', 'Gender')}
            <Field label="Senior citizen">
              <Segmented
                name="SeniorCitizen"
                label="Senior citizen"
                value={Number(customer.SeniorCitizen) === 1 ? 'Yes' : 'No'}
                onChange={(v) => set('SeniorCitizen', v === 'Yes' ? 1 : 0)}
                options={yesNo}
              />
            </Field>
            {choice('Partner')}
            {choice('Dependents')}
            {choice('PhoneService', 'Phone')}
            {choice('MultipleLines', 'Multiple lines', noPhone, { 'No phone service': 'n/a' })}
          </div>
          <div className="grid grid-cols-2 gap-4">
            {INTERNET_ADDONS.filter((a) => a !== 'TechSupport' && a !== 'OnlineSecurity').map((a) => (
              <div key={a}>{choice(a, FEATURE_LABELS[a], noInternet, { 'No internet service': 'n/a' })}</div>
            ))}
          </div>
          <Field label="Total billed so far" value={autoTotal ? 'tenure × bill' : undefined}>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={0}
                step={1}
                value={Number(customer.TotalCharges)}
                disabled={autoTotal}
                onChange={(e) => set('TotalCharges', Number(e.target.value) || 0)}
                aria-label="Total billed in dollars"
                className="w-full rounded-xl border border-[var(--glass-border)] bg-white/70 px-3 py-2 font-mono text-sm disabled:opacity-60 dark:bg-white/5"
              />
              <label className="flex shrink-0 items-center gap-1.5 text-xs text-zinc-600 dark:text-zinc-400">
                <input type="checkbox" checked={autoTotal} onChange={(e) => setAutoTotal(e.target.checked)} className="accent-emerald-500" />
                Auto
              </label>
            </div>
          </Field>
        </div>
      </details>
    </div>
  )
}

// ---- Result cards ----

function Card({
  title,
  aside,
  children,
  className = '',
  guide,
}: {
  title: string
  aside?: ReactNode
  children: ReactNode
  className?: string
  /** Section name the AI guide can highlight. */
  guide?: string
}) {
  return (
    <section data-guide={guide} className={`glass-strong rounded-2xl p-5 ${className}`}>
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <h2 className="font-display text-lg font-semibold">{title}</h2>
        {aside && <span className="text-right text-xs text-zinc-500">{aside}</span>}
      </div>
      {children}
    </section>
  )
}

function Stat({ value, label }: { value: ReactNode; label: ReactNode }) {
  return (
    <div className="rounded-xl bg-zinc-900/[0.03] p-3 dark:bg-white/[0.04]">
      <div className="font-display text-xl font-bold tabular-nums">{value}</div>
      <div className="mt-0.5 text-xs leading-snug text-zinc-600 dark:text-zinc-400">{label}</div>
    </div>
  )
}

function SegmentBadge({ segment }: { segment: Segment }) {
  return (
    <span
      key={segment}
      className="animate-pop inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold"
      style={{ color: segmentColor(segment), background: `color-mix(in oklab, ${segmentColor(segment)} 14%, transparent)` }}
    >
      <span className="size-2 rounded-full" style={{ background: segmentColor(segment) }} />
      {SEGMENTS[segment].label}
    </span>
  )
}

function Bar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="grid grid-cols-[6.5rem_minmax(0,1fr)_3rem] items-center gap-3 text-sm">
      <span className="text-zinc-600 dark:text-zinc-400">{label}</span>
      <span className="h-2.5 overflow-hidden rounded-full bg-zinc-900/[0.06] dark:bg-white/[0.08]">
        <span
          className="block h-full origin-left rounded-full"
          style={{
            background: color,
            transform: `scaleX(${value})`,
            transition: 'transform var(--dur-spring-settle) var(--spring-settle)',
          }}
        />
      </span>
      <span className="text-right font-mono text-xs tabular-nums">{pct(value)}</span>
    </div>
  )
}

// ---- Page ----

function useLab() {
  const [lab, setLab] = useState<LabBundle | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let live = true
    loadLab().then(
      (bundle) => live && setLab(bundle),
      (err: unknown) => live && setError(err instanceof Error ? err.message : String(err)),
    )
    return () => {
      live = false
    }
  }, [attempt])
  const retry = () => {
    setError(null)
    setAttempt((n) => n + 1)
  }
  return { lab, error, retry }
}

export default function Lab() {
  const { lab, error, retry } = useLab()
  return (
    <>
      <PageHeader
        eyebrow="Live model · runs in your browser"
        title={
          <>
            Churn <span className="text-aurora">Uplift Lab</span>
          </>
        }
      >
        Most churn models stop at “who is likely to leave”. This one also asks who a retention offer would actually
        keep. The XGBoost churn model and T-learner uplift model from my{' '}
        <a href="https://github.com/thechiragbatra/customer-churn-mlops" target="_blank" rel="noreferrer" className="font-medium text-emerald-700 underline decoration-emerald-500/40 underline-offset-4 hover:decoration-emerald-500 dark:text-emerald-400">
          churn project
        </a>{' '}
        run right here, with no server: change the customer and watch the prediction, the reasons and the decision
        update.
      </PageHeader>
      {error ? (
        <div role="alert" className="glass-strong rounded-2xl p-6 text-sm">
          <p className="font-medium">The model did not load: {error}</p>
          <button type="button" onClick={retry} className="pressable mt-3 inline-flex items-center gap-2 rounded-lg bg-zinc-950 px-3 py-1.5 text-white dark:bg-white dark:text-zinc-950">
            <RotateCcw className="size-4" aria-hidden /> Try again
          </button>
        </div>
      ) : lab ? (
        <LabView lab={lab} />
      ) : (
        <div aria-busy className="grid gap-6 lg:grid-cols-[22rem_minmax(0,1fr)]">
          <div className="glass-strong h-[34rem] animate-pulse rounded-2xl" />
          <div className="space-y-6">
            <div className="glass-strong h-48 animate-pulse rounded-2xl" />
            <div className="glass-strong h-72 animate-pulse rounded-2xl" />
          </div>
          <span className="sr-only">Loading the model…</span>
        </div>
      )}
    </>
  )
}

function LabView({ lab }: { lab: LabBundle }) {
  const [preset, setPreset] = useState<Segment | null>(lab.presets[0]?.segment ?? null)
  const [customer, setCustomer] = useState<Customer>(() => ({ ...lab.presets[0].values }))
  const [autoTotal, setAutoTotal] = useState(false)
  const [budget, setBudget] = useState(0.2)

  const result = useMemo(() => score(lab, customer), [lab, customer])

  // Tell the AI guide what is on screen, so "why is this customer at risk?" means this one.
  useEffect(() => {
    setGuideView('/lab', { customer })
  }, [customer])
  useEffect(() => () => setGuideView('/lab', null), [])

  // Customers sent by the AI guide ("what if this customer had a two-year contract?").
  useEffect(() => {
    const apply = () => {
      const values = takeLabCustomer()
      if (!values) return
      setPreset(null)
      setAutoTotal(false)
      setCustomer({ ...values })
    }
    apply()
    return onLabCustomer(apply)
  }, [])
  const set = (name: string, value: string | number) => {
    setPreset(null)
    setCustomer((c) => withChange(c, name, value, autoTotal))
  }
  const choosePreset = (segment: Segment) => {
    const p = lab.presets.find((x) => x.segment === segment)
    if (!p) return
    setPreset(segment)
    setAutoTotal(false) // presets carry their real total billed
    setCustomer({ ...p.values })
  }
  const toggleAuto = (on: boolean) => {
    setAutoTotal(on)
    if (on) setCustomer((c) => withChange(c, 'tenure', c.tenure, true))
  }

  const reasons = result.contributions.slice(0, SHOWN_REASONS)
  const rest = result.contributions.slice(SHOWN_REASONS).reduce((s, c) => s + c.shap, 0)
  const band = result.percentile >= 80 ? 'High' : result.percentile >= 50 ? 'Elevated' : 'Low'
  const bandColor = band === 'High' ? '#f43f5e' : band === 'Elevated' ? '#f59e0b' : '#10b981'
  const u = lab.uplift
  const m = lab.churn.metrics
  const bi = Math.round(budget / 0.05)

  return (
    <div className="space-y-16">
      <div>
        <div className="mb-5 flex flex-wrap items-center gap-2 text-sm">
          <span className="mr-1 text-zinc-600 dark:text-zinc-400">Start from a typical</span>
          {lab.presets.map((p) => (
            <button
              key={p.segment}
              type="button"
              aria-pressed={preset === p.segment}
              onClick={() => choosePreset(p.segment)}
              className="pressable glass inline-flex items-center gap-2 rounded-full px-3 py-1.5 font-medium transition-colors aria-pressed:bg-zinc-950 aria-pressed:text-white dark:aria-pressed:bg-white dark:aria-pressed:text-zinc-950"
            >
              <span className="size-2 rounded-full" style={{ background: segmentColor(p.segment) }} />
              {SEGMENTS[p.segment].label}
            </button>
          ))}
        </div>

        <div className="grid items-start gap-6 lg:grid-cols-[22rem_minmax(0,1fr)]">
          <section data-guide="customer" className="glass-strong rounded-2xl p-5 lg:sticky lg:top-24" aria-labelledby="customer-heading">
            <h2 id="customer-heading" className="font-display mb-4 text-lg font-semibold">
              Customer
            </h2>
            <CustomerForm lab={lab} customer={customer} autoTotal={autoTotal} set={set} setAutoTotal={toggleAuto} />
          </section>

          <div className="space-y-6">
            <p className="sr-only" aria-live="polite">
              {ordinal(result.percentile)} percentile churn risk. {SEGMENTS[result.segment].label}: {SEGMENTS[result.segment].verdict}.
            </p>
            <Card guide="risk" title="Churn risk" aside={`XGBoost · ${lab.churn.model.trees.length} trees`}>
              <div className="grid items-center gap-4 sm:grid-cols-[minmax(0,15rem)_minmax(0,1fr)]">
                <div className="text-zinc-900 dark:text-zinc-100">
                  <RiskGauge percentile={result.percentile} />
                </div>
                <div>
                  <p className="font-display text-5xl font-bold tabular-nums">
                    {ordinal(result.percentile)}
                    <span className="ml-1 text-lg font-medium text-zinc-500">percentile</span>
                  </p>
                  <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
                    Riskier than {Math.round(result.percentile)}% of held-out customers.{' '}
                    <span className="font-semibold" style={{ color: bandColor }}>
                      {band} risk
                    </span>
                    .
                  </p>
                  <p className="mt-1 font-mono text-xs text-zinc-500">model score {result.risk.toFixed(3)}</p>
                </div>
              </div>
            </Card>

            <Card guide="reasons" title="Why the model thinks so" aside={`exact TreeSHAP · ${result.millis.toFixed(1)} ms in your browser`}>
              <ShapBars items={reasons} rest={rest} />
              <p className="mt-4 text-xs leading-relaxed text-zinc-500">
                Each bar is a feature’s exact Shapley value in log-odds: how far it moves this customer from the
                average customer’s score. <span className="text-rose-600 dark:text-rose-400">Red</span> pushes toward
                leaving, <span className="text-emerald-600 dark:text-emerald-400">green</span> toward staying.
              </p>
            </Card>

            <Card guide="offer" title="Should we send a retention offer?" aside="T-learner uplift model">
              <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
                <div className="space-y-4">
                  <SegmentBadge segment={result.segment} />
                  <div>
                    <p className="font-display text-2xl font-bold">{SEGMENTS[result.segment].verdict}</p>
                    <p className="mt-1 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{SEGMENTS[result.segment].detail}</p>
                  </div>
                  <div className="space-y-2">
                    <Bar label="Without offer" value={result.churnWithout} color="#f59e0b" />
                    <Bar label="With offer" value={result.churnWith} color={segmentColor(result.segment)} />
                  </div>
                  <p className="text-sm">
                    The offer changes churn by{' '}
                    <span className="font-mono font-semibold" style={{ color: segmentColor(result.segment) }}>
                      {result.uplift >= 0 ? '−' : '+'}
                      {Math.abs(result.uplift * 100).toFixed(1)} pts
                    </span>
                  </p>
                </div>
                <div className="text-zinc-900 dark:text-zinc-100">
                  <DecisionMap churnWithout={result.churnWithout} uplift={result.uplift} thresholds={u.thresholds} segment={result.segment} />
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>

      <section data-guide="evaluation" aria-labelledby="trust-heading">
        <Reveal className="mb-8">
          <p className="mb-2 font-mono text-xs tracking-[0.2em] text-emerald-600 uppercase dark:text-emerald-400">Evaluation</p>
          <h2 id="trust-heading" className="font-display text-3xl font-bold sm:text-4xl">
            Can you trust it?
          </h2>
        </Reveal>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
          <Reveal variant="scan">
            <Card title="Churn model" aside={`holdout of ${m.testSize.toLocaleString()} customers`} className="h-full">
              <div className="flex justify-center text-zinc-900 dark:text-zinc-100">
                <RocCurve points={m.roc} auc={m.auc} />
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <Stat value={m.auc.toFixed(3)} label="ROC-AUC on the project’s own split" />
                <Stat value={`${m.aucSplits.mean.toFixed(3)} ± ${m.aucSplits.sd.toFixed(3)}`} label={`AUC over ${m.aucSplits.n} random splits`} />
                <Stat value={pct(m.recall)} label="of churners caught (recall at 0.5)" />
                <Stat value={pct(m.precision)} label="of flagged customers do churn (precision)" />
              </div>
              <p className="mt-4 text-xs leading-relaxed text-zinc-500">
                Trained with SMOTE oversampling, which inflates raw scores, so this page reports risk as a percentile
                rather than a probability.
              </p>
            </Card>
          </Reveal>
          <Reveal variant="scan" delay={110}>
            <Card title="Who to target with offers" aside={`mean of ${u.seeds.length} simulated experiments`} className="h-full">
              <div className="text-zinc-900 dark:text-zinc-100">
                <TargetingChart budgets={u.budgets} curves={u.curves} budget={budget} />
              </div>
              <Field label="Offer budget" value={`${Math.round(budget * 100)}% of customers`}>
                <Slider label="Offer budget, share of customers" min={0.05} max={1} step={0.05} value={budget} onChange={setBudget} />
              </Field>
              <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
                {STRATEGIES.map((s) => (
                  <li key={s.key} className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2 text-zinc-600 dark:text-zinc-400">
                      <span className="h-0.5 w-4 rounded" style={{ background: s.color }} />
                      {s.label}
                    </span>
                    <span className="font-mono text-xs tabular-nums">{u.curves[s.key][bi].toFixed(0)}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-zinc-500">Churners prevented per 1,000 customers at this budget.</p>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <Stat value={`+${pct(u.gainAt20.mean)}`} label={`more churn prevented than risk targeting at a 20% budget (± ${pct(u.gainAt20.sd)})`} />
                <Stat value={pct(u.offersSavedAt20.mean)} label={`fewer offers for the same impact (± ${pct(u.offersSavedAt20.sd)})`} />
              </div>
            </Card>
          </Reveal>
        </div>

        <Reveal variant="scan" className="mt-6">
          <Card guide="segments" title="Are the segments real?" aside="graded against the planted truth">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-zinc-500">
                  <tr>
                    <th className="py-2 pr-4 font-medium">Predicted segment</th>
                    <th className="py-2 pr-4 font-medium">Share of customers</th>
                    <th className="py-2 font-medium">True average effect of the offer</th>
                  </tr>
                </thead>
                <tbody>
                  {(Object.keys(SEGMENTS) as Segment[]).map((s) => (
                    <tr key={s} className="border-t border-[var(--glass-border)]">
                      <td className="py-2 pr-4">
                        <span className="inline-flex items-center gap-2 font-medium">
                          <span className="size-2 rounded-full" style={{ background: segmentColor(s) }} />
                          {SEGMENTS[s].label}
                        </span>
                      </td>
                      <td className="py-2 pr-4 font-mono tabular-nums">{pct(u.segments[s].share, 1)}</td>
                      <td className="py-2 font-mono tabular-nums">
                        {u.segments[s].trueEffect >= 0 ? 'saves ' : 'costs '}
                        {pts(Math.abs(u.segments[s].trueEffect))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-4 grid gap-2 sm:grid-cols-3">
              <Stat value={u.correlation.mean.toFixed(2)} label={`correlation of predicted and true effect (± ${u.correlation.sd.toFixed(2)})`} />
              <Stat value={pct(u.segmentAccuracy)} label="of customers placed in their true segment (chance ≈ 29%)" />
              <Stat value={`± ${(u.errorSd * 100).toFixed(0)} pts`} label="typical error on one customer’s effect" />
            </div>
            <p className="mt-4 text-xs leading-relaxed text-zinc-500">
              Rankings are much more reliable than any single customer’s number, which is why the model is used to
              choose <em>who</em> gets an offer, not to promise an individual outcome.
            </p>
          </Card>
        </Reveal>
      </section>

      <Reveal>
        <section data-guide="method" aria-labelledby="method-heading" className="glass rounded-2xl p-6">
          <h2 id="method-heading" className="font-display mb-3 flex items-center gap-2 text-xl font-semibold">
            <ShieldCheck className="size-5 text-emerald-500" aria-hidden /> Method and honest caveats
          </h2>
          <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-zinc-700 marker:text-emerald-500 dark:text-zinc-300">
            <li>
              <strong>Churn model.</strong> IBM Telco data (7,032 customers after cleaning), the project’s XGBoost
              configuration ({lab.churn.model.trees.length} trees, depth {lab.churn.params.max_depth}) with SMOTE on
              integer-coded features, evaluated on a held-out 20%.
            </li>
            <li>
              <strong>Why the uplift part is a benchmark.</strong> The dataset has no record of who received a retention
              offer, so an offer’s effect cannot be learned from it. Instead, the real customers are kept, a known effect
              is planted, and a 50/50 randomized experiment is simulated with it. The T-learner trains on 70% and is
              graded on the other 30% against the truth, which real data never allows.
            </li>
            <li>
              <strong>The planted effect.</strong> Month-to-month customers respond, most around a year in and more on
              high bills; new fiber customers without tech support are lost causes (a discount does not fix the
              service); long-tenure customers on automatic payment are sleeping dogs (the offer makes them reconsider).
            </li>
            <li>
              <strong>Before using this for real</strong>, run an actual A/B test of the offer: the uplift numbers here
              show the method works when the effect exists, not what any real offer does.
            </li>
          </ul>
          <div className="mt-5 flex flex-wrap gap-2 text-sm">
            <a href={TRAINING_CODE} target="_blank" rel="noreferrer" className="glass inline-flex items-center gap-2 rounded-lg px-3 py-1.5 font-medium hover:bg-white/80 dark:hover:bg-white/10">
              <FlaskConical className="size-4" aria-hidden /> Training and export code
            </a>
            <a href={lab.source} target="_blank" rel="noreferrer" className="glass inline-flex items-center gap-2 rounded-lg px-3 py-1.5 font-medium hover:bg-white/80 dark:hover:bg-white/10">
              <FolderGit2 className="size-4" aria-hidden /> Original project <ExternalLink className="size-3.5" aria-hidden />
            </a>
          </div>
        </section>
      </Reveal>
    </div>
  )
}
