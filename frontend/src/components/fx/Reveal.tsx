import type { ElementType, ReactNode } from 'react'
import { useInView } from '../../hooks/useInView'

interface Props {
  children: ReactNode
  delay?: number
  className?: string
  as?: ElementType
  /** 'fade' lifts and unblurs; 'scan' wipes in top to bottom behind a glowing line. */
  variant?: 'fade' | 'scan'
}

/** Fades, unblurs and lifts its children the first time they scroll into view. */
export function Reveal({ children, delay = 0, className = '', as: Tag = 'div', variant = 'fade' }: Props) {
  const [ref, inView] = useInView<HTMLElement>()
  return (
    <Tag
      ref={ref}
      data-visible={inView || undefined}
      className={`${variant === 'scan' ? 'reveal-scan' : 'reveal'} ${className}`}
      style={{ transitionDelay: `${delay}ms`, animationDelay: `${delay}ms` }}
    >
      {children}
    </Tag>
  )
}
