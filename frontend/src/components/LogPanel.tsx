import { useLayoutEffect, useRef } from 'react'
import type { LogLine } from '../hooks/useDeploymentStream'
import type { LogLevel } from '../types/events'

const LEVEL_CLASS: Record<LogLevel, string> = {
  info: 'text-zinc-300',
  warn: 'text-amber-300',
  error: 'text-red-400',
  success: 'text-emerald-400',
}

function time(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour12: false })
}

/** Terminal-style log. Stays dark in both themes; follows new lines unless scrolled up. */
export function LogPanel({ logs, active }: { logs: LogLine[]; active: boolean }) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const prevHeightRef = useRef(0)

  // Before paint, follow new lines only if the view was at the bottom of the
  // previous content, so scrolling up to read history isn't interrupted.
  useLayoutEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const wasAtBottom = prevHeightRef.current - el.scrollTop - el.clientHeight < 24
    if (wasAtBottom) el.scrollTop = el.scrollHeight
    prevHeightRef.current = el.scrollHeight
  }, [logs.length])

  return (
    <section
      aria-label="Deployment logs"
      className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950 shadow-sm"
    >
      <div className="flex items-center gap-2 border-b border-zinc-800 px-4 py-2.5">
        <span className="size-3 rounded-full bg-zinc-700" />
        <span className="size-3 rounded-full bg-zinc-700" />
        <span className="size-3 rounded-full bg-zinc-700" />
        <span className="ml-2 font-mono text-xs text-zinc-500">deploysmith — logs</span>
      </div>
      <div
        ref={scrollRef}
        role="log"
        aria-live="polite"
        className="h-80 overflow-y-auto p-4 font-mono text-xs leading-relaxed sm:h-[26rem] sm:text-[13px]"
      >
        {logs.length === 0 ? (
          <p className="text-zinc-500">$ waiting for a repository…</p>
        ) : (
          logs.map((line) => (
            <div key={line.id} className="flex gap-3 whitespace-pre-wrap break-words">
              <span className="shrink-0 text-zinc-600">{time(line.timestamp)}</span>
              <span className="w-[11ch] shrink-0 text-zinc-500">{line.agent ?? 'system'}</span>
              <span className={`min-w-0 ${LEVEL_CLASS[line.level]}`}>{line.message}</span>
            </div>
          ))
        )}
        {active && <span className="inline-block h-4 w-2 animate-pulse bg-zinc-400 align-middle" />}
      </div>
    </section>
  )
}
