import { Check, ChevronLeft, X } from 'lucide-react'
import { Fragment } from 'react'
import type { Phase } from '../hooks/useDeploymentStream'
import { AGENT_NAMES, MAX_REPAIR_ATTEMPTS, type AgentName, type AgentStatus } from '../types/events'
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
        className={`relative grid size-14 place-items-center sm:size-20 ${status === 'failed' ? 'animate-shake' : ''}`}
      >
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
              <Check className="size-3" strokeWidth={3} aria-hidden />
            </span>
          )}
          {status === 'failed' && (
            <span className="animate-pop absolute -top-1.5 -right-1.5 grid size-5 place-items-center rounded-full bg-red-500 text-white shadow-lg ring-2 ring-white dark:ring-zinc-950">
              <X className="size-3" strokeWidth={3} aria-hidden />
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
    <div className="relative mb-10 h-[3px] min-w-3 overflow-hidden rounded-full bg-zinc-900/10 sm:mb-12 dark:bg-white/10">
      <div
        className={`absolute inset-0 origin-left rounded-full transition-transform duration-700 ease-out ${
          filled ? 'scale-x-100 bg-gradient-to-r from-emerald-400 to-cyan-400' : flowing ? 'connector-flow scale-x-100' : 'scale-x-0'
        }`}
      />
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
      <div className="mb-6 h-1.5 overflow-hidden rounded-full bg-zinc-900/[0.07] dark:bg-white/10">
        <div
          className={`relative h-full rounded-full transition-all duration-700 ease-out ${
            phase === 'failed' ? 'bg-red-500' : 'bg-gradient-to-r from-emerald-400 via-cyan-400 to-violet-400'
          } ${phase === 'streaming' || phase === 'starting' ? 'shine' : ''}`}
          style={{ width: `${phase === 'starting' ? 4 : progress}%` }}
        />
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
