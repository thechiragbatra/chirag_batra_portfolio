import type { ReactNode } from 'react'

export function PageHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string
  title: ReactNode
  children?: ReactNode
}) {
  return (
    <div className="mb-10">
      {eyebrow && (
        <p className="mb-3 font-mono text-xs tracking-[0.2em] text-emerald-600 uppercase dark:text-emerald-400">
          {eyebrow}
        </p>
      )}
      <h1 className="font-display text-4xl font-bold sm:text-5xl">{title}</h1>
      {children && (
        <p className="mt-3 max-w-2xl text-base leading-relaxed text-zinc-600 dark:text-zinc-400">
          {children}
        </p>
      )}
    </div>
  )
}
