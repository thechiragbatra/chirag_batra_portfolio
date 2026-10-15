import { Compass, HeartPulse, Rocket, ScanSearch, type LucideIcon } from 'lucide-react'
import { Logo } from './Logo'

const AGENTS: { label: string; icon: LucideIcon; color: string }[] = [
  { label: 'Profiler', icon: ScanSearch, color: 'text-emerald-400' },
  { label: 'Strategist', icon: Compass, color: 'text-cyan-400' },
  { label: 'Provisioner', icon: Rocket, color: 'text-violet-400' },
  { label: 'Healer', icon: HeartPulse, color: 'text-pink-400' },
]

/** Decorative hero visual: the four agents orbiting the DeploySmith core. */
export function AgentOrbit() {
  return (
    <div aria-hidden className="animate-float relative mx-auto aspect-square w-full max-w-[340px]">
      <div className="absolute inset-[6%] rounded-full border border-dashed border-zinc-900/10 dark:border-white/10" />
      <div className="absolute inset-[24%] rounded-full border border-zinc-900/10 dark:border-white/10" />
      <div
        className="absolute inset-[38%] rounded-full opacity-70 blur-2xl"
        style={{ background: 'conic-gradient(from 0deg, var(--glow-a), var(--glow-b), var(--glow-c), var(--glow-a))' }}
      />
      <div className="absolute inset-0 grid place-items-center">
        <Logo className="size-20 text-4xl drop-shadow-[0_0_30px_rgba(52,211,153,0.45)]" />
      </div>

      <div className="animate-orbit absolute inset-[6%]">
        {AGENTS.map(({ label, icon: Icon, color }, i) => {
          const angle = (i / AGENTS.length) * Math.PI * 2 - Math.PI / 2
          return (
            <div
              key={label}
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{ left: `${50 + 50 * Math.cos(angle)}%`, top: `${50 + 50 * Math.sin(angle)}%` }}
            >
              <div className="animate-orbit-reverse">
                {/* Flat glass: blurring the backdrop of something that orbits costs every frame. */}
                <div
                  className="glass-flat wake flex flex-col items-center gap-1 rounded-2xl px-3 py-2 shadow-xl shadow-black/5 dark:shadow-black/50"
                  style={{ animationDelay: `${350 + i * 110}ms` }}
                >
                  <Icon className={`size-5 ${color}`} />
                  <span className="font-mono text-[10px] text-zinc-600 dark:text-zinc-300">{label}</span>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <div className="animate-orbit-reverse absolute inset-[24%]">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="absolute size-1.5 rounded-full bg-cyan-400 shadow-[0_0_12px_4px_rgba(34,211,238,0.6)]"
            style={{ left: `${50 + 50 * Math.cos((i * 2 * Math.PI) / 3)}%`, top: `${50 + 50 * Math.sin((i * 2 * Math.PI) / 3)}%` }}
          />
        ))}
      </div>
    </div>
  )
}
