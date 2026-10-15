import {
  Boxes,
  ExternalLink,
  FileTerminal,
  Globe,
  History,
  LoaderCircle,
  Power,
  RefreshCw,
  RotateCcw,
  Server,
  Square,
  Trash2,
  TriangleAlert,
} from 'lucide-react'
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { PageHeader } from '../components/ui/PageHeader'
import { deleteApp, getDeployLog, listApps, rollbackApp, stopApp } from '../lib/api'
import type { App, AppsResponse, Deployment } from '../types/apps'

const STATUS_STYLE: Record<Deployment['status'], string> = {
  ready: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300',
  failed: 'bg-red-500/15 text-red-700 dark:text-red-300',
  building: 'bg-amber-500/15 text-amber-700 dark:text-amber-300',
}

const POLL_MS = 3000

const buttonClass =
  'inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50'

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function DeployRow({
  app,
  deploy,
  busy,
  onActivate,
}: {
  app: App
  deploy: Deployment
  busy: boolean
  onActivate: (deployId: string) => void
}) {
  // The text stays after closing so the drawer can slide shut with its content.
  const [log, setLog] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const [loadingLog, setLoadingLog] = useState(false)
  const logId = useId()
  const live = app.current === deploy.id

  const toggleLog = async () => {
    if (open) {
      setOpen(false)
      return
    }
    setLoadingLog(true)
    try {
      setLog(await getDeployLog(app.name, deploy.id))
    } catch (error) {
      setLog(error instanceof Error ? error.message : 'Could not load the log')
    } finally {
      setLoadingLog(false)
      setOpen(true)
    }
  }

  return (
    <li className="border-t border-[var(--glass-border)] py-2.5 first:border-t-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm">
        <span className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase ${STATUS_STYLE[deploy.status]}`}>
          {deploy.status === 'building' && <LoaderCircle className="mr-1 inline size-3 animate-spin" aria-hidden />}
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
            aria-expanded={open}
            aria-controls={logId}
            className={`${buttonClass} text-zinc-700 hover:bg-zinc-900/5 dark:text-zinc-300 dark:hover:bg-white/10`}
          >
            <FileTerminal className={`size-3.5 ${loadingLog ? 'animate-pulse' : ''}`} aria-hidden /> {open ? 'Hide log' : 'Log'}
          </button>
          {deploy.status === 'ready' && !live && (
            <button
              type="button"
              onClick={() => onActivate(deploy.id)}
              disabled={busy}
              className={`${buttonClass} text-emerald-700 hover:bg-emerald-500/10 dark:text-emerald-300`}
            >
              {app.current ? (
                <>
                  <RotateCcw className="size-3.5" aria-hidden /> Roll back
                </>
              ) : (
                <>
                  <Power className="size-3.5" aria-hidden /> Make live
                </>
              )}
            </button>
          )}
        </span>
      </div>
      {deploy.error && <p className="mt-1 text-xs break-words text-red-700 dark:text-red-300">{deploy.error}</p>}
      {/* Slides open and shut (grid-template-rows 0fr → 1fr) instead of popping. */}
      <div className="drawer" data-open={open || undefined} inert={!open}>
        <div>
          <pre
            id={logId}
            tabIndex={open ? 0 : -1}
            aria-label={`Build log for ${deploy.id}`}
            className="mt-2 max-h-72 overflow-auto rounded-xl bg-zinc-950 p-3 font-mono text-[11px] leading-relaxed text-zinc-200 focus-visible:outline-2 focus-visible:outline-emerald-500"
          >
            {log || '(empty: nothing ran in the sandbox for this deploy)'}
          </pre>
        </div>
      </div>
    </li>
  )
}

function AppCard({
  app,
  onChange,
  onDeleted,
}: {
  app: App
  onChange: (next: App) => void
  onDeleted: () => void
}) {
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const ModeIcon = app.mode === 'server' ? Server : Globe

  const act = async (label: string, action: () => Promise<void>) => {
    setBusy(label)
    setError(null)
    try {
      await action()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setBusy(null)
    }
  }

  return (
    <article
      aria-busy={busy !== null}
      className="glass-strong glow-border animate-fade-up rounded-2xl p-5"
      data-glow={app.url ? true : undefined}
    >
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="font-display flex flex-wrap items-center gap-2 text-xl font-semibold">
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
              className="mt-2 inline-flex items-center gap-1.5 font-mono text-sm break-all text-emerald-700 hover:underline dark:text-emerald-300"
            >
              <span aria-hidden className="led size-2 shrink-0 rounded-full bg-emerald-500 shadow-[0_0_8px_2px_rgba(16,185,129,0.6)]" />
              {app.url} <ExternalLink className="size-3.5 shrink-0" aria-hidden />
            </a>
          ) : (
            <p className="mt-2 text-sm text-zinc-500">Stopped. Use “Make live” on a deploy to bring it back.</p>
          )}
        </div>
        <div className="flex gap-1">
          {app.url && (
            <button
              type="button"
              disabled={busy !== null}
              onClick={() =>
                act('Stopping…', async () => {
                  await stopApp(app.name)
                  onChange({ ...app, current: null, url: null })
                })
              }
              className={`${buttonClass} glass text-zinc-700 hover:bg-white/80 dark:text-zinc-300 dark:hover:bg-white/10`}
            >
              <Square className="size-3.5" aria-hidden /> Stop
            </button>
          )}
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => {
              if (!confirm(`Delete ${app.name} and all of its deploys?`)) return
              void act('Deleting…', async () => {
                await deleteApp(app.name)
                onDeleted()
              })
            }}
            className={`${buttonClass} glass text-red-700 hover:bg-red-500/10 dark:text-red-300`}
          >
            <Trash2 className="size-3.5" aria-hidden /> Delete
          </button>
        </div>
      </div>
      <p aria-live="polite" className="sr-only">
        {busy ?? ''}
      </p>
      {busy && (
        <p className="mt-3 inline-flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400" aria-hidden>
          <LoaderCircle className="size-4 animate-spin" /> {busy}
        </p>
      )}
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
            busy={busy !== null}
            onActivate={(deployId) =>
              act(app.current ? 'Rolling back…' : 'Starting…', async () => onChange(await rollbackApp(app.name, deployId)))
            }
          />
        ))}
      </ul>
    </article>
  )
}

function Banner({ children }: { children: ReactNode }) {
  return (
    <p className="glass mb-6 flex items-start gap-2.5 rounded-2xl border-amber-400/40 p-4 text-sm text-amber-900 dark:text-amber-200">
      <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-500" aria-hidden />
      <span>{children}</span>
    </p>
  )
}

export default function Apps() {
  const [data, setData] = useState<AppsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const headingRef = useRef<HTMLHeadingElement>(null)

  const refresh = useCallback(async () => {
    setRefreshing(true)
    try {
      setData(await listApps())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load apps')
    } finally {
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    listApps()
      .then((response) => {
        if (!cancelled) setData(response)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load apps')
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Follow builds in progress: poll while any deploy is still building.
  const building = data?.apps.some((a) => a.deployments.some((d) => d.status === 'building')) ?? false
  useEffect(() => {
    if (!building) return
    const timer = setInterval(() => void refresh(), POLL_MS)
    return () => clearInterval(timer)
  }, [building, refresh])

  const replace = (name: string, next: App) =>
    setData((current) => current && { ...current, apps: current.apps.map((a) => (a.name === name ? next : a)) })
  const remove = (name: string) => {
    setData((current) => current && { ...current, apps: current.apps.filter((a) => a.name !== name) })
    headingRef.current?.focus()
  }

  const apps = data?.apps ?? null
  const anyLive = apps?.some((a) => a.url) ?? false

  return (
    <>
      <PageHeader
        eyebrow="Sandbox engine"
        titleRef={headingRef}
        title={
          <>
            Your apps, <span className="text-aurora">served locally.</span>
          </>
        }
      >
        Everything the deployer built in Docker on this machine. Each deploy is immutable: roll back
        in one click, read its build log, or stop the app.
      </PageHeader>

      <div className="mb-6 flex justify-end">
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={refreshing}
          className={`${buttonClass} glass text-zinc-700 hover:bg-white/80 dark:text-zinc-300 dark:hover:bg-white/10`}
        >
          <RefreshCw className={`size-3.5 ${refreshing ? 'animate-spin' : ''}`} aria-hidden /> Refresh
        </button>
      </div>

      {data && !data.engine_enabled && (
        <Banner>
          The sandbox engine is off, so the Deployer only simulates deploys. Restart the backend with{' '}
          <code className="font-mono">SANDBOX_ENGINE=1</code> (Docker must be running) to build and serve apps here.
        </Banner>
      )}
      {data && data.engine_enabled && anyLive && !data.router_running && (
        <Banner>
          The router container is not running, so the links below will not open. It starts again on the next
          deploy, rollback or backend restart.
        </Banner>
      )}

      {error && (
        <div role="alert" className="mb-6 flex flex-wrap items-center gap-3 rounded-2xl border border-red-400/40 bg-red-500/10 p-4 text-sm text-red-800 dark:text-red-200">
          <span className="flex-1">{error}</span>
          <button type="button" onClick={() => void refresh()} className={`${buttonClass} glass`}>
            <RefreshCw className="size-3.5" aria-hidden /> Retry
          </button>
        </div>
      )}

      {apps === null && !error && (
        <div aria-busy className="grid gap-5" aria-label="Loading apps">
          {[0, 1].map((i) => (
            <div key={i} className="glass skeleton h-40 rounded-2xl" />
          ))}
        </div>
      )}

      {apps !== null && apps.length === 0 && !error && (
        <div className="glass animate-fade-up flex flex-col items-center gap-3 rounded-2xl p-10 text-center">
          <Boxes className="size-8 text-emerald-500" aria-hidden />
          <p className="font-medium">No apps yet</p>
          <p className="max-w-md text-sm text-zinc-600 dark:text-zinc-400">
            {data?.engine_enabled
              ? 'Deploy a repository and it will show up here with a live *.localhost URL.'
              : 'Turn on the sandbox engine (see above) and deploy a repository; it will show up here with a live *.localhost URL.'}
          </p>
          <Link to="/deployer" viewTransition className="text-sm font-semibold text-emerald-700 hover:underline dark:text-emerald-300">
            Open the deployer →
          </Link>
        </div>
      )}
      <div className="grid gap-5">
        {apps?.map((app) => (
          <AppCard key={app.name} app={app} onChange={(next) => replace(app.name, next)} onDeleted={() => remove(app.name)} />
        ))}
      </div>
    </>
  )
}
