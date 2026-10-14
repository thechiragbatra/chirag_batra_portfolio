// Mirror of shared/schemas/{state,event}.schema.json — update by hand when they change.
// Every field is always present on the wire; nullable values are `T | null`.

export const AGENT_NAMES = ['profiler', 'strategist', 'provisioner', 'healer'] as const
export type AgentName = (typeof AGENT_NAMES)[number]

export type AgentStatus = 'idle' | 'running' | 'done' | 'failed'
export type LogLevel = 'info' | 'warn' | 'error' | 'success'
export type Platform =
  | 'vercel'
  | 'netlify'
  | 'cloudflare_pages'
  | 'render'
  | 'hf_spaces'
  | 'neon'
  | 'supabase'
  | 'turso'
  | 'sandbox'

export const MAX_REPAIR_ATTEMPTS = 3

export interface Component {
  name: string
  kind: 'frontend' | 'backend' | 'database'
  path: string
  framework: string | null
  build_command: string | null
  start_command: string | null
  port: number | null
}

export interface RepoProfile {
  name: string
  default_branch: string
  languages: string[]
  frameworks: string[]
  components: Component[]
  env_vars: string[]
}

export interface DeploymentTarget {
  component: string
  platform: Platform
  reason: string
  env_vars: string[]
}

export interface DeploymentPlan {
  targets: DeploymentTarget[]
  notes: string[]
}

export interface DeploymentResult {
  component: string
  platform: Platform
  status: 'live' | 'failed'
  url: string | null
  attempt: number
}

export interface HealthCheck {
  component: string
  url: string | null
  ok: boolean
  status_code: number | null
  latency_ms: number | null
  detail: string
}

export interface HealthReport {
  healthy: boolean
  checks: HealthCheck[]
  diagnosis: string | null
}

export interface DeploymentState {
  repo_url: string
  repo_profile: RepoProfile | null
  deployment_plan: DeploymentPlan | null
  deployment_results: DeploymentResult[]
  health_report: HealthReport | null
  errors: string[]
  repair_attempts: number
  agent_status: Record<AgentName, AgentStatus>
}

interface BaseEvent {
  timestamp: string
}

export interface StatusEvent extends BaseEvent {
  type: 'status'
  agent: AgentName
  status: AgentStatus
  repair_attempts: number
}

export interface LogEvent extends BaseEvent {
  type: 'log'
  agent: AgentName | null
  level: LogLevel
  message: string
}

export interface DoneEvent extends BaseEvent {
  type: 'done'
  success: boolean
  state: DeploymentState
}

export interface ErrorEvent extends BaseEvent {
  type: 'error'
  message: string
}

export type DeploymentEvent = StatusEvent | LogEvent | DoneEvent | ErrorEvent

/** Response of POST /api/deployments (not part of the event stream). */
export interface CreateDeploymentResponse {
  id: string
  repo_url: string
}
