// Client for Smith, the portfolio guide agent (backend/guide_api.py): status, and a
// streamed chat whose server-sent events arrive over a POST (EventSource cannot POST).

import { API_URL } from './api'
import { parseSse } from './sse'

export type GuideAction =
  | { type: 'navigate'; path: string; section: string | null }
  | { type: 'set_customer'; values: Record<string, string | number> }

export type GuideEvent =
  | { type: 'step'; id: string; tool: string; args: Record<string, unknown> }
  | { type: 'step_done'; id: string; tool: string; ok: boolean; summary: string }
  | { type: 'source'; id: string; doc: string; title: string; page: string; section: string | null; url: string | null }
  | { type: 'action'; action: GuideAction }
  | { type: 'token'; text: string }
  | { type: 'reset_text' }
  | { type: 'done' }
  | { type: 'error'; message: string }

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

export async function guideStatus(signal?: AbortSignal): Promise<{ enabled: boolean; model: string | null }> {
  const response = await fetch(`${API_URL}/api/guide`, { signal })
  if (!response.ok) throw new Error(`guide status ${response.status}`)
  return response.json()
}

async function failure(response: Response): Promise<string> {
  try {
    const body: { detail?: unknown } = await response.json()
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // not JSON
  }
  return `Smith is unavailable (${response.status})`
}

export async function askGuide(
  messages: ChatTurn[],
  page: string,
  onEvent: (event: GuideEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${API_URL}/api/guide/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-DeploySmith': '1' },
      body: JSON.stringify({ messages, page }),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new Error('Cannot reach Smith right now.', { cause: error })
  }
  if (!response.ok || !response.body) throw new Error(await failure(response))

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    const parsed = parseSse<GuideEvent>(buffer + value)
    buffer = parsed.rest
    parsed.events.forEach(onEvent)
  }
}

// ---- Hand-offs from the guide to pages (the Lab picks up a customer it was sent) ----

type Customer = Record<string, string | number>
let pendingCustomer: Customer | null = null
const customerListeners = new Set<() => void>()

export function sendCustomerToLab(values: Customer) {
  pendingCustomer = values
  customerListeners.forEach((listener) => listener())
}

/** Returns the customer waiting for the Lab, once. */
export function takeLabCustomer(): Customer | null {
  const values = pendingCustomer
  pendingCustomer = null
  return values
}

export function onLabCustomer(listener: () => void): () => void {
  customerListeners.add(listener)
  return () => customerListeners.delete(listener)
}
