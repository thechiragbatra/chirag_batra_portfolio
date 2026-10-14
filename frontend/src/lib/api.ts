import type { CreateDeploymentResponse } from '../types/events'

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '')

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
      headers: { 'Content-Type': 'application/json' },
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
