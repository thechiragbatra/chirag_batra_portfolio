import {
  BookOpenCheck,
  Check,
  Compass,
  Eye,
  FlaskConical,
  GitBranch,
  type LucideIcon,
  MessageSquare,
  Quote,
  Radio,
  Rocket,
  Search,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react'
import { type ReactNode, useEffect, useState } from 'react'
import { CountUp } from '../components/fx/CountUp'
import { Reveal } from '../components/fx/Reveal'
import { PageHeader } from '../components/ui/PageHeader'
import evalsData from '../data/guide-evals.json'
import { type GuideStats, guideStats, openSmith } from '../features/guide/client'

/** Written by `python -m agents.guide.evals --publish` (scores and questions, no answers). */
interface EvalSummary {
  generated: string
  models: Record<string, number>
  passed: number
  cases: number
  groups: Record<string, { passed: number; cases: number }>
  results: { id: string; group: string; question: string; passed: boolean }[]
}
const evals = evalsData as EvalSummary

const SOURCE = 'https://github.com/thechiragbatra/deploysmith/tree/main/agents/guide'

const TOOLS: { name: string; icon: LucideIcon; does: string }[] = [
  { name: 'search_portfolio', icon: Search, does: 'BM25 over the résumé, projects and Lab results, returning citable passages' },
  { name: 'open_page', icon: Compass, does: 'Navigates your browser and highlights the section it is talking about' },
  { name: 'describe_view', icon: Eye, does: 'Reads what is on your screen, like the customer loaded in the Lab' },
  { name: 'score_customer', icon: FlaskConical, does: 'Runs the churn and uplift models for what-if questions' },
  { name: 'profile_repo', icon: GitBranch, does: 'Clones any public repo (hardened, nothing executed) and plans its hosting' },
  { name: 'start_deployment', icon: Rocket, does: 'Starts a real DeploySmith run and opens the Deployer to watch it' },
]

const GUARDRAILS: ReactNode[] = [
  <>States facts only from tool results, and <strong>cites every one</strong>.</>,
  <>Never invents experience, employers or numbers; planned projects are <strong>always called planned</strong>.</>,
  <>Says <strong>“I don’t know”</strong> when the portfolio does not cover a question.</>,
  <>Declines off-topic requests, and treats tool output as <strong>data, never instructions</strong>.</>,
  <>Free tier, kept free: per-visitor and daily limits, a one-day answer cache, and fallback models.</>,
  <>Public stats are aggregates only: <strong>no visitor’s question is ever shown</strong>.</>,
]

const GROUP_LABELS: Record<string, string> = {
  facts: 'Facts, with the right citation',
  honesty: 'Honesty: no invented facts',
  'off-topic': 'Declines off-topic requests',
  tools: 'Uses the right tool',
}

function Section({ eyebrow, title, guide, children }: { eyebrow: string; title: string; guide: string; children: ReactNode }) {
  return (
    <section data-guide={guide} className="mt-16">
      <Reveal className="mb-6">
        <p className="mb-2 font-mono text-xs tracking-[0.2em] text-emerald-600 uppercase dark:text-emerald-400">{eyebrow}</p>
        <h2 className="font-display text-3xl font-bold">{title}</h2>
      </Reveal>
      {children}
    </section>
  )
}

function Node({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: ReactNode }) {
  return (
    <div className="glass-strong rounded-2xl p-4">
      <div className="mb-2 flex items-center gap-2">
        <span className="grid size-8 place-items-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
          <Icon className="size-4" aria-hidden />
        </span>
        <h3 className="font-display font-semibold">{title}</h3>
      </div>
      <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{children}</p>
    </div>
  )
}

/** Horizontal connector with the pipeline's travelling packet; a plain line on phones. */
function Wire() {
  return (
    <div aria-hidden className="flex items-center justify-center py-1 sm:px-1 sm:py-0">
      <div className="h-6 w-px bg-zinc-900/15 sm:hidden dark:bg-white/15" />
      <div className="packet-track relative hidden h-[3px] w-full min-w-6 rounded-full bg-zinc-900/10 sm:block dark:bg-white/10">
        <span className="packet" />
      </div>
    </div>
  )
}

function ScoreRing({ passed, total }: { passed: number; total: number }) {
  const share = total ? passed / total : 0
  return (
    <div className="relative size-36 shrink-0">
      <svg viewBox="0 0 100 100" className="size-full -rotate-90" aria-hidden>
        <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeOpacity="0.1" strokeWidth="9" />
        <circle
          cx="50"
          cy="50"
          r="42"
          fill="none"
          stroke="url(#smith-score)"
          strokeWidth="9"
          strokeLinecap="round"
          pathLength={100}
          strokeDasharray={`${share * 100} 100`}
          className="lab-draw"
          style={{ strokeDashoffset: 100 }}
        />
        <defs>
          <linearGradient id="smith-score" x1="0" x2="1">
            <stop offset="0" stopColor="var(--glow-a)" />
            <stop offset="1" stopColor="var(--glow-b)" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute inset-0 grid place-content-center text-center">
        <span className="font-display text-3xl font-bold tabular-nums">
          {passed}/{total}
        </span>
        <span className="text-xs text-zinc-500">cases passed</span>
      </div>
    </div>
  )
}

function Stat({ value, label }: { value: ReactNode; label: string }) {
  return (
    <div className="glass-strong rounded-2xl p-4">
      <div className="font-display text-2xl font-bold tabular-nums">{value}</div>
      <div className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">{label}</div>
    </div>
  )
}

function LiveStats() {
  const [stats, setStats] = useState<GuideStats | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    guideStats(controller.signal).then(setStats, () => !controller.signal.aborted && setFailed(true))
    return () => controller.abort()
  }, [])

  if (failed) {
    return <p className="text-sm text-zinc-500">Live usage appears here when the API is running.</p>
  }
  if (!stats) return <div aria-busy className="glass-strong h-28 animate-pulse rounded-2xl" />
  if (stats.questions === 0) {
    return (
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        No questions in the last {stats.window_hours} hours yet.{' '}
        <button type="button" onClick={openSmith} className="font-medium text-emerald-700 hover:underline dark:text-emerald-400">
          Be the first →
        </button>
      </p>
    )
  }
  const tools = Object.entries(stats.tools)
  const maxTool = Math.max(1, ...tools.map(([, n]) => n))
  const sec = (ms: number | null) => (ms === null ? '–' : `${(ms / 1000).toFixed(1)} s`)
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat value={<CountUp value={stats.questions} />} label={`questions in the last ${stats.window_hours} h`} />
        <Stat
          value={`${Math.round((100 * stats.answered_from_cache) / stats.questions)}%`}
          label="answered instantly from the cache"
        />
        <Stat value={sec(stats.latency_ms.p50)} label={`median answer time (p90 ${sec(stats.latency_ms.p90)})`} />
        <Stat
          value={stats.tokens_per_answer === null ? '–' : stats.tokens_per_answer.toLocaleString()}
          label="tokens per fresh answer"
        />
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="glass-strong rounded-2xl p-4">
          <h3 className="mb-3 text-sm font-semibold">Tools used</h3>
          <ul className="space-y-2">
            {tools.map(([name, n]) => (
              <li key={name} className="grid grid-cols-[9rem_minmax(0,1fr)_2rem] items-center gap-2 text-xs">
                <span className="truncate font-mono text-zinc-600 dark:text-zinc-400">{name}</span>
                <span className="h-2 overflow-hidden rounded-full bg-zinc-900/[0.06] dark:bg-white/10">
                  <span className="block h-full rounded-full bg-gradient-to-r from-emerald-400 to-cyan-400" style={{ width: `${(100 * n) / maxTool}%` }} />
                </span>
                <span className="text-right tabular-nums">{n}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="glass-strong rounded-2xl p-4 text-sm">
          <h3 className="mb-3 font-semibold">Models and feedback</h3>
          <ul className="space-y-1 text-xs">
            {Object.entries(stats.models).map(([model, n]) => (
              <li key={model} className="flex justify-between gap-2">
                <span className="font-mono text-zinc-600 dark:text-zinc-400">{model}</span>
                <span className="tabular-nums">{n} answers</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-zinc-600 dark:text-zinc-400">
            Visitor ratings: {stats.feedback.up} helpful · {stats.feedback.down} not helpful
            {stats.errors > 0 && ` · ${stats.errors} failed`}
          </p>
        </div>
      </div>
    </div>
  )
}

export default function Smith() {
  const groups = Object.entries(evals.groups)
  return (
    <>
      <PageHeader
        eyebrow="AI agent · LangGraph + Groq"
        title={
          <>
            How <span className="text-aurora">Smith</span> works
          </>
        }
      >
        Smith is the AI guide on this site. It answers questions about Chirag’s work from the site’s own content, cites
        every claim, and uses the site itself to show you: it opens pages, runs the churn model, profiles repositories
        and starts deployments. Its answers are graded on a fixed test set, below.
      </PageHeader>
      <div className="-mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={openSmith}
          className="shine-hover pressable inline-flex items-center gap-2 rounded-xl bg-zinc-950 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-emerald-500/20 dark:bg-white dark:text-zinc-950"
        >
          <Sparkles className="size-4" aria-hidden /> Ask Smith
        </button>
        <a href={SOURCE} target="_blank" rel="noreferrer" className="glass inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold hover:bg-white/80 dark:hover:bg-white/10">
          <GitBranch className="size-4" aria-hidden /> Source code
        </a>
      </div>

      <Section guide="architecture" eyebrow="Architecture" title="One question, start to finish">
        <Reveal variant="scan">
          <div className="grid items-stretch gap-0 sm:grid-cols-[1fr_2.5rem_1fr_2.5rem_1.3fr_2.5rem_1fr]">
            <Node icon={MessageSquare} title="You ask">
              Typed or spoken, plus the page you are on and what it shows.
            </Node>
            <Wire />
            <Node icon={Radio} title="FastAPI">
              Rate-limits, checks the cache, and streams every step back as server-sent events.
            </Node>
            <Wire />
            <div className="glass-strong glow-border rounded-2xl p-4" data-glow>
              <div className="mb-2 flex items-center gap-2">
                <span className="grid size-8 place-items-center rounded-lg bg-violet-500/10 text-violet-600 dark:text-violet-400">
                  <Sparkles className="size-4" aria-hidden />
                </span>
                <h3 className="font-display font-semibold">LangGraph loop</h3>
              </div>
              <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
                The model (gpt-oss-120b on Groq, with two fallbacks) picks tools; their results go back in; up to four
                rounds, then it must answer.
              </p>
              <p className="mt-3 flex items-center justify-center gap-2 font-mono text-xs text-zinc-500">
                model <span className="text-emerald-500">⇄</span> tools
              </p>
            </div>
            <Wire />
            <Node icon={Quote} title="Answer">
              Cited sources, page actions in your browser, and follow-up suggestions.
            </Node>
          </div>
        </Reveal>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {TOOLS.map((tool, i) => (
            <Reveal key={tool.name} delay={(i % 3) * 90} variant="scan">
              <div className="glass h-full rounded-2xl p-4">
                <p className="flex items-center gap-2 font-mono text-sm font-semibold">
                  <tool.icon className="size-4 text-emerald-500" aria-hidden /> {tool.name}
                </p>
                <p className="mt-1.5 text-sm text-zinc-600 dark:text-zinc-400">{tool.does}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </Section>

      <Section guide="guardrails" eyebrow="Guardrails" title="Built to be trusted by recruiters">
        <Reveal>
          <ul className="grid gap-3 sm:grid-cols-2">
            {GUARDRAILS.map((rule, i) => (
              <li key={i} className="glass flex gap-3 rounded-2xl p-4 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
                <ShieldCheck className="mt-0.5 size-4 shrink-0 text-emerald-500" aria-hidden />
                <span>{rule}</span>
              </li>
            ))}
          </ul>
        </Reveal>
      </Section>

      <Section guide="evaluation" eyebrow="Evaluation" title="Graded, not just demoed">
        <Reveal variant="scan">
          <div className="glass-strong rounded-2xl p-5 sm:p-6">
            <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
              <ScoreRing passed={evals.passed} total={evals.cases} />
              <div className="flex-1 space-y-3">
                {groups.map(([group, g]) => (
                  <div key={group}>
                    <div className="mb-1 flex justify-between text-sm">
                      <span>{GROUP_LABELS[group] ?? group}</span>
                      <span className="font-mono text-xs tabular-nums">
                        {g.passed}/{g.cases}
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-zinc-900/[0.06] dark:bg-white/10">
                      <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-cyan-400" style={{ width: `${(100 * g.passed) / g.cases}%` }} />
                    </div>
                  </div>
                ))}
                <p className="text-xs text-zinc-500">
                  Run on {evals.generated} with {Object.keys(evals.models).join(', ')}. Each case is graded by code, not by
                  another model: the right source cited, required facts present, forbidden claims absent, the right tool
                  called.
                </p>
              </div>
            </div>
            <details className="mt-5 rounded-xl border border-[var(--glass-border)] p-3">
              <summary className="cursor-pointer text-sm font-medium select-none">
                <BookOpenCheck className="mr-1.5 inline size-4 align-[-3px] text-emerald-500" aria-hidden />
                All {evals.cases} questions
              </summary>
              <ul className="mt-3 divide-y divide-[var(--glass-border)] text-sm">
                {evals.results.map((r) => (
                  <li key={r.id} className="flex items-start gap-3 py-2">
                    {r.passed ? (
                      <Check className="mt-0.5 size-4 shrink-0 text-emerald-500" aria-label="passed" />
                    ) : (
                      <X className="mt-0.5 size-4 shrink-0 text-rose-500" aria-label="failed" />
                    )}
                    <span className="flex-1 text-zinc-700 dark:text-zinc-300">{r.question}</span>
                    <span className="shrink-0 font-mono text-[11px] text-zinc-500">{r.group}</span>
                  </li>
                ))}
              </ul>
            </details>
          </div>
        </Reveal>
      </Section>

      <Section guide="usage" eyebrow="Observability" title="Live usage">
        <LiveStats />
      </Section>
    </>
  )
}
