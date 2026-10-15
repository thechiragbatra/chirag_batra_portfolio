import type { App, AppsResponse } from '../types/apps'
import type { CreateDeploymentResponse } from '../types/events'

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '')

/** Required by the backend on every write (it blocks cross-site requests without it). */
const CSRF = { 'X-DeploySmith': '1' }

interface ValidationIssue {
  msg: string
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body: { detail?: string | ValidationIssue[] } = await response.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail) && body.detail.length > 0) {
      return body.detail.map((issue) => issue.msg.replace(/^Value error, /, '')).join('; ')
    }
  } catch {
    // Non-JSON error body; fall through to the status line.
  }
  return `Request failed (${response.status} ${response.statusText})`
}

export async function createDeployment(
  repoUrl: string,
  signal?: AbortSignal,
): Promise<CreateDeploymentResponse> {
  let response: Response
  try {
    response = await fetch(`${API_URL}/api/deployments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...CSRF },
      body: JSON.stringify({ repo_url: repoUrl }),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new Error(`Cannot reach the API at ${API_URL}. Is the backend running?`, { cause: error })
  }
  if (!response.ok) throw new Error(await errorMessage(response))
  return (await response.json()) as CreateDeploymentResponse
}

export function deploymentEventsUrl(id: string): string {
  return `${API_URL}/api/deployments/${encodeURIComponent(id)}/events`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    const method = init?.method ?? 'GET'
    const headers = method === 'GET' ? init?.headers : { ...CSRF, ...init?.headers }
    response = await fetch(`${API_URL}${path}`, { ...init, headers })
  } catch (error) {
    throw new Error(`Cannot reach the API at ${API_URL}. Is the backend running?`, { cause: error })
  }
  if (!response.ok) throw new Error(await errorMessage(response))
  if (response.status === 204) return undefined as T
  const text = await response.text()
  return (response.headers.get('content-type')?.includes('application/json') ? JSON.parse(text) : text) as T
}

const appPath = (name: string) => `/api/apps/${encodeURIComponent(name)}`

export const listApps = () => request<AppsResponse>('/api/apps')

export const getDeployLog = (name: string, deployId: string) =>
  request<string>(`${appPath(name)}/deploys/${encodeURIComponent(deployId)}/log`)

export const rollbackApp = (name: string, deployId: string) =>
  request<App>(`${appPath(name)}/rollback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ deploy_id: deployId }),
  })

export const stopApp = (name: string) => request<void>(`${appPath(name)}/stop`, { method: 'POST' })

export const deleteApp = (name: string) => request<void>(appPath(name), { method: 'DELETE' })
