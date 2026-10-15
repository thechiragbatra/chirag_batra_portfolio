import { Rocket, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AgentStatusList } from '../features/deployer/AgentStatusList'
import { DeploymentSummary } from '../features/deployer/DeploymentSummary'
import { LogPanel } from '../features/deployer/LogPanel'
import { PageHeader } from '../components/ui/PageHeader'
import { PipelineGraph } from '../features/deployer/PipelineGraph'
import { useDeploymentStream } from '../features/deployer/useDeploymentStream'
import { setActivity } from '../lib/activity'
import { isGithubRepoUrl } from '../lib/githubUrl'

const EXAMPLES = [
  { label: 'FastAPI + React + Postgres', url: 'https://github.com/fastapi/full-stack-fastapi-template' },
  { label: 'Streamlit app', url: 'https://github.com/streamlit/streamlit-example' },
  { label: 'Static site', url: 'https://github.com/octocat/Spoon-Knife' },
]

/** Seconds since `startedAt`, ticking while busy and frozen at the last tick when it ends. */
function useElapsed(busy: boolean, startedAt: number | null) {
  const [now, setNow] = useState(0)

  useEffect(() => {
    if (!busy) return
    const timer = setInterval(() => setNow(performance.now()), 100)
    return () => clearInterval(timer)
  }, [busy])

  return startedAt === null ? 0 : Math.max(0, now - startedAt) / 1000
}

const RUN_ID = /^[0-9a-f]{32}$/

/**
 * /deployer, or /deployer?run=<id>&repo=<url> to watch a run started elsewhere (the AI
 * guide). Keyed by run, so a new run remounts the page with fresh state.
 */
export default function DeployerPage() {
  const [params] = useSearchParams()
  const run = params.get('run')
  const valid = run && RUN_ID.test(run) ? run : null
  const repo = params.get('repo')
  return <Deployer key={valid ?? 'new'} run={valid} repo={repo && isGithubRepoUrl(repo) ? repo : null} />
}

function Deployer({ run, repo }: { run: string | null; repo: string | null }) {
  const [repoUrl, setRepoUrl] = useState(repo ?? '')
  const [inputError, setInputError] = useState<string | null>(null)
  const [startedAt, setStartedAt] = useState<number | null>(() => (run ? performance.now() : null))
  const stream = useDeploymentStream()
  const finished = stream.phase === 'succeeded' || stream.phase === 'failed'
  const elapsed = useElapsed(stream.isBusy, startedAt)
  const inputRef = useRef<HTMLInputElement>(null)
  const { attach } = stream
  const busy = stream.isBusy

  // The background surges while a deployment streams.
  useEffect(() => {
    setActivity('deploy', busy ? 1 : 0)
    return () => setActivity('deploy', 0)
  }, [busy])

  // Opened on a run someone else started (the AI guide): follow its live stream.
  useEffect(() => {
    if (run) attach(run, repo ?? 'the requested repository')
  }, [run, repo, attach])

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!isGithubRepoUrl(repoUrl)) {
      setInputError('Enter a GitHub repository URL like https://github.com/owner/repo')
      return
    }
    setInputError(null)
    setStartedAt(performance.now())
    void stream.start(repoUrl.trim())
  }

  return (
    <>
      <PageHeader
        eyebrow="Live demo"
        title={
          <>
            Ship a repo. <span className="text-aurora">Watch it think.</span>
          </>
        }
      >
        Paste a public GitHub repository. Four agents clone and profile it, plan free-tier hosting,
        deploy, and self-heal, streaming every step below.
      </PageHeader>

      <form onSubmit={onSubmit} noValidate className="mb-3">
        <label htmlFor="repo-url" className="sr-only">
          Repository URL
        </label>
        <div
          data-glow={stream.isBusy || undefined}
          className="glass glow-border flex flex-col gap-2 rounded-2xl p-2 shadow-xl shadow-black/[0.04] transition-shadow focus-within:shadow-[0_0_50px_-12px_var(--glow-a)] sm:flex-row dark:shadow-black/40"
        >
          <div className="flex min-w-0 flex-1 items-center gap-2 px-2">
            <span aria-hidden className="font-mono text-lg font-bold text-emerald-500">
              $
            </span>
            <input
              ref={inputRef}
              id="repo-url"
              type="url"
              inputMode="url"
              autoComplete="off"
              spellCheck={false}
              placeholder="https://github.com/owner/repo"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              aria-invalid={inputError !== null}
              aria-describedby={inputError ? 'repo-url-error' : undefined}
              className="min-w-0 flex-1 bg-transparent py-2.5 font-mono text-sm outline-none placeholder:text-zinc-400"
            />
          </div>
          <button
            type="submit"
            disabled={stream.isBusy}
            className="shine-hover pressable group inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-emerald-500/30 transition-all hover:shadow-emerald-500/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500 disabled:cursor-not-allowed disabled:opacity-70"
          >
            <Rocket
              aria-hidden
              className={`size-4 transition-transform duration-500 ${
                stream.isBusy ? 'animate-float' : 'group-hover:-translate-y-1 group-hover:translate-x-1 group-hover:-rotate-12'
              }`}
            />
            {stream.isBusy ? 'Deploying…' : 'Deploy'}
          </button>
        </div>
        {inputError && (
          <p id="repo-url-error" className="animate-fade-up mt-2 text-sm text-red-600 dark:text-red-400">
            {inputError}
          </p>
        )}
      </form>

      <div className="mb-8 flex flex-wrap items-center gap-2 text-xs">
        <span className="inline-flex items-center gap-1 text-zinc-500">
          <Sparkles className="size-3.5" aria-hidden /> Try
        </span>
        {EXAMPLES.map((example) => (
          <button
            key={example.url}
            type="button"
            disabled={stream.isBusy}
            onClick={() => {
              setRepoUrl(example.url)
              setInputError(null)
              inputRef.current?.focus()
            }}
            className="glass rounded-full px-3 py-1 font-medium text-zinc-700 transition-all hover:-translate-y-0.5 hover:text-emerald-700 disabled:opacity-50 dark:text-zinc-300 dark:hover:text-emerald-300"
          >
            {example.label}
          </button>
        ))}
      </div>

      <div className="mb-6">
        <PipelineGraph agents={stream.agents} repairAttempts={stream.repairAttempts} phase={stream.phase} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[20rem_1fr] lg:items-start">
        <div className="space-y-5">
          <AgentStatusList agents={stream.agents} repairAttempts={stream.repairAttempts} />
          {finished && <DeploymentSummary key={stream.deploymentId} result={stream.result} error={stream.error} />}
        </div>
        <LogPanel logs={stream.logs} active={stream.isBusy} elapsed={elapsed} />
      </div>
    </>
  )
}
