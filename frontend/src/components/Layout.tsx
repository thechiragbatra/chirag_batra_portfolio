import { NavLink, Outlet } from 'react-router-dom'
import { ThemeToggle } from './ThemeToggle'

const NAV = [
  { to: '/projects', label: 'Projects' },
  { to: '/resume', label: 'Resume' },
  { to: '/deployer', label: 'Deployer' },
]

export function Layout() {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/80 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/80">
        <div className="mx-auto flex max-w-5xl items-center gap-2 px-4 py-3 sm:gap-6">
          <NavLink to="/projects" className="flex items-center gap-2 font-semibold tracking-tight">
            <img src="/favicon.svg" alt="" className="size-6" />
            <span className="hidden sm:inline">DeploySmith</span>
          </NavLink>
          <nav className="flex flex-1 gap-1 text-sm" aria-label="Main">
            {NAV.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `rounded-lg px-2.5 py-1.5 font-medium transition-colors sm:px-3 ${
                    isActive
                      ? 'bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-50'
                      : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100'
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
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:py-12">
        <Outlet />
      </main>
      <footer className="border-t border-zinc-200 py-6 text-center text-xs text-zinc-500 dark:border-zinc-800">
        DeploySmith OS · free-tier deployments only
      </footer>
    </div>
  )
}
