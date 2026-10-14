import { CircleCheck, CircleX } from 'lucide-react'
import type { DeploymentState } from '../types/events'

export function DeploymentSummary({ result, error }: { result: DeploymentState | null; error: string | null }) {
  if (!result) {
    return error ? (
      <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
        {error}
      </div>
    ) : null
  }

  const healthy = result.health_report?.healthy === true && result.errors.length === 0
  return (
    <section
      aria-label="Deployment result"
      className={`rounded-xl border p-4 text-sm ${
        healthy
          ? 'border-emerald-200 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950/60'
          : 'border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/60'
      }`}
    >
      <p className="flex items-center gap-2 font-semibold">
        {healthy ? (
          <CircleCheck className="size-4 text-emerald-600 dark:text-emerald-400" aria-hidden />
        ) : (
          <CircleX className="size-4 text-red-600 dark:text-red-400" aria-hidden />
        )}
        {healthy ? 'Deployment healthy' : 'Deployment failed'}
        {result.repair_attempts > 0 && (
          <span className="font-normal text-zinc-600 dark:text-zinc-400">
            · {result.repair_attempts} repair{result.repair_attempts > 1 ? 's' : ''}
          </span>
        )}
      </p>
      {result.deployment_results.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {result.deployment_results.map((r) => (
            <li key={r.component} className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-medium">{r.component}</span>
              <span className="text-xs text-zinc-500">{r.platform}</span>
              <span className="min-w-0 break-all font-mono text-xs text-zinc-700 dark:text-zinc-300">{r.url}</span>
            </li>
          ))}
        </ul>
      )}
      {result.errors.length > 0 && (
        <ul className="mt-3 list-inside list-disc text-red-800 dark:text-red-300">
          {result.errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs text-zinc-500">Profiling and planning are real; deployment and health checks are simulated, so these URLs are not live yet.</p>
    </section>
  )
}
