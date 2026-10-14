import { useEffect, useState } from 'react'
import { useInView } from '../../hooks/useInView'
import { useReducedMotion } from '../../hooks/useMediaQuery'

interface Props {
  value: number
  decimals?: number
  prefix?: string
  suffix?: string
  duration?: number
}

const format = (n: number, decimals: number) =>
  n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })

/** Counts from 0 to `value` with an ease-out curve once visible. */
export function CountUp({ value, decimals = 0, prefix = '', suffix = '', duration = 1600 }: Props) {
  const [ref, inView] = useInView<HTMLSpanElement>()
  const reduced = useReducedMotion()
  const [current, setCurrent] = useState(0)

  useEffect(() => {
    if (!inView || reduced) return
    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      setCurrent(value * (1 - Math.pow(1 - t, 4)))
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [inView, reduced, value, duration])

  const shown = reduced ? value : current
  return (
    <span ref={ref} className="tabular-nums">
      <span className="sr-only">
        {prefix}
        {format(value, decimals)}
        {suffix}
      </span>
      <span aria-hidden>
        {prefix}
        {format(shown, decimals)}
        {suffix}
      </span>
    </span>
  )
}
