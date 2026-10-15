import { LoaderCircle, X } from 'lucide-react'
import { useId, useState, type FormEvent, type ReactNode } from 'react'
import { isGithubRepoUrl } from '../../lib/githubUrl'
import { previewProject, saveProject } from './projectEditor'
import type { Project } from '../../types/content'

const inputClass =
  'w-full min-w-0 rounded-lg border border-zinc-300 bg-white/80 px-3 py-2 text-sm placeholder:text-zinc-400 focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/20 focus:outline-none dark:border-zinc-700 dark:bg-black/40'
const primaryButton =
  'inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60'
const secondaryButton =
  'rounded-lg px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800'

function Field({ label, children, hint }: { label: string; children: (id: string) => ReactNode; hint?: string }) {
  const id = useId()
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">
        {label}
      </label>
      {children(id)}
      {hint && <p className="mt-1 text-xs text-zinc-500">{hint}</p>}
    </div>
  )
}

interface Draft {
  title: string
  description: string
  tags: string
  liveUrl: string
  githubUrl: string
}

const toDraft = (p: Project): Draft => ({
  title: p.title,
  description: p.description,
  tags: p.tags.join(', '),
  liveUrl: p.liveUrl ?? '',
  githubUrl: p.githubUrl,
})

/** Dev-only: fetch a repo's details from GitHub, edit them, then append to projects.json. */
export function AddProjectPanel({ onClose }: { onClose: () => void }) {
  const [repoUrl, setRepoUrl] = useState('')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchDetails = async (event: FormEvent) => {
    event.preventDefault()
    if (!isGithubRepoUrl(repoUrl)) {
      setError('Enter a GitHub repository URL like https://github.com/owner/repo')
      return
    }
    setBusy(true)
    setError(null)
    try {
      setDraft(toDraft(await previewProject(repoUrl)))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const save = async (event: FormEvent) => {
    event.preventDefault()
    if (!draft) return
    setBusy(true)
    setError(null)
    try {
      await saveProject({
        title: draft.title,
        description: draft.description,
        tags: draft.tags.split(',').map((t) => t.trim()).filter(Boolean),
        githubUrl: draft.githubUrl,
        ...(draft.liveUrl.trim() ? { liveUrl: draft.liveUrl.trim() } : {}),
      })
      onClose() // Vite hot-reloads projects.json, so the new card appears on its own.
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setBusy(false)
    }
  }

  const update = (key: keyof Draft) => (e: { target: { value: string } }) =>
    setDraft((d) => (d ? { ...d, [key]: e.target.value } : d))

  return (
    <section
      aria-labelledby="add-project-heading"
      className="glass glow-border animate-blur-in mb-8 rounded-2xl p-5" data-glow
    >
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 id="add-project-heading" className="font-semibold">
            Add a project
          </h2>
          <p className="text-sm text-zinc-500">
            Local dev only. Saves to <code className="font-mono text-xs">src/data/projects.json</code>; commit it to publish.
          </p>
        </div>
        <button type="button" onClick={onClose} className="rounded-lg p-1.5 text-zinc-500 hover:bg-zinc-200 dark:hover:bg-zinc-800" aria-label="Close">
          <X className="size-4" />
        </button>
      </div>

      {draft === null ? (
        <form onSubmit={fetchDetails} noValidate className="flex flex-col gap-2 sm:flex-row">
          <input
            aria-label="GitHub repository URL"
            type="url"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            autoFocus
            placeholder="https://github.com/owner/repo"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            className={`${inputClass} flex-1 font-mono`}
          />
          <button type="submit" disabled={busy} className={primaryButton}>
            {busy && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
            Fetch details
          </button>
        </form>
      ) : (
        <form onSubmit={save} className="grid gap-4">
          <p className="truncate font-mono text-xs text-zinc-500">{draft.githubUrl}</p>
          <Field label="Title">
            {(id) => <input id={id} required value={draft.title} onChange={update('title')} className={inputClass} />}
          </Field>
          <Field label="Description" hint={draft.description ? undefined : 'The repo has no GitHub description; write one here.'}>
            {(id) => (
              <textarea id={id} rows={3} value={draft.description} onChange={update('description')} className={inputClass} />
            )}
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Tags" hint="Comma-separated">
              {(id) => <input id={id} value={draft.tags} onChange={update('tags')} className={inputClass} />}
            </Field>
            <Field label="Live URL" hint="Optional, https://">
              {(id) => <input id={id} type="url" value={draft.liveUrl} onChange={update('liveUrl')} className={inputClass} />}
            </Field>
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button type="button" onClick={() => setDraft(null)} className={secondaryButton}>
              Back
            </button>
            <button type="submit" disabled={busy || !draft.title.trim()} className={primaryButton}>
              {busy && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
              Save project
            </button>
          </div>
        </form>
      )}

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
    </section>
  )
}
