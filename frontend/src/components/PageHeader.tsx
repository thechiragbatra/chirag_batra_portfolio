import type { ReactNode } from 'react'

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-8">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
      {children && <p className="mt-2 max-w-2xl text-zinc-600 dark:text-zinc-400">{children}</p>}
    </div>
  )
}
