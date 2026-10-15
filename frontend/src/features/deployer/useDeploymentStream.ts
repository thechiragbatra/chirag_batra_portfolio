import { useCallback, useEffect, useReducer, useRef } from 'react'
import { createDeployment, deploymentEventsUrl } from '../../lib/api'
import {
  AGENT_NAMES,
  type AgentName,
  type AgentStatus,
  type DeploymentEvent,
  type DeploymentState,
  type LogLevel,
} from '../../types/events'

export type Phase = 'idle' | 'starting' | 'streaming' | 'succeeded' | 'failed'

export interface LogLine {
  id: number
  timestamp: string
  agent: AgentName | null
  level: LogLevel
  message: string
}

export interface StreamState {
  phase: Phase
  deploymentId: string | null
  agents: Record<AgentName, AgentStatus>
  repairAttempts: number
  logs: LogLine[]
  result: DeploymentState | null
  error: string | null
}

type Action =
  | { type: 'start' }
  | { type: 'created'; id: string; repoUrl: string }
  | { type: 'event'; event: DeploymentEvent }
  | { type: 'fail'; message: string }

const idleAgents = () =>
  Object.fromEntries(AGENT_NAMES.map((name) => [name, 'idle'])) as Record<AgentName, AgentStatus>

const initialState: StreamState = {
  phase: 'idle',
  deploymentId: null,
  agents: idleAgents(),
  repairAttempts: 0,
  logs: [],
  result: null,
  error: null,
}

function appendLog(state: StreamState, line: Omit<LogLine, 'id'>): LogLine[] {
  return [...state.logs, { ...line, id: state.logs.length }]
}

function reducer(state: StreamState, action: Action): StreamState {
  switch (action.type) {
    case 'start':
      return { ...initialState, agents: idleAgents(), phase: 'starting' }
    case 'created':
      return {
        ...state,
        phase: 'streaming',
        deploymentId: action.id,
        logs: appendLog(state, {
          timestamp: new Date().toISOString(),
          agent: null,
          level: 'info',
          message: `Deployment ${action.id.slice(0, 8)} queued for ${action.repoUrl}`,
        }),
      }
    case 'fail':
      return {
        ...state,
        phase: 'failed',
        error: action.message,
        logs: appendLog(state, {
          timestamp: new Date().toISOString(),
          agent: null,
          level: 'error',
          message: action.message,
        }),
      }
    case 'event': {
      const event = action.event
      switch (event.type) {
        case 'status':
          return {
            ...state,
            agents: { ...state.agents, [event.agent]: event.status },
            repairAttempts: event.repair_attempts,
          }
        case 'log':
          return { ...state, logs: appendLog(state, event) }
        case 'done':
          return {
            ...state,
            phase: event.success ? 'succeeded' : 'failed',
            agents: event.state.agent_status,
            repairAttempts: event.state.repair_attempts,
            result: event.state,
            error: event.success ? null : (event.state.errors.at(-1) ?? 'Deployment failed'),
          }
        case 'error':
          return reducer(state, { type: 'fail', message: event.message })
      }
    }
  }
}

/** Starts a deployment and follows its SSE event stream. */
export function useDeploymentStream() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const sourceRef = useRef<EventSource | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const stop = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    sourceRef.current?.close()
    sourceRef.current = null
  }, [])

  useEffect(() => stop, [stop])

  /** Follow a run's event stream (one this page created, or one started elsewhere). */
  const follow = useCallback(
    (id: string) => {
      const source = new EventSource(deploymentEventsUrl(id))
      sourceRef.current = source
      source.onmessage = (message: MessageEvent<string>) => {
        const event = JSON.parse(message.data) as DeploymentEvent
        dispatch({ type: 'event', event })
        if (event.type === 'done' || event.type === 'error') stop()
      }
      source.onerror = () => {
        // While CONNECTING the browser retries on its own (resuming via Last-Event-ID).
        if (source.readyState === EventSource.CLOSED) {
          stop()
          dispatch({ type: 'fail', message: 'Lost connection to the deployment stream.' })
        }
      }
    },
    [stop],
  )

  /** Watch a run that was already started, e.g. by the AI guide. */
  const attach = useCallback(
    (id: string, repoUrl: string) => {
      stop()
      dispatch({ type: 'start' })
      dispatch({ type: 'created', id, repoUrl })
      follow(id)
    },
    [stop, follow],
  )

  const start = useCallback(
    async (repoUrl: string) => {
      stop()
      const abort = new AbortController()
      abortRef.current = abort
      dispatch({ type: 'start' })

      let id: string
      try {
        const created = await createDeployment(repoUrl, abort.signal)
        id = created.id
        dispatch({ type: 'created', id, repoUrl: created.repo_url })
      } catch (error) {
        if (abort.signal.aborted) return
        dispatch({ type: 'fail', message: error instanceof Error ? error.message : String(error) })
        return
      }
      if (abort.signal.aborted) return
      follow(id)
    },
    [stop, follow],
  )

  const isBusy = state.phase === 'starting' || state.phase === 'streaming'
  return { ...state, isBusy, start, attach }
}
