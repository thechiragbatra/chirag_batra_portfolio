import type { ReactNode, Ref } from 'react'

export function PageHeader({
  eyebrow,
  title,
  children,
  titleRef,
}: {
  eyebrow?: string
  title: ReactNode
  children?: ReactNode
  /** Lets a page move focus to its heading (e.g. after deleting the focused item). */
  titleRef?: Ref<HTMLHeadingElement>
}) {
  return (
    <div className="mb-10">
      {eyebrow && (
        <p className="mb-3 font-mono text-xs tracking-[0.2em] text-emerald-600 uppercase dark:text-emerald-400">
          {eyebrow}
        </p>
      )}
      <h1 ref={titleRef} tabIndex={titleRef ? -1 : undefined} className="font-display text-4xl font-bold outline-none sm:text-5xl">
        {title}
      </h1>
      {children && (
        <p className="mt-3 max-w-2xl text-base leading-relaxed text-zinc-600 dark:text-zinc-400">
          {children}
        </p>
      )}
    </div>
  )
}
