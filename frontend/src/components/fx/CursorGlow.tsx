import { useEffect, useRef } from 'react'
import { useFinePointer, useReducedMotion } from '../../hooks/useMediaQuery'

/** A soft light that trails the mouse. Desktop only; off with reduced motion. */
export function CursorGlow() {
  const ref = useRef<HTMLDivElement>(null)
  const fine = useFinePointer()
  const reduced = useReducedMotion()
  const enabled = fine && !reduced

  useEffect(() => {
    if (!enabled) return
    const el = ref.current
    if (!el) return
    const target = { x: innerWidth / 2, y: innerHeight / 3 }
    const pos = { ...target }
    let frame = 0
    const onMove = (e: PointerEvent) => {
      target.x = e.clientX
      target.y = e.clientY
    }
    const loop = () => {
      pos.x += (target.x - pos.x) * 0.12
      pos.y += (target.y - pos.y) * 0.12
      el.style.transform = `translate3d(${pos.x - 300}px, ${pos.y - 300}px, 0)`
      frame = requestAnimationFrame(loop)
    }
    window.addEventListener('pointermove', onMove, { passive: true })
    frame = requestAnimationFrame(loop)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('pointermove', onMove)
    }
  }, [enabled])

  if (!enabled) return null
  return (
    <div
      ref={ref}
      aria-hidden
      className="pointer-events-none fixed top-0 left-0 -z-[5] size-[600px] rounded-full opacity-60 mix-blend-soft-light dark:opacity-40 dark:mix-blend-screen"
      style={{
        background:
          'radial-gradient(circle, color-mix(in oklab, var(--glow-b) 40%, transparent), transparent 65%)',
      }}
    />
  )
}
