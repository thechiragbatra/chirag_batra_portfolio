import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'

export interface TabItem {
  id: string
  label: string
  content: ReactNode
}

/** Accessible tabs (WAI-ARIA pattern): arrow keys, Home and End move between tabs. */
export function Tabs({ items, label }: { items: TabItem[]; label: string }) {
  const [active, setActive] = useState(0)
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([])
  const baseId = useId()

  const focusTab = (index: number) => {
    const next = (index + items.length) % items.length
    setActive(next)
    tabRefs.current[next]?.focus()
  }

  const onKeyDown = (event: KeyboardEvent) => {
    const moves: Record<string, number> = {
      ArrowRight: active + 1,
      ArrowLeft: active - 1,
      Home: 0,
      End: items.length - 1,
    }
    if (event.key in moves) {
      event.preventDefault()
      focusTab(moves[event.key])
    }
  }

  return (
    <div>
      <div
        role="tablist"
        aria-label={label}
        onKeyDown={onKeyDown}
        className="-mx-4 flex gap-1 overflow-x-auto overflow-y-hidden px-4 shadow-[inset_0_-1px_0_var(--color-zinc-200)] sm:mx-0 sm:px-0 dark:shadow-[inset_0_-1px_0_var(--color-zinc-800)]"
      >
        {items.map((item, index) => {
          const selected = index === active
          return (
            <button
              key={item.id}
              ref={(el) => {
                tabRefs.current[index] = el
              }}
              id={`${baseId}-tab-${item.id}`}
              role="tab"
              type="button"
              aria-selected={selected}
              aria-controls={`${baseId}-panel-${item.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => setActive(index)}
              className={`shrink-0 border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
                selected
                  ? 'border-emerald-600 text-zinc-900 dark:text-zinc-50'
                  : 'border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200'
              }`}
            >
              {item.label}
            </button>
          )
        })}
      </div>
      {items.map((item, index) => (
        <div
          key={item.id}
          id={`${baseId}-panel-${item.id}`}
          role="tabpanel"
          aria-labelledby={`${baseId}-tab-${item.id}`}
          hidden={index !== active}
          tabIndex={0}
          className="pt-6 focus-visible:outline-none"
        >
          {item.content}
        </div>
      ))}
    </div>
  )
}
