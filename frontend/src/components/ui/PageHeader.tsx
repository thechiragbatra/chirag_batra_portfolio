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
    <div className="mb-12 pt-4">
      {eyebrow && <p className="eyebrow mb-4">{eyebrow}</p>}
      <h1
        ref={titleRef}
        tabIndex={titleRef ? -1 : undefined}
        className="font-display text-[clamp(2.4rem,6vw,5.2rem)] leading-[0.95] font-extrabold text-white outline-none"
      >
        {title}
      </h1>
      {children && <p className="mt-5 max-w-2xl text-lg leading-relaxed text-zinc-400">{children}</p>}
    </div>
  )
}
