import { ChevronLeft } from 'lucide-react'
import { Fragment } from 'react'
import type { Phase } from './useDeploymentStream'
import { AGENT_NAMES, MAX_REPAIR_ATTEMPTS, type AgentName, type AgentStatus } from '../../types/events'
import { AGENT_META } from './agentMeta'

interface Props {
  agents: Record<AgentName, AgentStatus>
  repairAttempts: number
  phase: Phase
}

function Node({ name, status }: { name: AgentName; status: AgentStatus }) {
  const { icon: Icon } = AGENT_META[name]
  return (
    <div className="flex flex-col items-center gap-2">
      <div
        key={status === 'done' || status === 'failed' ? status : 'live'}
        className={`relative grid size-14 place-items-center sm:size-20 ${
          status === 'failed' ? 'animate-shake' : status === 'done' ? 'node-lock' : ''
        }`}
      >
        {status === 'done' && (
          <span aria-hidden className="ripple-once absolute inset-0 rounded-2xl ring-2 ring-emerald-400/70" />
        )}
        {status === 'running' && (
          <>
            <span className="animate-ping-slow absolute inset-0 rounded-2xl bg-cyan-400/30" />
            <span
              className="absolute -inset-[2px] rounded-[18px] [animation:spin-angle_1.2s_linear_infinite]"
              style={{ background: 'conic-gradient(from var(--angle), transparent 20%, var(--glow-b), var(--glow-a), transparent 80%)' }}
            />
          </>
        )}
        <div
          className={`relative grid size-full place-items-center rounded-2xl border backdrop-blur-xl transition-all duration-500 ${
            {
              idle: 'border-[var(--glass-border)] bg-[var(--glass)] opacity-50 grayscale',
              running: 'border-transparent bg-white shadow-[0_0_40px_-6px_var(--glow-b)] dark:bg-zinc-900',
              done: 'border-emerald-400/50 bg-emerald-50 shadow-[0_0_30px_-10px_var(--glow-a)] dark:bg-emerald-950/60',
              failed: 'border-red-400/60 bg-red-50 shadow-[0_0_30px_-8px_#f87171] dark:bg-red-950/60',
            }[status]
          }`}
        >
          <Icon
            className={`size-6 transition-transform duration-500 sm:size-8 ${status === 'running' ? 'scale-110 text-cyan-500' : status === 'failed' ? 'text-red-500' : AGENT_META[name].text}`}
            aria-hidden
          />
          {status === 'done' && (
            <span className="animate-pop absolute -top-1.5 -right-1.5 grid size-5 place-items-center rounded-full bg-emerald-500 text-white shadow-lg ring-2 ring-white dark:ring-zinc-950">
              {/* The checkmark draws itself after the badge pops in (LOCK). */}
              <svg viewBox="0 0 24 24" className="size-3" fill="none" stroke="currentColor" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path className="draw-stroke" d="M5 12.5l4.5 4.5L19 7.5" />
              </svg>
            </span>
          )}
          {status === 'failed' && (
            <span className="animate-pop absolute -top-1.5 -right-1.5 grid size-5 place-items-center rounded-full bg-red-500 text-white shadow-lg ring-2 ring-white dark:ring-zinc-950">
              <svg viewBox="0 0 24 24" className="size-3" fill="none" stroke="currentColor" strokeWidth={4} strokeLinecap="round" aria-hidden>
                <path className="draw-stroke" d="M6 6l12 12" />
                <path className="draw-stroke [animation-delay:0.34s]" d="M18 6L6 18" />
              </svg>
            </span>
          )}
        </div>
      </div>
      <div className="text-center">
        <p className="text-[11px] font-semibold capitalize sm:text-sm">{name}</p>
        <p
          className={`font-mono text-[10px] sm:text-[11px] ${
            { idle: 'text-zinc-400', running: 'text-cyan-600 dark:text-cyan-400', done: 'text-emerald-600 dark:text-emerald-400', failed: 'text-red-500' }[status]
          }`}
        >
          {status}
        </p>
      </div>
    </div>
  )
}

function Connector({ from, to }: { from: AgentStatus; to: AgentStatus }) {
  const flowing = from === 'done' && to === 'running'
  const filled = from === 'done' && (to === 'done' || to === 'failed')
  return (
    <div className="packet-track relative mb-10 h-[3px] min-w-3 rounded-full bg-zinc-900/10 sm:mb-12 dark:bg-white/10">
      <div
        className={`absolute inset-0 origin-left rounded-full bg-gradient-to-r from-emerald-400 to-cyan-400 transition-transform duration-700 ease-out ${
          filled ? 'scale-x-100' : 'scale-x-0'
        }`}
      />
      {/* PACKET: data in transit while the next agent works on it. */}
      {flowing &&
        [0, 1, 2].map((i) => (
          <span key={i} aria-hidden className="packet" style={{ animationDelay: `${(-i * 1.4) / 3}s` }} />
        ))}
    </div>
  )
}

/** Live view of the agent pipeline with flowing connectors and the repair loop. */
export function PipelineGraph({ agents, repairAttempts, phase }: Props) {
  const done = AGENT_NAMES.filter((n) => agents[n] === 'done').length
  const finished = phase === 'succeeded' || phase === 'failed'
  const progress = finished ? 100 : (done / AGENT_NAMES.length) * 100
  const repairing = repairAttempts > 0
  const looping = repairing && phase === 'streaming'

  return (
    <section aria-label="Pipeline" className="glass relative overflow-hidden rounded-3xl p-4 sm:p-6">
      <div className="relative mb-6 h-1.5 rounded-full bg-zinc-900/[0.07] dark:bg-white/10" role="progressbar" aria-label="Pipeline progress" aria-valuenow={Math.round(progress)} aria-valuemin={0} aria-valuemax={100}>
        {phase === 'starting' ? (
          // Indeterminate: a scanner sweeps until the first agent reports.
          <div className="absolute inset-0 overflow-hidden rounded-full">
            <div className="progress-scanner h-full w-1/5 rounded-full bg-gradient-to-r from-transparent via-cyan-400 to-transparent" />
          </div>
        ) : (
          <>
            <div
              className={`absolute inset-0 origin-left rounded-full ${
                phase === 'failed' ? 'bg-red-500' : 'bg-gradient-to-r from-emerald-400 via-cyan-400 to-violet-400'
              }`}
              style={{
                transform: `scaleX(${progress / 100})`,
                transition: 'transform var(--dur-spring-settle) var(--spring-settle)',
              }}
            />
            {/* A glowing head rides the leading edge while work continues. */}
            {phase === 'streaming' && (
              <span
                aria-hidden
                className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 animate-pulse rounded-full bg-white shadow-[0_0_14px_4px_var(--glow-b)]"
                style={{ left: `${progress}%`, transition: 'left var(--dur-spring-settle) var(--spring-settle)' }}
              />
            )}
          </>
        )}
      </div>

      <div className="grid grid-cols-[auto_1fr_auto_1fr_auto_1fr_auto] items-center gap-x-1.5 sm:gap-x-3">
        {/* Repair arc: healer -> provisioner, spanning columns 5-7. */}
        <div
          className={`relative col-start-5 col-end-8 row-start-1 mx-7 mb-1 h-10 transition-opacity duration-500 sm:mx-10 sm:h-12 ${
            repairing ? 'opacity-100' : 'opacity-25'
          }`}
          aria-hidden
        >
          <svg viewBox="0 0 100 30" preserveAspectRatio="none" className="absolute inset-0 size-full overflow-visible">
            <path
              d="M100 30 C100 0, 0 0, 0 30"
              fill="none"
              stroke={repairing ? 'url(#repair-gradient)' : 'currentColor'}
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
              className={looping ? 'repair-path' : ''}
              strokeDasharray={repairing ? undefined : '3 4'}
            />
            {/* PACKET: the healer's diagnosis travelling back to the provisioner. */}
            {looping &&
              [0, -0.8].map((delay) => (
                <path
                  key={delay}
                  d="M100 30 C100 0, 0 0, 0 30"
                  pathLength={100}
                  fill="none"
                  stroke="#f5d0fe"
                  strokeWidth="4"
                  strokeLinecap="round"
                  vectorEffect="non-scaling-stroke"
                  className="arc-packet"
                  style={{ animationDelay: `${delay}s` }}
                />
              ))}
            <defs>
              <linearGradient id="repair-gradient" x1="1" x2="0">
                <stop offset="0%" stopColor="#f472b6" />
                <stop offset="100%" stopColor="#a78bfa" />
              </linearGradient>
            </defs>
          </svg>
          <ChevronLeft className="absolute bottom-0 left-0 size-4 -translate-x-1/2 rotate-[-60deg] text-violet-400" />
          <span
            key={repairAttempts}
            className={`absolute -top-2 left-1/2 -translate-x-1/2 rounded-full px-2 py-0.5 font-mono text-[10px] whitespace-nowrap ${
              repairing
                ? 'animate-pop bg-violet-500/15 text-violet-700 ring-1 ring-violet-500/30 dark:text-violet-300'
                : 'text-zinc-400'
            }`}
          >
            repair {repairAttempts}/{MAX_REPAIR_ATTEMPTS}
          </span>
        </div>

        {AGENT_NAMES.map((name, i) => (
          <Fragment key={name}>
            <div className="row-start-2">
              <Node name={name} status={agents[name]} />
            </div>
            {i < AGENT_NAMES.length - 1 && (
              <div className="row-start-2">
                <Connector from={agents[name]} to={agents[AGENT_NAMES[i + 1]]} />
              </div>
            )}
          </Fragment>
        ))}
      </div>
    </section>
  )
}
