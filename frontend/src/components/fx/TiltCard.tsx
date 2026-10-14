import { useRef, type PointerEvent, type ReactNode } from 'react'
import { useFinePointer, useReducedMotion } from '../../hooks/useMediaQuery'

interface Props {
  children: ReactNode
  className?: string
  max?: number
}

/**
 * 3D tilt toward the cursor with a moving glare and spotlight. Falls back to a
 * flat card on touch screens or with reduced motion.
 */
export function TiltCard({ children, className = '', max = 9 }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const fine = useFinePointer()
  const reduced = useReducedMotion()
  const enabled = fine && !reduced

  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    const el = ref.current
    if (!el || !enabled) return
    const rect = el.getBoundingClientRect()
    const px = (e.clientX - rect.left) / rect.width
    const py = (e.clientY - rect.top) / rect.height
    el.style.setProperty('--rx', `${(0.5 - py) * max}deg`)
    el.style.setProperty('--ry', `${(px - 0.5) * max}deg`)
    el.style.setProperty('--mx', `${px * 100}%`)
    el.style.setProperty('--my', `${py * 100}%`)
  }

  const onLeave = () => {
    const el = ref.current
    if (!el) return
    el.style.setProperty('--rx', '0deg')
    el.style.setProperty('--ry', '0deg')
  }

  return (
    <div style={{ perspective: '1000px' }} className="h-full">
      <div
        ref={ref}
        onPointerMove={onMove}
        onPointerLeave={onLeave}
        className={`group/tilt glow-border relative h-full rounded-2xl transition-transform duration-300 ease-out will-change-transform ${className}`}
        style={{
          transform: enabled ? 'rotateX(var(--rx, 0deg)) rotateY(var(--ry, 0deg))' : undefined,
          transformStyle: 'preserve-3d',
        }}
      >
        {children}
        {enabled && (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 z-[2] rounded-[inherit] opacity-0 transition-opacity duration-300 group-hover/tilt:opacity-100"
            style={{
              background:
                'radial-gradient(420px circle at var(--mx, 50%) var(--my, 50%), rgb(255 255 255 / 0.14), transparent 45%)',
            }}
          />
        )}
      </div>
    </div>
  )
}
