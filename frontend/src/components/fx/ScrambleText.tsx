import { useEffect, useState } from 'react'
import { useReducedMotion } from '../../hooks/useMediaQuery'

const GLYPHS = '!<>-_\\/[]{}—=+*^?#01ABCDEFX'

/** Decodes `text` from random glyphs, left to right. Screen readers get the final text. */
export function ScrambleText({ text, duration = 1200, className }: { text: string; duration?: number; className?: string }) {
  const reduced = useReducedMotion()
  const [scrambled, setScrambled] = useState('')

  useEffect(() => {
    if (reduced) return
    let frame = 0
    const start = performance.now()
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration)
      const settled = Math.floor(progress * text.length)
      let out = text.slice(0, settled)
      for (let i = settled; i < text.length; i++) {
        out += text[i] === ' ' ? ' ' : GLYPHS[Math.floor(Math.random() * GLYPHS.length)]
      }
      setScrambled(out)
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [text, duration, reduced])

  return (
    <span className={className}>
      <span className="sr-only">{text}</span>
      <span aria-hidden>{reduced ? text : scrambled || '\u00a0'}</span>
    </span>
  )
}
