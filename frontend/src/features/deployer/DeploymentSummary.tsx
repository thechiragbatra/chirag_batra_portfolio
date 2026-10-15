import { CircleCheck, CircleX, ExternalLink } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { confetti } from './confetti'
import type { DeploymentState } from '../../types/events'

export function DeploymentSummary({ result, error }: { result: DeploymentState | null; error: string | null }) {
  const ref = useRef<HTMLElement>(null)
  const healthy = result !== null && result.health_report?.healthy === true && result.errors.length === 0
  const sandbox = result?.deployment_results.some((r) => r.platform === 'sandbox') ?? false
  const sandboxLive = result?.deployment_results.some((r) => r.platform === 'sandbox' && r.status === 'live') ?? false

  useEffect(() => {
    if (!healthy || !ref.current) return
    // The card may be below the fold when the run ends; keep the burst on screen.
    const rect = ref.current.getBoundingClientRect()
    const y = Math.min(Math.max(rect.top + 24, 120), innerHeight * 0.55)
    confetti({ x: rect.left + rect.width / 2, y })
  }, [healthy])

  if (!result) {
    return error ? (
      <div
        role="alert"
        className="animate-shake rounded-2xl border border-red-400/40 bg-red-500/10 p-4 text-sm text-red-800 backdrop-blur-xl dark:text-red-200"
      >
        {error}
      </div>
    ) : null
  }

  return (
    <section
      ref={ref}
      aria-label="Deployment result"
      data-glow={healthy || undefined}
      className={`glow-border rounded-2xl border p-4 text-sm backdrop-blur-xl ${
        healthy ? 'animate-blur-in border-emerald-400/40 bg-emerald-500/10' : 'animate-shake border-red-400/40 bg-red-500/10'
      }`}
    >
      <p className="font-display flex items-center gap-2 text-base font-semibold">
        {healthy ? (
          <CircleCheck className="animate-pop size-5 text-emerald-500" aria-hidden />
        ) : (
          <CircleX className="animate-pop size-5 text-red-500" aria-hidden />
        )}
        {healthy ? 'Deployment healthy' : 'Deployment failed'}
        {result.repair_attempts > 0 && (
          <span className="text-sm font-normal text-zinc-600 dark:text-zinc-400">
            · {result.repair_attempts} repair{result.repair_attempts > 1 ? 's' : ''}
          </span>
        )}
      </p>
      {result.deployment_results.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {result.deployment_results.map((r, i) => (
            <li
              key={r.component}
              className="animate-fade-up flex flex-wrap items-baseline gap-x-2"
              style={{ animationDelay: `${200 + i * 120}ms` }}
            >
              <span className="font-medium">{r.component}</span>
              <span className="rounded bg-zinc-900/5 px-1.5 font-mono text-[10px] text-zinc-500 dark:bg-white/10">{r.platform}</span>
              {r.status === 'failed' && (
                <span className="rounded bg-red-500/15 px-1.5 font-mono text-[10px] font-semibold text-red-700 uppercase dark:text-red-300">
                  not deployed
                </span>
              )}
              {r.platform === 'sandbox' && r.url ? (
                <a
                  href={r.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex min-w-0 items-center gap-1 font-mono text-xs break-all text-emerald-700 hover:underline dark:text-emerald-300"
                >
                  {r.url} <ExternalLink className="size-3 shrink-0" aria-hidden />
                </a>
              ) : (
                <span className="min-w-0 font-mono text-xs break-all text-zinc-700 dark:text-zinc-300">{r.url}</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {!healthy && result.health_report?.diagnosis && (
        <p className="mt-3 text-red-800 dark:text-red-300">
          <span className="font-medium">Diagnosis:</span> {result.health_report.diagnosis}
        </p>
      )}
      {result.errors.length > 0 && (
        <ul className="mt-3 list-inside list-disc text-red-800 dark:text-red-300">
          {result.errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs text-zinc-500">
        {sandbox && !sandboxLive ? (
          'Nothing was built: the reason is in the log above.'
        ) : sandbox ? (
          <>
            Built and served in Docker on this machine. Manage deploys and rollbacks on the{' '}
            <Link to="/apps" viewTransition className="font-medium text-emerald-700 hover:underline dark:text-emerald-300">
              Apps page
            </Link>
            .
          </>
        ) : (
          'Profiling and planning are real; deployment is simulated, so these URLs are not live.'
        )}
      </p>
    </section>
  )
}
