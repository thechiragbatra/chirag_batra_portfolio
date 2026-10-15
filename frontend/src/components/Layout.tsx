import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { NavLink, Outlet, ScrollRestoration, useLocation } from 'react-router-dom'
import { useReducedMotion } from '../hooks/useMediaQuery'
import { Background } from './fx/Background'
import { CursorGlow } from './fx/CursorGlow'
import { Logo } from './Logo'
import { ThemeToggle } from './ThemeToggle'

const NAV = [
  { to: '/projects', label: 'Projects' },
  { to: '/lab', label: 'Lab' },
  { to: '/resume', label: 'Resume' },
  { to: '/deployer', label: 'Deployer' },
  { to: '/apps', label: 'Apps' },
]

/** Order of the main routes, so page transitions slide the way the nav reads. */
function navIndex(pathname: string): number {
  return NAV.findIndex((item) => pathname.startsWith(item.to))
}

/**
 * Before the new page paints (this runs inside the view transition's update), tell the
 * CSS which way to slide: forward/back along the nav, or a plain fade for other routes.
 */
function useNavDirection(pathname: string) {
  const previous = useRef(pathname)
  useLayoutEffect(() => {
    const from = navIndex(previous.current)
    const to = navIndex(pathname)
    const dir = to < 0 || from < 0 ? (to < 0 ? 'none' : 'back') : to >= from ? 'forward' : 'back'
    document.documentElement.dataset.navDir = dir
    previous.current = pathname
  }, [pathname])
}

/** True once the page has scrolled a little; the header condenses. */
function useScrolled(threshold = 24) {
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > threshold)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [threshold])
  return scrolled
}

export function Layout() {
  const { pathname } = useLocation()
  const reduced = useReducedMotion()
  const scrolled = useScrolled()
  useNavDirection(pathname)
  const navRef = useRef<HTMLElement>(null)
  // Keep the active link visible when the nav is scrollable.
  useEffect(() => {
    navRef.current?.querySelector('[aria-current="page"]')?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }, [pathname])

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

      <ScrollRestoration />
      <header data-scrolled={scrolled || undefined} className="sticky top-0 z-40 px-3 pt-3 sm:px-4">
        <div className="glass mx-auto flex max-w-5xl items-center gap-2 rounded-2xl px-3 py-2 shadow-lg shadow-black/[0.03] sm:gap-6 sm:px-4 dark:shadow-black/40">
          <NavLink to="/projects" viewTransition={!reduced} className="group flex items-center gap-2.5 font-display font-semibold">
            <Logo className="size-8 transition-transform duration-500 group-hover:rotate-[360deg]" />
            <span className="hidden tracking-tight sm:inline">
              Deploy<span className="text-aurora">Smith</span>
            </span>
          </NavLink>
          {/* Scrolls sideways on narrow phones instead of pushing the header off-screen. */}
          <nav
            ref={navRef}
            className="relative flex min-w-0 flex-1 gap-1 overflow-x-auto text-sm [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            aria-label="Main"
          >
            {NAV.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                viewTransition={!reduced}
                className={({ isActive }) =>
                  `relative isolate shrink-0 rounded-xl px-2.5 py-1.5 font-medium whitespace-nowrap transition-colors sm:px-3.5 ${
                    isActive
                      ? 'text-zinc-950 dark:text-white'
                      : 'text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {/* Lives inside the active link; the page transition morphs it from
                        the old link to the new one (a shared element). */}
                    {isActive && (
                      <span
                        aria-hidden
                        className="nav-pill absolute inset-0 -z-10 rounded-xl bg-zinc-900/[0.06] ring-1 ring-zinc-900/5 dark:bg-white/[0.08] dark:ring-white/10"
                      />
                    )}
                    {label}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
          <div className="shrink-0">
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-10 sm:py-14">
        {/* Keyed by route so every navigation replays the entrance animation (the blur-in
            is the fallback where the View Transitions API is unavailable). */}
        <div key={pathname} data-page className="animate-blur-in">
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
