// Hand-drawn SVG charts for the Churn Lab. Fixed-aspect viewBoxes (never
// preserveAspectRatio="none") so circles and labels never stretch.

import { useId } from 'react'
import { type Contribution, FEATURE_LABELS, formatValue, type Segment, SEGMENTS } from './churnLab'
import { SEGMENT_TINT, STRATEGIES, type Strategy } from './palette'

const SPRING = 'var(--dur-spring-settle) var(--spring-settle)'

/** Semicircle gauge for the risk percentile (0-100). */
export function RiskGauge({ percentile }: { percentile: number }) {
  const id = useId()
  const angle = -90 + (percentile / 100) * 180
  return (
    <svg viewBox="0 0 200 112" className="w-full" aria-hidden>
      <defs>
        <linearGradient id={`${id}-g`} x1="0" x2="1">
          <stop offset="0" stopColor="#10b981" />
          <stop offset="0.55" stopColor="#f59e0b" />
          <stop offset="1" stopColor="#f43f5e" />
        </linearGradient>
      </defs>
      <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="currentColor" strokeOpacity="0.1" strokeWidth="14" strokeLinecap="round" />
      <path
        d="M 20 100 A 80 80 0 0 1 180 100"
        fill="none"
        stroke={`url(#${id}-g)`}
        strokeWidth="14"
        strokeLinecap="round"
        pathLength={100}
        strokeDasharray={`${Math.max(percentile, 0.5)} 200`}
        style={{ transition: `stroke-dasharray ${SPRING}` }}
      />
      <g style={{ transform: `rotate(${angle}deg)`, transformOrigin: '100px 100px', transition: `transform ${SPRING}` }}>
        <line x1="100" y1="100" x2="100" y2="34" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      </g>
      <circle cx="100" cy="100" r="7" fill="currentColor" />
    </svg>
  )
}

/** Diverging SHAP bars: red pushes toward churn, green toward staying. */
export function ShapBars({ items, rest }: { items: Contribution[]; rest: number }) {
  const max = Math.max(0.4, ...items.map((c) => Math.abs(c.shap)), Math.abs(rest))
  const rows = [...items, ...(Math.abs(rest) > 1e-6 ? [{ name: '__rest', value: '', shap: rest }] : [])]
  return (
    <ul className="space-y-1.5">
      {rows.map((c) => {
        const up = c.shap > 0
        const width = (Math.abs(c.shap) / max) * 50
        return (
          <li key={c.name} className="grid grid-cols-[minmax(0,10rem)_minmax(0,1fr)_3.25rem] items-center gap-3 text-sm sm:grid-cols-[minmax(0,13rem)_minmax(0,1fr)_3.5rem]">
            <span className="truncate text-zinc-700 dark:text-zinc-300">
              {c.name === '__rest' ? (
                <span className="text-zinc-500">All other features</span>
              ) : (
                <>
                  {FEATURE_LABELS[c.name] ?? c.name}{' '}
                  <span className="font-mono text-xs text-zinc-500">{formatValue(c.name, c.value)}</span>
                </>
              )}
            </span>
            <span className="relative h-5 rounded bg-zinc-900/[0.03] dark:bg-white/[0.04]">
              <span aria-hidden className="absolute inset-y-0 left-1/2 w-px bg-zinc-900/15 dark:bg-white/20" />
              <span
                aria-hidden
                className={`absolute inset-y-0.5 rounded ${up ? 'bg-gradient-to-r from-rose-400 to-rose-500' : 'bg-gradient-to-l from-emerald-400 to-emerald-500'}`}
                style={{
                  left: up ? '50%' : `${50 - width}%`,
                  width: `${width}%`,
                  transition: `left ${SPRING}, width ${SPRING}`,
                }}
              />
            </span>
            <span className={`text-right font-mono text-xs tabular-nums ${up ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
              {up ? '+' : '−'}
              {Math.abs(c.shap).toFixed(2)}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

/**
 * The decision map: churn risk without the offer (x) against the offer's effect (y).
 * The thresholds split it into the four segments; the customer's dot glides between them.
 */
export function DecisionMap({
  churnWithout,
  uplift,
  thresholds,
  segment,
}: {
  churnWithout: number
  uplift: number
  thresholds: { persuadable: number; sleepingDog: number; lostCause: number }
  segment: Segment
}) {
  const W = 300
  const H = 190
  const pad = { l: 34, r: 8, t: 8, b: 26 }
  const yMin = -0.15
  const yMax = 0.3
  const x = (v: number) => pad.l + v * (W - pad.l - pad.r)
  const y = (v: number) => pad.t + ((yMax - v) / (yMax - yMin)) * (H - pad.t - pad.b)
  const clampY = (v: number) => Math.min(yMax, Math.max(yMin, v))
  const top = y(thresholds.persuadable)
  const bottom = y(thresholds.sleepingDog)
  const split = x(thresholds.lostCause)
  const region = (s: Segment, rx: number, ry: number, rw: number, rh: number, lx: number, ly: number) => (
    <g>
      <rect x={rx} y={ry} width={rw} height={rh} fill={SEGMENT_TINT[s]} opacity={segment === s ? 0.16 : 0.06} style={{ transition: 'opacity 300ms' }} />
      <text x={lx} y={ly} fontSize="9.5" fontWeight={600} fill={SEGMENT_TINT[s]} opacity={segment === s ? 1 : 0.7}>
        {SEGMENTS[s].label}
      </text>
    </g>
  )
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`Decision map: this customer is a ${SEGMENTS[segment].label}`}>
      {region('persuadable', x(0), y(yMax), x(1) - x(0), top - y(yMax), x(0) + 6, y(yMax) + 13)}
      {region('sure_thing', x(0), top, split - x(0), bottom - top, x(0) + 6, top + 13)}
      {region('lost_cause', split, top, x(1) - split, bottom - top, split + 6, top + 13)}
      {region('sleeping_dog', x(0), bottom, x(1) - x(0), y(yMin) - bottom, x(0) + 6, y(yMin) - 6)}
      <line x1={x(0)} x2={x(1)} y1={y(0)} y2={y(0)} stroke="currentColor" strokeOpacity="0.25" strokeDasharray="3 3" />
      {[-0.1, 0, 0.1, 0.2, 0.3].map((v) => (
        <text key={v} x={pad.l - 5} y={y(v) + 3} fontSize="8.5" textAnchor="end" fill="currentColor" opacity="0.55">
          {v > 0 ? '+' : ''}
          {Math.round(v * 100)}
        </text>
      ))}
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <text key={v} x={x(v)} y={H - 12} fontSize="8.5" textAnchor={v === 1 ? 'end' : 'middle'} fill="currentColor" opacity="0.55">
          {Math.round(v * 100)}%
        </text>
      ))}
      <text x={(x(0) + x(1)) / 2} y={H - 1} fontSize="8.5" textAnchor="middle" fill="currentColor" opacity="0.7">
        churn risk without an offer
      </text>
      <text x={8} y={(pad.t + H - pad.b) / 2} fontSize="8.5" textAnchor="middle" fill="currentColor" opacity="0.7" transform={`rotate(-90 8 ${(pad.t + H - pad.b) / 2})`}>
        pts the offer saves
      </text>
      <g
        style={{
          transform: `translate(${x(churnWithout)}px, ${y(clampY(uplift))}px)`,
          transition: `transform ${SPRING}`,
        }}
      >
        <circle r="11" fill={SEGMENT_TINT[segment]} opacity="0.2" className="animate-ping-slow" style={{ transformBox: 'fill-box', transformOrigin: 'center' }} />
        <circle r="5.5" fill={SEGMENT_TINT[segment]} stroke="white" strokeWidth="2" />
      </g>
    </svg>
  )
}

/** ROC curve of the churn model on its holdout set. */
export function RocCurve({ points, auc }: { points: [number, number][]; auc: number }) {
  const id = useId()
  const S = 200
  const p = 6
  const sx = (v: number) => p + v * (S - 2 * p)
  const sy = (v: number) => S - p - v * (S - 2 * p)
  const line = points.map(([fx, ty], i) => `${i ? 'L' : 'M'} ${sx(fx).toFixed(1)} ${sy(ty).toFixed(1)}`).join(' ')
  const area = `${line} L ${sx(1)} ${sy(0)} L ${sx(0)} ${sy(0)} Z`
  return (
    <svg viewBox={`0 0 ${S} ${S}`} className="w-full max-w-[16rem]" role="img" aria-label={`ROC curve, area under curve ${auc.toFixed(3)}`}>
      <defs>
        <linearGradient id={`${id}-a`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#10b981" stopOpacity="0.35" />
          <stop offset="1" stopColor="#10b981" stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect x={p} y={p} width={S - 2 * p} height={S - 2 * p} fill="none" stroke="currentColor" strokeOpacity="0.12" />
      <line x1={sx(0)} y1={sy(0)} x2={sx(1)} y2={sy(1)} stroke="currentColor" strokeOpacity="0.3" strokeDasharray="4 4" />
      <path d={area} fill={`url(#${id}-a)`} />
      <path d={line} fill="none" stroke="#10b981" strokeWidth="2.5" pathLength={1} strokeDasharray="1" strokeDashoffset="1" className="lab-draw" />
      <text x={sx(0.97)} y={sy(0.06)} fontSize="11" textAnchor="end" fill="currentColor" opacity="0.7">
        false-positive rate →
      </text>
      <text x={sx(0.03)} y={sy(0.92)} fontSize="11" fill="currentColor" opacity="0.7">
        ↑ recall
      </text>
    </svg>
  )
}

/** Churners prevented per 1,000 customers as the offer budget grows, per strategy. */
export function TargetingChart({
  budgets,
  curves,
  budget,
}: {
  budgets: number[]
  curves: Record<Strategy, number[]>
  budget: number
}) {
  const W = 320
  const H = 200
  const pad = { l: 30, r: 10, t: 10, b: 28 }
  const yMax = Math.ceil(Math.max(...curves.oracle) / 20) * 20
  const x = (v: number) => pad.l + v * (W - pad.l - pad.r)
  const y = (v: number) => pad.t + (1 - v / yMax) * (H - pad.t - pad.b)
  const path = (values: number[]) =>
    values.map((v, i) => `${i ? 'L' : 'M'} ${x(budgets[i]).toFixed(1)} ${y(v).toFixed(1)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Churners prevented per 1,000 customers by offer budget for each targeting strategy">
      {Array.from({ length: yMax / 20 + 1 }, (_, i) => i * 20).map((v) => (
        <g key={v}>
          <line x1={x(0)} x2={x(1)} y1={y(v)} y2={y(v)} stroke="currentColor" strokeOpacity="0.08" />
          <text x={pad.l - 5} y={y(v) + 3} fontSize="9" textAnchor="end" fill="currentColor" opacity="0.55">
            {v}
          </text>
        </g>
      ))}
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <text key={v} x={x(v)} y={H - 14} fontSize="9" textAnchor={v === 1 ? 'end' : 'middle'} fill="currentColor" opacity="0.55">
          {v * 100}%
        </text>
      ))}
      <text x={(x(0) + x(1)) / 2} y={H - 2} fontSize="9" textAnchor="middle" fill="currentColor" opacity="0.7">
        share of customers who get the offer
      </text>
      {STRATEGIES.map((s) => (
        <path
          key={s.key}
          d={path(curves[s.key])}
          fill="none"
          stroke={s.color}
          strokeWidth={s.key === 'uplift' || s.key === 'risk' ? 2.5 : 1.5}
          strokeDasharray={s.dash}
          strokeLinejoin="round"
        />
      ))}
      <g style={{ transform: `translateX(${x(budget)}px)`, transition: `transform ${SPRING}` }}>
        <line x1={0} x2={0} y1={pad.t} y2={H - pad.b} stroke="currentColor" strokeOpacity="0.45" strokeDasharray="2 3" />
      </g>
    </svg>
  )
}
