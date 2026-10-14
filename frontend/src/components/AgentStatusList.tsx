import { Circle, CircleCheck, CircleX, LoaderCircle, type LucideIcon } from 'lucide-react'
import {
  AGENT_NAMES,
  MAX_REPAIR_ATTEMPTS,
  type AgentName,
  type AgentStatus,
} from '../types/events'

const DESCRIPTIONS: Record<AgentName, string> = {
  profiler: 'Analyzes the repo statically',
  strategist: 'Picks a free-tier platform per component',
  provisioner: 'Creates resources and deploys',
  healer: 'Health-checks and requests repairs',
}

const STATUS_STYLE: Record<AgentStatus, { icon: LucideIcon; className: string; label: string }> = {
  idle: { icon: Circle, className: 'text-zinc-400 dark:text-zinc-600', label: 'Idle' },
  running: { icon: LoaderCircle, className: 'animate-spin text-sky-600 dark:text-sky-400', label: 'Running' },
  done: { icon: CircleCheck, className: 'text-emerald-600 dark:text-emerald-400', label: 'Done' },
  failed: { icon: CircleX, className: 'text-red-600 dark:text-red-400', label: 'Failed' },
}

const PILL_STYLE: Record<AgentStatus, string> = {
  idle: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400',
  running: 'bg-sky-50 text-sky-700 dark:bg-sky-950 dark:text-sky-300',
  done: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
  failed: 'bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300',
}

interface Props {
  agents: Record<AgentName, AgentStatus>
  repairAttempts: number
}

export function AgentStatusList({ agents, repairAttempts }: Props) {
  return (
    <section
      aria-labelledby="agents-heading"
      className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"
    >
      <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
        <h2 id="agents-heading" className="text-sm font-semibold">
          Agents
        </h2>
        <span
          className={`text-xs tabular-nums ${repairAttempts > 0 ? 'text-amber-700 dark:text-amber-400' : 'text-zinc-500'}`}
        >
          Repairs {repairAttempts}/{MAX_REPAIR_ATTEMPTS}
        </span>
      </div>
      <ol className="divide-y divide-zinc-200 dark:divide-zinc-800">
        {AGENT_NAMES.map((name) => {
          const status = agents[name]
          const { icon: Icon, className, label } = STATUS_STYLE[status]
          return (
            <li key={name} className="flex items-center gap-3 px-4 py-3">
              <Icon className={`size-5 shrink-0 ${className}`} aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium capitalize">{name}</p>
                <p className="truncate text-xs text-zinc-500">{DESCRIPTIONS[name]}</p>
              </div>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${PILL_STYLE[status]}`}>
                {label}
              </span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
