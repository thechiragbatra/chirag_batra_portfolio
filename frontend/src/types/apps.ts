// Mirror of backend/app/routers/apps.py response models — update by hand when they change.
import type { Component } from './events'

export type DeployStatus = 'building' | 'ready' | 'failed'
export type AppMode = 'static' | 'server'

export interface Deployment {
  id: string
  created_at: string
  status: DeployStatus
  mode: AppMode
  component: Component
  error: string | null
}

export interface App {
  name: string
  repo_url: string
  component: string
  framework: string | null
  mode: AppMode
  current: string | null
  url: string | null
  /** Newest first. */
  deployments: Deployment[]
}

export interface AppsResponse {
  router_port: number
  /** SANDBOX_ENGINE is set on the backend (otherwise the Deployer only simulates). */
  engine_enabled: boolean
  /** The nginx router container is up, so *.localhost links can open. */
  router_running: boolean
  apps: App[]
}
