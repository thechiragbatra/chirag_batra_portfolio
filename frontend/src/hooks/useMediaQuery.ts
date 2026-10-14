import { useMemo, useSyncExternalStore } from 'react'

function subscribeTo(query: string) {
  return (onChange: () => void) => {
    const list = window.matchMedia(query)
    list.addEventListener('change', onChange)
    return () => list.removeEventListener('change', onChange)
  }
}

export function useMediaQuery(query: string): boolean {
  const subscribe = useMemo(() => subscribeTo(query), [query])
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => false,
  )
}

/** True when the user asked the OS to minimize motion. Every effect checks this. */
export const useReducedMotion = () => useMediaQuery('(prefers-reduced-motion: reduce)')

/** True for a mouse or trackpad (not touch), where hover effects make sense. */
export const useFinePointer = () => useMediaQuery('(hover: hover) and (pointer: fine)')

export function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}
