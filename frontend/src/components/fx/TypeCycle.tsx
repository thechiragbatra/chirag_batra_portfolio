import { useEffect, useState } from 'react'
import { useReducedMotion } from '../../hooks/useMediaQuery'

/** Types each phrase, pauses, deletes it, and moves to the next. */
export function TypeCycle({ phrases, className }: { phrases: string[]; className?: string }) {
  const reduced = useReducedMotion()
  const [index, setIndex] = useState(0)
  const [length, setLength] = useState(0)
  const [deleting, setDeleting] = useState(false)
  const phrase = phrases[index % phrases.length]

  useEffect(() => {
    if (reduced) return
    const done = !deleting && length === phrase.length
    const empty = deleting && length === 0
    const delay = done ? 1600 : empty ? 250 : deleting ? 28 : 55
    const timer = setTimeout(() => {
      if (done) setDeleting(true)
      else if (empty) {
        setDeleting(false)
        setIndex((i) => i + 1)
      } else setLength((n) => n + (deleting ? -1 : 1))
    }, delay)
    return () => clearTimeout(timer)
  }, [length, deleting, phrase, reduced])

  return (
    <span className={className}>
      <span className="sr-only">{phrases.join(', ')}</span>
      <span aria-hidden>
        {reduced ? phrases[0] : phrase.slice(0, length)}
        <span className="animate-blink ml-0.5 inline-block w-[0.08em] translate-y-[0.1em] self-stretch bg-current">&nbsp;</span>
      </span>
    </span>
  )
}
