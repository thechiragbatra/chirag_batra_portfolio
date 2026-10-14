// Dev-only editor for src/data/projects.json. Runs inside `vite dev` (apply: 'serve'),
// so it never exists in a production build and site visitors cannot reach it.
//
//   GET  /__dev/projects/preview?repo=<github url>  -> Project built from the GitHub API
//   POST /__dev/projects  (Project JSON)             -> appended to projects.json
import { readFile, writeFile } from 'node:fs/promises'
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Plugin } from 'vite'
import { parseGithubRepoUrl } from '../src/lib/githubUrl.ts'
import type { Project } from '../src/types/content.ts'

export const PROJECT_EDITOR_BASE = '/__dev/projects'

class HttpError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

interface GithubRepo {
  name: string
  html_url: string
  description: string | null
  homepage: string | null
  topics?: string[]
  language: string | null
}

/** "customer-churn_uplift" -> "Customer Churn Uplift" */
export function humanizeRepoName(name: string): string {
  return name
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(' ')
}

export function repoToProject(repo: GithubRepo): Project {
  const tags = repo.topics?.length ? repo.topics.slice(0, 6) : repo.language ? [repo.language] : []
  const project: Project = {
    title: humanizeRepoName(repo.name),
    description: repo.description?.trim() ?? '',
    tags,
    githubUrl: repo.html_url,
  }
  if (repo.homepage?.trim()) project.liveUrl = repo.homepage.trim()
  return project
}

async function fetchRepo(url: string, token: string | undefined): Promise<GithubRepo> {
  const ref = parseGithubRepoUrl(url)
  if (!ref) throw new HttpError(400, 'Enter a GitHub repository URL like https://github.com/owner/repo')

  const headers: Record<string, string> = {
    Accept: 'application/vnd.github+json',
    'User-Agent': 'deploysmith-dev',
    'X-GitHub-Api-Version': '2022-11-28',
  }
  if (token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(`https://api.github.com/repos/${ref.owner}/${ref.repo}`, { headers })
  if (response.status === 404) throw new HttpError(404, 'Repository not found (or it is private).')
  if (response.status === 403 || response.status === 429) {
    throw new HttpError(429, 'GitHub API rate limit reached. Set GITHUB_TOKEN in .env to raise it.')
  }
  if (!response.ok) throw new HttpError(502, `GitHub API returned ${response.status}.`)
  return (await response.json()) as GithubRepo
}

function isHttpsUrl(value: unknown): value is string {
  if (typeof value !== 'string') return false
  try {
    return new URL(value).protocol === 'https:'
  } catch {
    return false
  }
}

/** Validate an untrusted body and keep only known fields. */
export function validateProject(body: unknown): Project {
  if (typeof body !== 'object' || body === null) throw new HttpError(400, 'Expected a JSON object.')
  const b = body as Record<string, unknown>

  const title = typeof b.title === 'string' ? b.title.trim() : ''
  if (!title) throw new HttpError(400, 'Title is required.')
  if (typeof b.description !== 'string') throw new HttpError(400, 'Description must be text.')
  if (!Array.isArray(b.tags) || !b.tags.every((t) => typeof t === 'string')) {
    throw new HttpError(400, 'Tags must be a list of strings.')
  }
  const ref = typeof b.githubUrl === 'string' ? parseGithubRepoUrl(b.githubUrl) : null
  if (!ref) throw new HttpError(400, 'githubUrl must be a GitHub repository URL.')
  if (b.liveUrl !== undefined && b.liveUrl !== '' && !isHttpsUrl(b.liveUrl)) {
    throw new HttpError(400, 'Live URL must start with https://')
  }

  const project: Project = {
    title,
    description: b.description.trim(),
    tags: [...new Set(b.tags.map((t) => t.trim()).filter(Boolean))],
    githubUrl: `https://github.com/${ref.owner}/${ref.repo}`,
  }
  if (typeof b.liveUrl === 'string' && b.liveUrl) project.liveUrl = b.liveUrl
  return project
}

async function readBody(req: IncomingMessage, limit = 64 * 1024): Promise<unknown> {
  let size = 0
  const chunks: Buffer[] = []
  for await (const chunk of req) {
    size += chunk.length
    if (size > limit) throw new HttpError(413, 'Request body too large.')
    chunks.push(chunk as Buffer)
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8'))
  } catch {
    throw new HttpError(400, 'Invalid JSON.')
  }
}

function send(res: ServerResponse, status: number, body: unknown): void {
  res.statusCode = status
  res.setHeader('Content-Type', 'application/json')
  res.end(JSON.stringify(body))
}

const sameRepo = (a: string, b: string) => a.toLowerCase().replace(/\/$/, '') === b.toLowerCase().replace(/\/$/, '')

export function projectEditor(options: { dataFile: string; githubToken?: string }): Plugin {
  return {
    name: 'deploysmith:project-editor',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use(PROJECT_EDITOR_BASE, (req, res) => {
        void (async () => {
          try {
            const url = new URL(req.url ?? '/', 'http://localhost')
            if (req.method === 'GET' && url.pathname === '/preview') {
              const repo = await fetchRepo(url.searchParams.get('repo') ?? '', options.githubToken)
              send(res, 200, repoToProject(repo))
            } else if (req.method === 'POST' && url.pathname === '/') {
              const project = validateProject(await readBody(req))
              const projects = JSON.parse(await readFile(options.dataFile, 'utf8')) as Project[]
              if (projects.some((p) => sameRepo(p.githubUrl, project.githubUrl))) {
                throw new HttpError(409, 'That repository is already in projects.json.')
              }
              projects.push(project)
              await writeFile(options.dataFile, `${JSON.stringify(projects, null, 2)}\n`)
              send(res, 201, project)
            } else {
              throw new HttpError(404, 'Not found.')
            }
          } catch (error) {
            const status = error instanceof HttpError ? error.status : 500
            const message = error instanceof Error ? error.message : 'Unexpected error.'
            if (status === 500) server.config.logger.error(`[project-editor] ${message}`)
            send(res, status, { detail: message })
          }
        })()
      })
    },
  }
}
