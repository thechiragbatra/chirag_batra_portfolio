import { useId, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'

export interface TabItem {
  id: string
  label: string
  content: ReactNode
}

/** Accessible tabs (WAI-ARIA pattern) with a sliding gradient indicator. */
export function Tabs({ items, label }: { items: TabItem[]; label: string }) {
  const [active, setActive] = useState(0)
  // Which way the panel should slide in: the direction the tabs moved.
  const [direction, setDirection] = useState<'left' | 'right' | null>(null)
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([])
  const [indicator, setIndicator] = useState<{ left: number; width: number } | null>(null)
  const baseId = useId()

  useLayoutEffect(() => {
    const measure = () => {
      const el = tabRefs.current[active]
      if (el) setIndicator({ left: el.offsetLeft, width: el.offsetWidth })
    }
    measure()
    window.addEventListener('resize', measure)
    document.fonts?.ready.then(measure).catch(() => {})
    return () => window.removeEventListener('resize', measure)
  }, [active])

  const select = (next: number) => {
    if (next === active) return
    setDirection(next > active ? 'right' : 'left')
    setActive(next)
  }

  const focusTab = (index: number) => {
    const next = (index + items.length) % items.length
    select(next)
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
      <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <div
          role="tablist"
          aria-label={label}
          onKeyDown={onKeyDown}
          className="glass relative inline-flex gap-1 rounded-2xl p-1"
        >
          {indicator && (
            <span
              aria-hidden
              className="absolute inset-y-1 rounded-xl bg-zinc-950 shadow-lg shadow-emerald-500/20 dark:bg-white"
              style={{
                left: indicator.left,
                width: indicator.width,
                transition:
                  'left var(--dur-spring-snappy) var(--spring-snappy), width var(--dur-spring-snappy) var(--spring-snappy)',
              }}
            />
          )}
          {items.map((item, index) => {
            const selected = index === active
            return (
              <button
                key={item.id}
                ref={(el) => {
                  tabRefs.current[index] = el
                }}
                id={`${baseId}-tab-${item.id}`}
                data-guide={item.id}
                role="tab"
                type="button"
                aria-selected={selected}
                aria-controls={`${baseId}-panel-${item.id}`}
                tabIndex={selected ? 0 : -1}
                onClick={() => select(index)}
                className={`relative shrink-0 rounded-xl px-4 py-2 text-sm font-medium transition-colors duration-300 ${
                  selected
                    ? 'text-white dark:text-zinc-950'
                    : 'text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white'
                }`}
              >
                {item.label}
              </button>
            )
          })}
        </div>
      </div>
      {items.map((item, index) => (
        <div
          key={item.id}
          id={`${baseId}-panel-${item.id}`}
          role="tabpanel"
          aria-labelledby={`${baseId}-tab-${item.id}`}
          hidden={index !== active}
          tabIndex={0}
          className="pt-8 focus-visible:outline-none"
        >
          {/* Remount on activation so the panel's entrance animations replay. */}
          {index === active && (
            <div
              className={
                direction === 'right' ? 'slide-from-right' : direction === 'left' ? 'slide-from-left' : 'animate-blur-in'
              }
            >
              {item.content}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
