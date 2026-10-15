// Client for the dev-only project editor served by plugins/projectEditor.ts.
import type { Project } from '../../types/content'

const BASE = '/__dev/projects'

async function request<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init)
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status})`)
  }
  return body as T
}

export function previewProject(repoUrl: string): Promise<Project> {
  return request(`${BASE}/preview?repo=${encodeURIComponent(repoUrl.trim())}`)
}

export function saveProject(project: Project): Promise<Project> {
  return request(`${BASE}/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(project),
  })
}
