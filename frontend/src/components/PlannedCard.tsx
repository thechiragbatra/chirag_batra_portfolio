import { Hammer } from 'lucide-react'
import type { PlannedProject } from '../types/content'

/** A project that exists as a design doc only. Clearly labelled so nobody mistakes it for shipped work. */
export function PlannedCard({ project }: { project: PlannedProject }) {
  return (
    <article className="glass-strong glow-border group flex h-full flex-col gap-3 rounded-2xl border-dashed p-5">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[11px] tracking-[0.15em] text-violet-600 uppercase dark:text-violet-300">
          {project.focus}
        </span>
        <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-semibold text-amber-700 ring-1 ring-amber-500/30 dark:text-amber-300">
          <span className="relative flex size-1.5" aria-hidden>
            <span className="animate-ping-slow absolute inline-flex size-full rounded-full bg-amber-400" />
            <span className="relative inline-flex size-1.5 rounded-full bg-amber-500" />
          </span>
          In development
        </span>
      </div>
      <h3 className="font-display text-lg font-semibold">{project.title}</h3>
      <p className="flex-1 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{project.summary}</p>
      <ul className="flex flex-wrap gap-1.5" aria-label="Planned stack">
        {project.tags.map((tag) => (
          <li
            key={tag}
            className="rounded-full border border-[var(--glass-border)] bg-white/50 px-2.5 py-0.5 font-mono text-[11px] text-zinc-700 dark:bg-white/5 dark:text-zinc-300"
          >
            {tag}
          </li>
        ))}
      </ul>
      <p className="flex items-center gap-1.5 pt-1 text-xs text-zinc-500">
        <Hammer className="size-3.5" aria-hidden /> Design doc written · code in progress
      </p>
    </article>
  )
}
