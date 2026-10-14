import { useLayoutEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { Background } from './fx/Background'
import { CursorGlow } from './fx/CursorGlow'
import { Logo } from './Logo'
import { ThemeToggle } from './ThemeToggle'

const NAV = [
  { to: '/projects', label: 'Projects' },
  { to: '/resume', label: 'Resume' },
  { to: '/deployer', label: 'Deployer' },
  { to: '/apps', label: 'Apps' },
]

/** Pill that slides under the active nav link. */
function useNavIndicator(pathname: string) {
  const links = useRef<Record<string, HTMLAnchorElement | null>>({})
  const [style, setStyle] = useState<{ left: number; width: number } | null>(null)

  useLayoutEffect(() => {
    const measure = () => {
      const active = NAV.find((item) => pathname.startsWith(item.to))
      const el = active ? links.current[active.to] : null
      setStyle(el ? { left: el.offsetLeft, width: el.offsetWidth } : null)
    }
    measure()
    window.addEventListener('resize', measure)
    document.fonts?.ready.then(measure).catch(() => {})
    return () => window.removeEventListener('resize', measure)
  }, [pathname])

  return { links, style }
}

export function Layout() {
  const { pathname } = useLocation()
  const { links, style } = useNavIndicator(pathname)

  return (
    <div className="relative flex min-h-dvh flex-col">
      <Background />
      <CursorGlow />
      <a
        href="#main"
        className="sr-only z-50 rounded-lg bg-emerald-600 px-3 py-2 text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>

      <header className="sticky top-0 z-40 px-3 pt-3 sm:px-4">
        <div className="glass mx-auto flex max-w-5xl items-center gap-2 rounded-2xl px-3 py-2 shadow-lg shadow-black/[0.03] sm:gap-6 sm:px-4 dark:shadow-black/40">
          <NavLink to="/projects" className="group flex items-center gap-2.5 font-display font-semibold">
            <Logo className="size-8 transition-transform duration-500 group-hover:rotate-[360deg]" />
            <span className="hidden tracking-tight sm:inline">
              Deploy<span className="text-aurora">Smith</span>
            </span>
          </NavLink>
          <nav className="relative flex flex-1 gap-1 text-sm" aria-label="Main">
            {style && (
              <span
                aria-hidden
                className="absolute inset-y-0 rounded-xl bg-zinc-900/[0.06] ring-1 ring-zinc-900/5 transition-all duration-500 ease-[cubic-bezier(0.2,0.9,0.2,1.15)] dark:bg-white/[0.08] dark:ring-white/10"
                style={{ left: style.left, width: style.width }}
              />
            )}
            {NAV.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                ref={(el) => {
                  links.current[to] = el
                }}
                className={({ isActive }) =>
                  `relative rounded-xl px-2.5 py-1.5 font-medium transition-colors sm:px-3.5 ${
                    isActive
                      ? 'text-zinc-950 dark:text-white'
                      : 'text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100'
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <ThemeToggle />
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-10 sm:py-14">
        {/* Keyed by route so every navigation replays the entrance animation. */}
        <div key={pathname} className="animate-blur-in">
          <Outlet />
        </div>
      </main>

      <footer className="px-4 pb-8 text-center text-xs text-zinc-500">
        <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1.5">
          <span className="relative flex size-2">
            <span className="animate-ping-slow absolute inline-flex size-full rounded-full bg-emerald-400" />
            <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
          </span>
          DeploySmith OS · free-tier deployments only
        </span>
      </footer>
    </div>
  )
}
