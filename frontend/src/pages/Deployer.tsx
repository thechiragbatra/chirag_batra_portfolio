import { Rocket } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { AgentStatusList } from '../components/AgentStatusList'
import { DeploymentSummary } from '../components/DeploymentSummary'
import { LogPanel } from '../components/LogPanel'
import { PageHeader } from '../components/PageHeader'
import { useDeploymentStream } from '../hooks/useDeploymentStream'
import { isGithubRepoUrl } from '../lib/githubUrl'

export default function Deployer() {
  const [repoUrl, setRepoUrl] = useState('')
  const [inputError, setInputError] = useState<string | null>(null)
  const stream = useDeploymentStream()
  const finished = stream.phase === 'succeeded' || stream.phase === 'failed'

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!isGithubRepoUrl(repoUrl)) {
      setInputError('Enter a GitHub repository URL like https://github.com/owner/repo')
      return
    }
    setInputError(null)
    void stream.start(repoUrl.trim())
  }

  return (
    <>
      <PageHeader title="Deployer">
        Paste a public GitHub repository. Four agents profile it, plan free-tier hosting, deploy,
        and self-heal, streaming every step below.
      </PageHeader>

      <form onSubmit={onSubmit} noValidate className="mb-6">
        <label htmlFor="repo-url" className="mb-1.5 block text-sm font-medium">
          Repository URL
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
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
            className="min-w-0 flex-1 rounded-lg border border-zinc-300 bg-white px-3 py-2 font-mono text-sm placeholder:text-zinc-400 focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/20 focus:outline-none aria-invalid:border-red-500 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <button
            type="submit"
            disabled={stream.isBusy}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-600 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Rocket className="size-4" aria-hidden />
            {stream.isBusy ? 'Deploying…' : 'Deploy'}
          </button>
        </div>
        {inputError && (
          <p id="repo-url-error" className="mt-1.5 text-sm text-red-600 dark:text-red-400">
            {inputError}
          </p>
        )}
      </form>

      <div className="grid gap-5 lg:grid-cols-[20rem_1fr] lg:items-start">
        <div className="space-y-5">
          <AgentStatusList agents={stream.agents} repairAttempts={stream.repairAttempts} />
          {finished && <DeploymentSummary result={stream.result} error={stream.error} />}
        </div>
        <LogPanel logs={stream.logs} active={stream.isBusy} />
      </div>
    </>
  )
}
