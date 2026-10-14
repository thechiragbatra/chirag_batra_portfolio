import { Moon, Sun } from 'lucide-react'
import { useState } from 'react'

function readTheme(): boolean {
  return document.documentElement.classList.contains('dark')
}

export function ThemeToggle() {
  const [dark, setDark] = useState(readTheme)

  const toggle = () => {
    const next = !dark
    const apply = () => {
      document.documentElement.classList.toggle('dark', next)
      setDark(next)
    }
    // Cross-fade the whole page where the View Transitions API exists.
    const doc = document as Document & { startViewTransition?: (cb: () => void) => unknown }
    if (doc.startViewTransition && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      doc.startViewTransition(apply)
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
