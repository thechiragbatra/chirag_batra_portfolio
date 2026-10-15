// Colors shared by the Churn Lab charts and page.

import type { Segment } from './churnLab'

export const SEGMENT_TINT: Record<Segment, string> = {
  persuadable: '#10b981',
  sure_thing: '#0ea5e9',
  lost_cause: '#f59e0b',
  sleeping_dog: '#f43f5e',
}

export const segmentColor = (s: Segment) => SEGMENT_TINT[s]

export type Strategy = 'uplift' | 'risk' | 'random' | 'oracle'

export const STRATEGIES: { key: Strategy; label: string; color: string; dash?: string }[] = [
  { key: 'oracle', label: 'Perfect knowledge', color: '#a1a1aa', dash: '4 4' },
  { key: 'uplift', label: 'Target by uplift', color: '#10b981' },
  { key: 'risk', label: 'Target by churn risk', color: '#f59e0b' },
  { key: 'random', label: 'Random', color: '#71717a', dash: '1 4' },
]

