import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { NavLink, Outlet, ScrollRestoration, useLocation } from 'react-router-dom'
import { useReducedMotion } from '../../hooks/useMediaQuery'
import { ArrowUpRight, Mail } from 'lucide-react'
import resumeData from '../../data/resume.json'
import { ShaderBackground } from '../fx/ShaderBackground'
import { Guide } from '../../features/guide/Guide'
import { Logo } from './Logo'

const NAV = [
  { to: '/projects', label: 'Work' },
  { to: '/lab', label: 'Lab' },
  { to: '/smith', label: 'Smith' },
  { to: '/resume', label: 'Résumé' },
  { to: '/deployer', label: 'Deploy' },
  { to: '/apps', label: 'Apps' },
]
const { basics } = resumeData
const YEAR = new Date().getFullYear()
const EMAIL = basics.links.find((l) => l.url.startsWith('mailto:'))?.url.replace('mailto:', '') ?? ''

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
    <div className="relative flex min-h-dvh flex-col overflow-x-clip">
      <ShaderBackground />
      <a
        href="#main"
        className="sr-only z-50 rounded-lg bg-emerald-600 px-3 py-2 text-white focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>

      <ScrollRestoration />
      <header data-scrolled={scrolled || undefined} className="site-header sticky top-0 z-40 px-3 pt-3 sm:px-5">
        <div className="mx-auto flex max-w-6xl items-center gap-3 rounded-2xl border border-white/[0.07] bg-[#06060e]/60 px-3 py-2 shadow-[0_10px_40px_-20px_rgb(0_0_0/0.9)] backdrop-blur-xl sm:gap-6 sm:px-4">
          <NavLink to="/projects" viewTransition={!reduced} className="group flex shrink-0 items-center gap-2.5">
            <Logo className="size-8 transition-transform duration-700 group-hover:rotate-[360deg]" />
            <span className="hidden leading-none sm:block">
              <span className="font-display block text-[15px] font-bold tracking-tight text-white">Chirag Batra</span>
              <span className="mt-0.5 block font-mono text-[10px] tracking-[0.2em] text-zinc-500 uppercase">DeploySmith OS</span>
            </span>
          </NavLink>
          {/* Scrolls sideways on narrow phones instead of pushing the header off-screen. */}
          <nav
            ref={navRef}
            className="relative flex min-w-0 flex-1 justify-start gap-0.5 overflow-x-auto [scrollbar-width:none] sm:justify-center [&::-webkit-scrollbar]:hidden"
            aria-label="Main"
          >
            {NAV.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                viewTransition={!reduced}
                className={({ isActive }) =>
                  `relative isolate shrink-0 rounded-xl px-2.5 py-1.5 font-mono text-[11px] tracking-[0.14em] whitespace-nowrap uppercase transition-colors sm:px-3 ${
                    isActive ? 'text-white' : 'text-zinc-500 hover:text-zinc-100'
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
                        className="nav-pill absolute inset-0 -z-10 rounded-xl bg-white/[0.07] shadow-[inset_0_1px_0_rgb(255_255_255/0.08),0_0_24px_-6px_var(--glow-a)] ring-1 ring-white/10"
                      />
                    )}
                    {label}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
          <a
            href={`mailto:${EMAIL}`}
            className="hidden shrink-0 items-center gap-2 rounded-full border border-white/10 px-3 py-1.5 font-mono text-[10px] tracking-[0.16em] text-zinc-300 uppercase transition-colors hover:border-cyan-300/50 hover:text-white lg:inline-flex"
          >
            <span className="relative flex size-1.5">
              <span className="animate-ping-slow absolute inline-flex size-full rounded-full bg-emerald-400" />
              <span className="relative inline-flex size-1.5 rounded-full bg-emerald-400" />
            </span>
            Open to ML roles
          </a>
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6 sm:py-14">
        {/* Keyed by route so every navigation replays the entrance animation (the blur-in
            is the fallback where the View Transitions API is unavailable). */}
        <div key={pathname} data-page className="animate-blur-in">
          <Outlet />
        </div>
      </main>

      <Guide />

      <footer className="site-footer mt-24 border-t border-white/[0.06] px-4 pt-16 pb-28 sm:px-6">
        <div className="mx-auto max-w-6xl">
          <p className="eyebrow">What next</p>
          <p className="font-display mt-4 max-w-4xl text-4xl leading-[0.95] font-extrabold text-white sm:text-6xl lg:text-7xl">
            Let&apos;s build something that <span className="font-serif text-aurora">thinks.</span>
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <a
              href={`mailto:${EMAIL}`}
              className="shine-hover pressable inline-flex items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-zinc-950 shadow-[0_0_40px_-8px_var(--glow-a)]"
            >
              <Mail className="size-4" aria-hidden /> {EMAIL}
            </a>
            {basics.links
              .filter((l) => !l.url.startsWith('mailto:'))
              .map((l) => (
                <a
                  key={l.url}
                  href={l.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-full border border-white/10 px-4 py-3 text-sm font-medium text-zinc-300 transition-colors hover:border-white/30 hover:text-white"
                >
                  {l.label} <ArrowUpRight className="size-3.5" aria-hidden />
                </a>
              ))}
          </div>
          <div className="mt-14 flex flex-col gap-3 border-t border-white/[0.06] pt-6 font-mono text-[11px] tracking-[0.12em] text-zinc-500 uppercase sm:flex-row sm:items-center sm:justify-between">
            <span>© {YEAR} {basics.name} · {basics.location}</span>
            <span className="inline-flex items-center gap-2">
              <span className="size-1.5 rounded-full bg-emerald-400" aria-hidden /> DeploySmith OS · free-tier deployments only
            </span>
          </div>
        </div>
      </footer>
    </div>
  )
}
