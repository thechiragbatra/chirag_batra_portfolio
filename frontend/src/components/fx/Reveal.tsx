import type { ElementType, ReactNode } from 'react'
import { useInView } from '../../hooks/useInView'

interface Props {
  children: ReactNode
  delay?: number
  className?: string
  as?: ElementType
}

/** Fades, unblurs and lifts its children the first time they scroll into view. */
export function Reveal({ children, delay = 0, className = '', as: Tag = 'div' }: Props) {
  const [ref, inView] = useInView<HTMLElement>()
  return (
    <Tag
      ref={ref}
      data-visible={inView || undefined}
      className={`reveal ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </Tag>
  )
}
