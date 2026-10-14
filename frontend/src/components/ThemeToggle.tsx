import { Moon, Sun } from 'lucide-react'
import { useState } from 'react'

function readTheme(): boolean {
  return document.documentElement.classList.contains('dark')
}

export function ThemeToggle() {
  const [dark, setDark] = useState(readTheme)

  const toggle = () => {
    const next = !dark
    document.documentElement.classList.toggle('dark', next)
    try {
      localStorage.setItem('theme', next ? 'dark' : 'light')
    } catch {
      // Storage blocked (private mode): the choice lasts for this page view only.
    }
    setDark(next)
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="rounded-lg p-2 text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900 focus-visible:outline-2 focus-visible:outline-emerald-600 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
      aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
    >
      {dark ? <Sun className="size-5" /> : <Moon className="size-5" />}
    </button>
  )
}
