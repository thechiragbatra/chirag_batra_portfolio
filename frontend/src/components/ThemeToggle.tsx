import { Moon, Sun } from 'lucide-react'
import { useState, type MouseEvent } from 'react'

function readTheme(): boolean {
  return document.documentElement.classList.contains('dark')
}

export function ThemeToggle() {
  const [dark, setDark] = useState(readTheme)

  const toggle = (event: MouseEvent<HTMLButtonElement>) => {
    const next = !dark
    const root = document.documentElement
    const apply = () => {
      root.classList.toggle('dark', next)
      setDark(next)
    }
    // The new theme irises out from the button where the View Transitions API exists.
    const doc = document as Document & {
      startViewTransition?: (cb: () => void) => { finished: Promise<void> }
    }
    if (doc.startViewTransition && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      const rect = event.currentTarget.getBoundingClientRect()
      root.style.setProperty('--vt-x', `${rect.left + rect.width / 2}px`)
      root.style.setProperty('--vt-y', `${rect.top + rect.height / 2}px`)
      root.dataset.vt = 'theme'
      doc.startViewTransition(apply).finished.finally(() => {
        root.dataset.vt = 'route'
      })
    } else {
      apply()
    }
    try {
      localStorage.setItem('theme', next ? 'dark' : 'light')
    } catch {
      // Storage blocked (private mode): the choice lasts for this page view only.
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="group relative grid size-9 place-items-center overflow-hidden rounded-xl text-zinc-600 transition-colors hover:bg-zinc-900/5 hover:text-zinc-900 focus-visible:outline-2 focus-visible:outline-emerald-500 dark:text-zinc-300 dark:hover:bg-white/10 dark:hover:text-white"
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
    >
      <span key={String(dark)} className="animate-pop">
        {dark ? (
          <Sun className="size-[18px] transition-transform duration-700 group-hover:rotate-180" />
        ) : (
          <Moon className="size-[18px] transition-transform duration-500 group-hover:-rotate-12" />
        )}
      </span>
    </button>
  )
}
