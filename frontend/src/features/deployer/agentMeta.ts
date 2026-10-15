import { Compass, HeartPulse, Rocket, ScanSearch, type LucideIcon } from 'lucide-react'
import type { AgentName } from '../../types/events'

export const AGENT_META: Record<AgentName, { icon: LucideIcon; description: string; text: string }> = {
  profiler: { icon: ScanSearch, description: 'Clones and analyzes the repo statically', text: 'text-emerald-400' },
  strategist: { icon: Compass, description: 'Picks a free-tier platform per component', text: 'text-cyan-400' },
  provisioner: { icon: Rocket, description: 'Creates resources and deploys', text: 'text-violet-400' },
  healer: { icon: HeartPulse, description: 'Health-checks and requests repairs', text: 'text-pink-400' },
}
