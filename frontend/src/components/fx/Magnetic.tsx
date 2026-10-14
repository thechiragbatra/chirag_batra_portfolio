import { useRef, type PointerEvent, type ReactNode } from 'react'
import { useFinePointer, useReducedMotion } from '../../hooks/useMediaQuery'

/** Wrapper that pulls its child toward the cursor while hovered. */
export function Magnetic({ children, strength = 0.3 }: { children: ReactNode; strength?: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  const fine = useFinePointer()
  const reduced = useReducedMotion()

  const onMove = (e: PointerEvent<HTMLSpanElement>) => {
    const el = ref.current
    if (!el || !fine || reduced) return
    const rect = el.getBoundingClientRect()
    const x = (e.clientX - rect.left - rect.width / 2) * strength
    const y = (e.clientY - rect.top - rect.height / 2) * strength
    el.style.transform = `translate(${x}px, ${y}px)`
  }

  const reset = () => {
    if (ref.current) ref.current.style.transform = ''
  }

  return (
    <span
      ref={ref}
      onPointerMove={onMove}
      onPointerLeave={reset}
      className="inline-flex transition-transform duration-300 ease-out"
    >
      {children}
    </span>
  )
}
