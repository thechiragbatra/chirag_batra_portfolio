import { Circle, CircleCheck, CircleX, LoaderCircle, type LucideIcon } from 'lucide-react'
import { AGENT_NAMES, MAX_REPAIR_ATTEMPTS, type AgentName, type AgentStatus } from '../../types/events'
import { AGENT_META } from './agentMeta'

const STATUS_STYLE: Record<AgentStatus, { icon: LucideIcon; className: string; label: string }> = {
  idle: { icon: Circle, className: 'text-zinc-400 dark:text-zinc-600', label: 'Idle' },
  running: { icon: LoaderCircle, className: 'animate-spin text-cyan-500 dark:text-cyan-400', label: 'Running' },
  done: { icon: CircleCheck, className: 'text-emerald-600 dark:text-emerald-400', label: 'Done' },
  failed: { icon: CircleX, className: 'text-red-600 dark:text-red-400', label: 'Failed' },
}

const PILL_STYLE: Record<AgentStatus, string> = {
  idle: 'bg-zinc-900/5 text-zinc-500 dark:bg-white/5 dark:text-zinc-400',
  running: 'bg-cyan-500/15 text-cyan-700 ring-1 ring-cyan-500/30 dark:text-cyan-300',
  done: 'bg-emerald-500/15 text-emerald-700 ring-1 ring-emerald-500/30 dark:text-emerald-300',
  failed: 'bg-red-500/15 text-red-700 ring-1 ring-red-500/30 dark:text-red-300',
}

interface Props {
  agents: Record<AgentName, AgentStatus>
  repairAttempts: number
}

export function AgentStatusList({ agents, repairAttempts }: Props) {
  return (
    <section aria-labelledby="agents-heading" className="glass-strong overflow-hidden rounded-2xl">
      <div className="flex items-center justify-between border-b border-[var(--glass-border)] px-4 py-3">
        <h2 id="agents-heading" className="font-display text-sm font-semibold">
          Agents
        </h2>
        <span
          className={`font-mono text-xs tabular-nums ${repairAttempts > 0 ? 'text-violet-600 dark:text-violet-400' : 'text-zinc-500'}`}
        >
          Repairs {repairAttempts}/{MAX_REPAIR_ATTEMPTS}
        </span>
      </div>
      <ol className="divide-y divide-[var(--glass-border)]">
        {AGENT_NAMES.map((name) => {
          const status = agents[name]
          const { icon: Icon, className, label } = STATUS_STYLE[status]
          return (
            <li
              key={name}
              className={`relative flex items-center gap-3 px-4 py-3 transition-colors duration-500 ${
                status === 'running' ? 'bg-cyan-500/[0.07]' : ''
              }`}
            >
              {status === 'running' && (
                <span aria-hidden className="absolute inset-y-0 left-0 w-0.5 bg-gradient-to-b from-cyan-400 to-emerald-400" />
              )}
              <Icon className={`size-5 shrink-0 ${className}`} aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium capitalize">{name}</p>
                <p className="truncate text-xs text-zinc-500">{AGENT_META[name].description}</p>
              </div>
              <span key={status} className={`animate-pop rounded-full px-2 py-0.5 text-xs font-medium ${PILL_STYLE[status]}`}>
                {label}
              </span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
