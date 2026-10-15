import { useLayoutEffect, useRef } from 'react'
import type { LogLine } from './useDeploymentStream'
import type { AgentName, LogLevel } from '../../types/events'

const LEVEL_CLASS: Record<LogLevel, string> = {
  info: 'text-zinc-300',
  warn: 'text-amber-300 [text-shadow:0_0_10px_rgba(252,211,77,0.45)]',
  error: 'text-red-400 [text-shadow:0_0_10px_rgba(248,113,113,0.55)]',
  success: 'text-emerald-300 [text-shadow:0_0_10px_rgba(52,211,153,0.55)]',
}

const AGENT_CLASS: Record<AgentName | 'system', string> = {
  profiler: 'text-emerald-400/80',
  strategist: 'text-cyan-400/80',
  provisioner: 'text-violet-400/80',
  healer: 'text-pink-400/80',
  system: 'text-zinc-500',
}

function time(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour12: false })
}

interface Props {
  logs: LogLine[]
  active: boolean
  elapsed: number
}

/** CRT-style terminal. Stays dark in both themes; follows new lines unless scrolled up. */
export function LogPanel({ logs, active, elapsed }: Props) {
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
      className={`relative flex min-h-0 flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#07090d] shadow-2xl shadow-black/30 transition-shadow duration-700 ${
        active ? 'shadow-[0_0_60px_-15px_rgba(34,211,238,0.5)]' : ''
      }`}
    >
      <div className="flex items-center gap-2 border-b border-white/[0.07] bg-white/[0.02] px-4 py-2.5">
        <span className="size-3 rounded-full bg-[#ff5f57]" />
        <span className="size-3 rounded-full bg-[#febc2e]" />
        <span className="size-3 rounded-full bg-[#28c840]" />
        <span className="ml-2 font-mono text-xs text-zinc-500">deploysmith — agents.log</span>
        {active && (
          <span className="ml-auto flex items-center gap-1.5 font-mono text-[10px] tracking-widest text-red-400">
            <span className="relative flex size-2">
              <span className="animate-ping-slow absolute inline-flex size-full rounded-full bg-red-500" />
              <span className="relative inline-flex size-2 rounded-full bg-red-500" />
            </span>
            LIVE
          </span>
        )}
      </div>
      {/* Powers on like a CRT the first time a run starts (the class is added once). */}
      <div className={`relative overflow-hidden ${logs.length > 0 ? 'crt-on' : ''}`}>
        <div
          ref={scrollRef}
          role="log"
          aria-live="polite"
          className="h-80 overflow-y-auto p-4 font-mono text-xs leading-relaxed sm:h-[26rem] sm:text-[13px]"
        >
          {logs.length === 0 ? (
            <p className="text-zinc-500">
              $ waiting for a repository<span className="animate-blink">_</span>
            </p>
          ) : (
            logs.map((line, i) => (
              <div key={line.id} className="animate-line-in flex gap-3 whitespace-pre-wrap break-words">
                <span className="hidden shrink-0 text-zinc-600 sm:inline">{time(line.timestamp)}</span>
                <span className={`w-[11ch] shrink-0 ${AGENT_CLASS[line.agent ?? 'system']}`}>{line.agent ?? 'system'}</span>
                {/* Only the newest lines type in, so a burst of events stays cheap. */}
                <span className={`min-w-0 ${LEVEL_CLASS[line.level]} ${i >= logs.length - 3 ? 'type-in' : ''}`}>
                  {line.message}
                </span>
              </div>
            ))
          )}
          {active && <span className="animate-blink inline-block h-4 w-2 bg-emerald-400 align-middle shadow-[0_0_8px_#34d399]" />}
        </div>
        <div aria-hidden className="scanlines pointer-events-none absolute inset-0" />
        {active && <div aria-hidden className="scan-band pointer-events-none absolute inset-x-0 top-0" />}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{ background: 'radial-gradient(ellipse at center, transparent 60%, rgba(0,0,0,0.45) 100%)' }}
        />
      </div>
      <div className="flex items-center justify-between border-t border-white/[0.07] px-4 py-1.5 font-mono text-[10px] text-zinc-500">
        <span>{logs.length} lines</span>
        <span className="tabular-nums">{elapsed > 0 ? `${elapsed.toFixed(1)}s` : '—'}</span>
      </div>
    </section>
  )
}
