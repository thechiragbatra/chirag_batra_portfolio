import { Boxes, ExternalLink, FileTerminal, Globe, History, RotateCcw, Server, Square, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { PageHeader } from '../components/PageHeader'
import { deleteApp, getDeployLog, listApps, rollbackApp, stopApp } from '../lib/api'
import type { App, Deployment } from '../types/apps'

const STATUS_STYLE: Record<Deployment['status'], string> = {
  ready: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300',
  failed: 'bg-red-500/15 text-red-700 dark:text-red-300',
  building: 'bg-amber-500/15 text-amber-700 dark:text-amber-300',
}

const buttonClass =
  'inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50'

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function DeployRow({
  app,
  deploy,
  busy,
  onRollback,
}: {
  app: App
  deploy: Deployment
  busy: boolean
  onRollback: (deployId: string) => void
}) {
  const [log, setLog] = useState<string | null>(null)
  const [loadingLog, setLoadingLog] = useState(false)
  const live = app.current === deploy.id

  const toggleLog = async () => {
    if (log !== null) {
      setLog(null)
      return
    }
    setLoadingLog(true)
    try {
      setLog(await getDeployLog(app.name, deploy.id))
    } catch (error) {
      setLog(error instanceof Error ? error.message : 'Could not load the log')
    } finally {
      setLoadingLog(false)
    }
  }

  return (
    <li className="border-t border-[var(--glass-border)] py-2.5 first:border-t-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm">
        <span className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase ${STATUS_STYLE[deploy.status]}`}>
          {deploy.status}
        </span>
        <span className="font-mono text-xs text-zinc-600 dark:text-zinc-400">{deploy.id}</span>
        <span className="text-xs text-zinc-500">{formatTime(deploy.created_at)}</span>
        {live && (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 uppercase dark:text-emerald-300">
            <span className="size-1.5 animate-pulse rounded-full bg-emerald-500" aria-hidden /> Live
          </span>
        )}
        <span className="ml-auto flex gap-1">
          <button
            type="button"
            onClick={toggleLog}
            disabled={loadingLog}
            className={`${buttonClass} text-zinc-700 hover:bg-zinc-900/5 dark:text-zinc-300 dark:hover:bg-white/10`}
          >
            <FileTerminal className="size-3.5" aria-hidden /> {log === null ? 'Log' : 'Hide log'}
          </button>
          {deploy.status === 'ready' && !live && (
            <button
              type="button"
              onClick={() => onRollback(deploy.id)}
              disabled={busy}
              className={`${buttonClass} text-emerald-700 hover:bg-emerald-500/10 dark:text-emerald-300`}
            >
              <RotateCcw className="size-3.5" aria-hidden /> Roll back
            </button>
          )}
        </span>
      </div>
      {deploy.error && <p className="mt-1 text-xs text-red-700 dark:text-red-300">{deploy.error}</p>}
      {log !== null && (
        <pre className="animate-fade-up mt-2 max-h-72 overflow-auto rounded-xl bg-zinc-950 p-3 font-mono text-[11px] leading-relaxed text-zinc-200">
          {log || '(empty: nothing ran in the sandbox for this deploy)'}
        </pre>
      )}
    </li>
  )
}

function AppCard({ app, onChange }: { app: App; onChange: (next: App | null) => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const ModeIcon = app.mode === 'server' ? Server : Globe

  const act = async (action: () => Promise<App | null>) => {
    setBusy(true)
    setError(null)
    try {
      onChange(await action())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="glass-strong glow-border animate-fade-up rounded-2xl p-5" data-glow={app.url ? true : undefined}>
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="font-display flex items-center gap-2 text-xl font-semibold">
            <ModeIcon className="size-5 text-emerald-500" aria-hidden />
            {app.name}
            <span className="rounded bg-zinc-900/5 px-1.5 font-mono text-[10px] font-normal text-zinc-500 dark:bg-white/10">
              {app.framework ?? app.mode} · {app.mode}
            </span>
          </h2>
          <p className="mt-1 truncate font-mono text-xs text-zinc-500">
            {app.component} from {app.repo_url.replace('https://github.com/', '')}
          </p>
          {app.url ? (
            <a
              href={app.url}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-flex items-center gap-1.5 font-mono text-sm text-emerald-700 hover:underline dark:text-emerald-300"
            >
              {app.url} <ExternalLink className="size-3.5" aria-hidden />
            </a>
          ) : (
            <p className="mt-2 text-sm text-zinc-500">Stopped. Roll back to a deploy to bring it online.</p>
          )}
        </div>
        <div className="flex gap-1">
          {app.url && (
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await stopApp(app.name)
                  return { ...app, current: null, url: null }
                })
              }
              className={`${buttonClass} glass text-zinc-700 hover:bg-white/80 dark:text-zinc-300 dark:hover:bg-white/10`}
            >
              <Square className="size-3.5" aria-hidden /> Stop
            </button>
          )}
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              if (!confirm(`Delete ${app.name} and all of its deploys?`)) return
              void act(async () => {
                await deleteApp(app.name)
                return null
              })
            }}
            className={`${buttonClass} glass text-red-700 hover:bg-red-500/10 dark:text-red-300`}
          >
            <Trash2 className="size-3.5" aria-hidden /> Delete
          </button>
        </div>
      </div>
      {error && (
        <p role="alert" className="mt-3 rounded-xl border border-red-400/40 bg-red-500/10 px-3 py-2 text-sm text-red-800 dark:text-red-200">
          {error}
        </p>
      )}
      <h3 className="mt-4 mb-1 flex items-center gap-1.5 text-xs font-semibold tracking-wide text-zinc-500 uppercase">
        <History className="size-3.5" aria-hidden /> Deploys
      </h3>
      <ul>
        {app.deployments.map((deploy) => (
          <DeployRow
            key={deploy.id}
            app={app}
            deploy={deploy}
            busy={busy}
            onRollback={(deployId) => act(() => rollbackApp(app.name, deployId))}
          />
        ))}
      </ul>
    </article>
  )
}

export default function Apps() {
  const [apps, setApps] = useState<App[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    listApps()
      .then((response) => {
        if (!cancelled) setApps(response.apps)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load apps')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const replace = (name: string, next: App | null) =>
    setApps((current) =>
      current === null ? current : next === null ? current.filter((a) => a.name !== name) : current.map((a) => (a.name === name ? next : a)),
    )

  return (
    <>
      <PageHeader
        eyebrow="Sandbox engine"
        title={
          <>
            Your apps, <span className="text-aurora">served locally.</span>
          </>
        }
      >
        Everything the deployer built in Docker on this machine. Each deploy is immutable: roll back
        in one click, read its build log, or stop the app.
      </PageHeader>

      {error && (
        <p role="alert" className="mb-6 rounded-2xl border border-red-400/40 bg-red-500/10 p-4 text-sm text-red-800 dark:text-red-200">
          {error}
        </p>
      )}
      {apps !== null && apps.length === 0 && !error && (
        <div className="glass animate-fade-up flex flex-col items-center gap-3 rounded-2xl p-10 text-center">
          <Boxes className="size-8 text-emerald-500" aria-hidden />
          <p className="font-medium">No apps yet</p>
          <p className="max-w-md text-sm text-zinc-600 dark:text-zinc-400">
            Start the backend with <code className="font-mono">SANDBOX_ENGINE=1</code> and deploy a repo. It will
            show up here with a live <code className="font-mono">*.localhost</code> URL.
          </p>
          <Link to="/deployer" className="text-sm font-semibold text-emerald-700 hover:underline dark:text-emerald-300">
            Open the deployer →
          </Link>
        </div>
      )}
      <div className="grid gap-5">
        {apps?.map((app) => (
          <AppCard key={app.name} app={app} onChange={(next) => replace(app.name, next)} />
        ))}
      </div>
    </>
  )
}
