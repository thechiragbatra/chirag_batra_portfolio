import {
  ArrowUp,
  Check,
  Compass,
  Eye,
  FlaskConical,
  GitBranch,
  Loader2,
  Mic,
  Rocket,
  RotateCcw,
  Search,
  Sparkles,
  Square,
  ThumbsDown,
  ThumbsUp,
  Volume2,
  VolumeX,
  X,
  Zap,
} from 'lucide-react'
import { type FormEvent, type KeyboardEvent, type ReactNode, useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { prefersReducedMotion } from '../../hooks/useMediaQuery'
import { setActivity } from '../../lib/activity'
import {
  askGuide,
  type ChatTurn,
  type GuideAction,
  type GuideEvent,
  guideStatus,
  guideViewFor,
  sendCustomerToLab,
  sendFeedback,
} from './client'
import { canListen, canSpeak, speak, stopSpeaking, useSpeechInput } from './voice'

interface Step {
  id: string
  tool: string
  args: Record<string, unknown>
  done: boolean
  ok: boolean
  summary: string
}

interface Source {
  id: string
  title: string
  page: string
  section: string | null
  url: string | null
}

type Item =
  | { role: 'user'; content: string }
  | {
      role: 'assistant'
      content: string
      steps: Step[]
      sources: Source[]
      pending: boolean
      error?: string
      run?: string
      cached?: boolean
      rating?: 'up' | 'down'
      suggestions?: string[]
    }

const STORAGE_KEY = 'smith-chat'
const SPEAK_KEY = 'smith-speak'
// Used until the server's per-page starters arrive.
const DEFAULT_STARTERS = [
  'What has Chirag built with machine learning?',
  'Show me his causal inference work',
  'What if a lost-cause customer signed a two-year contract?',
]

function loadSpeak(): boolean {
  try {
    return localStorage.getItem(SPEAK_KEY) === '1'
  } catch {
    return false
  }
}

function loadItems(): Item[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as Item[]).filter((i) => i.role === 'user' || !i.pending) : []
  } catch {
    return []
  }
}

function saveItems(items: Item[]) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(-30)))
  } catch {
    // storage unavailable (private mode); the chat still works
  }
}

// ---- Acting on the page ----

/** Wait for a section to render (pages may still be loading), then scroll to it and flash it. */
function highlightSection(section: string) {
  const started = performance.now()
  const find = () => {
    const el = document.querySelector<HTMLElement>(`[data-guide="${CSS.escape(section)}"]`)
    if (!el) {
      if (performance.now() - started < 5000) requestAnimationFrame(find)
      return
    }
    let target: HTMLElement = el
    if (el.getAttribute('role') === 'tab') {
      // Résumé sections are tabs: select it, then show its panel.
      el.click()
      target = document.getElementById(el.getAttribute('aria-controls') ?? '') ?? el
    }
    target.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'center' })
    target.dataset.guideFlash = ''
    window.setTimeout(() => delete target.dataset.guideFlash, 2600)
  }
  window.setTimeout(find, 120)
}

// ---- Rendering answers ----

// Citations as models write them: [S1], 【S1】, 【S1†L3】, [**S1**].
const cites = (text: string, id: string) =>
  new RegExp(`[[【]\\s*(?:\\*\\*)?\\s*${id}(?!\\d)[^\\]】]*[\\]】]`).test(text)

const TOOL_META: Record<string, { icon: typeof Search; label: (args: Record<string, unknown>) => string }> = {
  search_portfolio: { icon: Search, label: (a) => `Searching the portfolio for “${String(a.query ?? '')}”` },
  open_page: { icon: Compass, label: (a) => `Opening ${String(a.page ?? '')}${a.section ? ` · ${String(a.section)}` : ''}` },
  score_customer: {
    icon: FlaskConical,
    label: (a) => {
      const changes = Object.entries((a.changes as Record<string, unknown>) ?? {})
      return `Running the churn model${changes.length ? `: ${changes.map(([k, v]) => `${k} = ${String(v)}`).join(', ')}` : ''}`
    },
  },
  profile_repo: { icon: GitBranch, label: (a) => `Profiling ${String(a.repo_url ?? 'the repo').replace('https://github.com/', '')}` },
  describe_view: { icon: Eye, label: () => 'Looking at your screen' },
  start_deployment: {
    icon: Rocket,
    label: (a) => `Deploying ${String(a.repo_url ?? 'the repo').replace('https://github.com/', '')}`,
  },
}

function StepChip({ step }: { step: Step }) {
  const meta = TOOL_META[step.tool] ?? { icon: Sparkles, label: () => step.tool }
  const Icon = meta.icon
  return (
    <li className="animate-fade-up flex items-start gap-2 text-xs">
      <span
        className={`mt-px grid size-5 shrink-0 place-items-center rounded-md ${
          step.done ? (step.ok ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400' : 'bg-rose-500/15 text-rose-600') : 'bg-zinc-900/5 text-zinc-500 dark:bg-white/10'
        }`}
      >
        {step.done ? step.ok ? <Check className="size-3" aria-hidden /> : <X className="size-3" aria-hidden /> : <Loader2 className="size-3 animate-spin" aria-hidden />}
      </span>
      <span className="min-w-0">
        <span className="flex items-center gap-1.5 text-zinc-700 dark:text-zinc-300">
          <Icon className="size-3.5 shrink-0 opacity-60" aria-hidden />
          <span className="break-words">{meta.label(step.args)}</span>
        </span>
        {step.done && <span className="block font-mono text-[11px] text-zinc-500">{step.summary}</span>}
      </span>
    </li>
  )
}

/** Bold, citations and simple lists; everything else is plain text (never HTML). */
function Inline({ text, sources, onCite }: { text: string; sources: Source[]; onCite: (s: Source) => void }) {
  // Models sometimes write citations with full-width brackets: 【S1】 or 【S1†L3】.
  const parts = text.replace(/\s*(?:【\s*】|\[\s*\])/g, '').split(/([[【]\s*(?:\*\*)?\s*S\d+[^\]】]*[\]】]|\*\*[^*]+\*\*)/g)
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>
        const cite = /^[[【]\s*(?:\*\*)?\s*(S\d+)[^\]】]*[\]】]$/.exec(part)
        if (cite) {
          const source = sources.find((s) => s.id === cite[1])
          if (!source) return null // never show a citation that points nowhere
          return (
            <button
              key={i}
              type="button"
              onClick={() => onCite(source)}
              title={source.title}
              className="mx-0.5 inline-flex -translate-y-px items-center rounded bg-emerald-500/15 px-1 font-mono text-[10px] font-semibold text-emerald-700 transition-colors hover:bg-emerald-500/30 dark:text-emerald-300"
            >
              {cite[1]}
            </button>
          )
        }
        return <span key={i}>{part}</span>
      })}
    </>
  )
}

function Answer({ text, sources, onCite }: { text: string; sources: Source[]; onCite: (s: Source) => void }) {
  const blocks: ReactNode[] = []
  let list: string[] = []
  const flush = () => {
    if (list.length) {
      blocks.push(
        <ul key={blocks.length} className="ml-4 list-disc space-y-1 marker:text-emerald-500">
          {list.map((item, i) => (
            <li key={i}>
              <Inline text={item} sources={sources} onCite={onCite} />
            </li>
          ))}
        </ul>,
      )
      list = []
    }
  }
  for (const line of text.split('\n')) {
    const bullet = /^\s*(?:[-*•]|\d+\.)\s+(.*)$/.exec(line)
    if (bullet) {
      list.push(bullet[1])
      continue
    }
    flush()
    if (line.trim()) {
      blocks.push(
        <p key={blocks.length}>
          <Inline text={line} sources={sources} onCite={onCite} />
        </p>,
      )
    }
  }
  flush()
  return <div className="space-y-2">{blocks}</div>
}

// ---- The panel ----

export function Guide() {
  const [enabled, setEnabled] = useState(false)
  const [starters, setStarters] = useState<Record<string, string[]>>({})
  const [speakAnswers, setSpeakAnswers] = useState(loadSpeak)
  const speakRef = useRef(speakAnswers)
  useEffect(() => {
    speakRef.current = speakAnswers
    try {
      localStorage.setItem(SPEAK_KEY, speakAnswers ? '1' : '0')
    } catch {
      // preference only
    }
    if (!speakAnswers) stopSpeaking()
  }, [speakAnswers])
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<Item[]>(loadItems)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const launcherRef = useRef<HTMLButtonElement>(null)
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const pathRef = useRef(pathname)
  useEffect(() => {
    pathRef.current = pathname
  }, [pathname])

  useEffect(() => {
    const controller = new AbortController()
    guideStatus(controller.signal).then(
      (s) => {
        setEnabled(s.enabled)
        setStarters(s.starters ?? {})
      },
      () => setEnabled(false),
    )
    return () => controller.abort()
  }, [])

  // The background stirs while Smith is working on an answer.
  useEffect(() => {
    setActivity('smith', busy ? 0.6 : 0)
    return () => setActivity('smith', 0)
  }, [busy])

  useEffect(() => saveItems(items.filter((i) => i.role === 'user' || !i.pending)), [items])

  useEffect(() => {
    const onOpen = () => setOpen(true)
    window.addEventListener('smith:open', onOpen)
    return () => window.removeEventListener('smith:open', onOpen)
  }, [])

  // ⌘K / Ctrl+K toggles the guide anywhere on the site.
  useEffect(() => {
    if (!enabled) return
    const onKey = (event: globalThis.KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setOpen((o) => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [enabled])

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  // Follow new content, unless the reader scrolled up.
  useEffect(() => {
    const el = scrollRef.current
    if (el && el.scrollHeight - el.scrollTop - el.clientHeight < 140) el.scrollTop = el.scrollHeight
  }, [items])

  const close = () => {
    setOpen(false)
    stopSpeaking()
    launcherRef.current?.focus()
  }

  const act = useCallback(
    (action: GuideAction) => {
      if (action.type === 'navigate') {
        if (pathRef.current !== action.path) navigate(action.path, { viewTransition: !prefersReducedMotion() })
        if (action.section) highlightSection(action.section)
      } else if (action.type === 'set_customer') {
        sendCustomerToLab(action.values)
      }
    },
    [navigate],
  )

  const onCite = (source: Source) => act({ type: 'navigate', path: source.page, section: source.section })

  const updateLast = (fn: (item: Extract<Item, { role: 'assistant' }>) => Extract<Item, { role: 'assistant' }>) =>
    setItems((all) => {
      const last = all[all.length - 1]
      if (!last || last.role !== 'assistant') return all
      return [...all.slice(0, -1), fn(last)]
    })

  const send = async (question: string) => {
    const text = question.trim()
    if (!text || busy) return
    const history: ChatTurn[] = [
      ...items.filter((i) => !(i.role === 'assistant' && (i.error || !i.content))).map((i) => ({ role: i.role, content: i.content })),
      { role: 'user', content: text },
    ]
    setItems((all) => [...all, { role: 'user', content: text }, { role: 'assistant', content: '', steps: [], sources: [], pending: true }])
    setInput('')
    setBusy(true)
    stopSpeaking()
    const controller = new AbortController()
    abortRef.current = controller

    let answerText = ''
    const onEvent = (event: GuideEvent) => {
      switch (event.type) {
        case 'token':
          answerText += event.text
          updateLast((m) => ({ ...m, content: m.content + event.text }))
          break
        case 'reset_text':
          answerText = ''
          updateLast((m) => ({ ...m, content: '' }))
          break
        case 'step':
          updateLast((m) => ({ ...m, steps: [...m.steps, { id: event.id, tool: event.tool, args: event.args, done: false, ok: true, summary: '' }] }))
          break
        case 'step_done':
          updateLast((m) => ({
            ...m,
            steps: m.steps.map((s) => (s.id === event.id ? { ...s, done: true, ok: event.ok, summary: event.summary } : s)),
          }))
          break
        case 'source':
          updateLast((m) => (m.sources.some((s) => s.id === event.id) ? m : { ...m, sources: [...m.sources, event] }))
          break
        case 'action':
          act(event.action)
          break
        case 'meta':
          updateLast((m) => ({ ...m, run: event.run, cached: event.cached }))
          break
        case 'suggestions':
          updateLast((m) => ({ ...m, suggestions: event.items }))
          break
        case 'error':
          updateLast((m) => ({ ...m, pending: false, error: event.message }))
          break
        case 'done':
          updateLast((m) => ({ ...m, pending: false, content: m.content.trim() }))
          if (speakRef.current && answerText.trim()) speak(answerText)
          break
      }
    }

    try {
      await askGuide(history, pathRef.current, onEvent, controller.signal, guideViewFor(pathRef.current))
      updateLast((m) => ({ ...m, pending: false }))
    } catch (error) {
      const stopped = error instanceof DOMException && error.name === 'AbortError'
      updateLast((m) => ({
        ...m,
        pending: false,
        error: stopped ? (m.content ? undefined : 'Stopped.') : error instanceof Error ? error.message : String(error),
      }))
    } finally {
      setBusy(false)
      abortRef.current = null
    }
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    void send(input)
  }

  const onInputKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void send(input)
    }
  }

  const voice = useSpeechInput(setInput, (text) => void send(text))
  const listenSupported = canListen()
  const speakSupported = canSpeak()

  const rate = (index: number, run: string, rating: 'up' | 'down') => {
    setItems((all) => all.map((item, i) => (i === index && item.role === 'assistant' ? { ...item, rating } : item)))
    sendFeedback(run, rating).catch(() => {
      // feedback is best effort
    })
  }

  const pageStarters = starters[pathname] ?? starters['/projects'] ?? DEFAULT_STARTERS
  const lastIndex = items.length - 1

  if (!enabled) return null

  return (
    <>
      <button
        ref={launcherRef}
        type="button"
        onClick={() => (open ? close() : setOpen(true))}
        aria-expanded={open}
        aria-controls="smith-panel"
        className={`shine-hover pressable fixed right-4 bottom-4 z-50 inline-flex items-center gap-2 rounded-full bg-zinc-950 py-2.5 pr-4 pl-3 text-sm font-semibold text-white shadow-xl shadow-emerald-500/25 transition-[opacity,transform] duration-300 hover:shadow-emerald-500/45 sm:right-6 sm:bottom-6 dark:bg-white dark:text-zinc-950 ${
          open ? 'pointer-events-none translate-y-2 opacity-0' : ''
        }`}
      >
        <span className="grid size-6 place-items-center rounded-full bg-gradient-to-br from-emerald-400 via-cyan-400 to-violet-500">
          <Sparkles className="size-3.5 text-white" aria-hidden />
        </span>
        Ask Smith
        <kbd className="hidden rounded border border-white/20 px-1.5 font-mono text-[10px] font-medium opacity-70 sm:inline dark:border-zinc-950/20">⌘K</kbd>
      </button>

      {open && (
        <section
          id="smith-panel"
          role="dialog"
          aria-label="Smith, the AI guide"
          onKeyDown={(e) => e.key === 'Escape' && close()}
          className="guide-panel glass-strong fixed inset-x-2 bottom-2 z-50 flex h-[min(42rem,calc(100dvh-1rem))] flex-col overflow-hidden rounded-2xl shadow-2xl shadow-black/20 sm:inset-x-auto sm:right-6 sm:bottom-6 sm:w-[26rem] sm:h-[min(42rem,calc(100dvh-3rem))]"
        >
          <header className="flex items-center gap-3 border-b border-[var(--glass-border)] px-4 py-3">
            <span className="grid size-8 place-items-center rounded-full bg-gradient-to-br from-emerald-400 via-cyan-400 to-violet-500 shadow-md shadow-emerald-500/30">
              <Sparkles className="size-4 text-white" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-display text-sm font-semibold">Smith</p>
              <p className="truncate text-xs text-zinc-500">AI guide · answers from this site, with sources</p>
            </div>
            {speakSupported && (
              <button
                type="button"
                onClick={() => setSpeakAnswers((on) => !on)}
                aria-pressed={speakAnswers}
                className="rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-zinc-900/5 hover:text-zinc-900 dark:hover:bg-white/10 dark:hover:text-white aria-pressed:text-emerald-600 dark:aria-pressed:text-emerald-400"
                aria-label={speakAnswers ? 'Stop reading answers aloud' : 'Read answers aloud'}
                title={speakAnswers ? 'Reading answers aloud' : 'Read answers aloud'}
              >
                {speakAnswers ? <Volume2 className="size-4" /> : <VolumeX className="size-4" />}
              </button>
            )}
            {items.length > 0 && (
              <button
                type="button"
                onClick={() => {
                  abortRef.current?.abort()
                  setItems([])
                }}
                className="rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-zinc-900/5 hover:text-zinc-900 dark:hover:bg-white/10 dark:hover:text-white"
                aria-label="New conversation"
                title="New conversation"
              >
                <RotateCcw className="size-4" />
              </button>
            )}
            <button
              type="button"
              onClick={close}
              className="rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-zinc-900/5 hover:text-zinc-900 dark:hover:bg-white/10 dark:hover:text-white"
              aria-label="Close Smith"
            >
              <X className="size-4" />
            </button>
          </header>

          <div ref={scrollRef} className="flex-1 space-y-5 overflow-y-auto px-4 py-4 text-sm leading-relaxed" aria-live="polite">
            {items.length === 0 && (
              <div className="animate-fade-up">
                <p className="text-zinc-700 dark:text-zinc-300">
                  Hi, I’m Smith. Ask me anything about Chirag’s work. I answer only from this site and cite my
                  sources. I can also open pages, explain what is on your screen, run the churn model, and profile or
                  deploy a GitHub repo.{listenSupported && ' Tap the mic to ask out loud.'}
                </p>
                <ul className="mt-4 space-y-2">
                  {pageStarters.map((s) => (
                    <li key={s}>
                      <button
                        type="button"
                        onClick={() => void send(s)}
                        className="w-full rounded-xl border border-[var(--glass-border)] bg-white/50 px-3 py-2 text-left text-[13px] text-zinc-700 transition-colors hover:border-emerald-400/50 hover:bg-emerald-500/5 dark:bg-white/5 dark:text-zinc-300"
                      >
                        {s}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {items.map((item, i) =>
              item.role === 'user' ? (
                <div key={i} className="flex justify-end">
                  <p className="max-w-[85%] rounded-2xl rounded-br-md bg-zinc-950 px-3.5 py-2 break-words whitespace-pre-wrap text-white dark:bg-white dark:text-zinc-950">
                    {item.content}
                  </p>
                </div>
              ) : (
                <div key={i} className="space-y-3">
                  {item.steps.length > 0 && <ul className="space-y-1.5">{item.steps.map((s) => <StepChip key={s.id} step={s} />)}</ul>}
                  {item.content && (
                    <div className="text-zinc-800 dark:text-zinc-200">
                      <Answer text={item.content} sources={item.sources} onCite={onCite} />
                      {item.pending && <span className="animate-blink ml-0.5 inline-block h-4 w-1.5 translate-y-0.5 bg-emerald-500" aria-hidden />}
                    </div>
                  )}
                  {item.pending && !item.content && item.steps.every((s) => s.done) && (
                    <p className="flex items-center gap-2 text-xs text-zinc-500">
                      <Loader2 className="size-3.5 animate-spin" aria-hidden /> Thinking…
                    </p>
                  )}
                  {item.error && <p className="text-xs text-rose-600 dark:text-rose-400">{item.error}</p>}
                  {!item.pending && item.sources.some((s) => cites(item.content, s.id)) && (
                    <ul className="flex flex-wrap gap-1.5">
                      {item.sources
                        .filter((s) => cites(item.content, s.id))
                        .map((s) => (
                          <li key={s.id}>
                            <button
                              type="button"
                              onClick={() => onCite(s)}
                              className="inline-flex max-w-[16rem] items-center gap-1.5 rounded-full border border-[var(--glass-border)] px-2 py-0.5 text-[11px] text-zinc-600 transition-colors hover:border-emerald-400/50 hover:text-emerald-700 dark:text-zinc-400 dark:hover:text-emerald-300"
                            >
                              <span className="font-mono font-semibold text-emerald-600 dark:text-emerald-400">{s.id}</span>
                              <span className="truncate">{s.title}</span>
                            </button>
                          </li>
                        ))}
                    </ul>
                  )}
                  {!item.pending && !item.error && item.content && (
                    <div className="flex items-center gap-1 text-zinc-400">
                      {item.run && (
                        <>
                          <button
                            type="button"
                            disabled={!!item.rating}
                            onClick={() => item.run && rate(i, item.run, 'up')}
                            aria-label="Helpful answer"
                            aria-pressed={item.rating === 'up'}
                            className="rounded-md p-1 transition-colors enabled:hover:bg-emerald-500/10 enabled:hover:text-emerald-600 aria-pressed:text-emerald-600 disabled:cursor-default dark:aria-pressed:text-emerald-400"
                          >
                            <ThumbsUp className="size-3.5" />
                          </button>
                          <button
                            type="button"
                            disabled={!!item.rating}
                            onClick={() => item.run && rate(i, item.run, 'down')}
                            aria-label="Unhelpful answer"
                            aria-pressed={item.rating === 'down'}
                            className="rounded-md p-1 transition-colors enabled:hover:bg-rose-500/10 enabled:hover:text-rose-600 aria-pressed:text-rose-600 disabled:cursor-default"
                          >
                            <ThumbsDown className="size-3.5" />
                          </button>
                          {item.rating && <span className="ml-1 text-[11px] text-zinc-500">Thanks for the feedback</span>}
                        </>
                      )}
                      {item.cached && (
                        <span className="ml-auto inline-flex items-center gap-1 text-[11px] text-zinc-500" title="A recent answer to the same question">
                          <Zap className="size-3" aria-hidden /> instant
                        </span>
                      )}
                    </div>
                  )}
                  {i === lastIndex && !busy && item.suggestions && item.suggestions.length > 0 && (
                    <ul className="flex flex-wrap gap-1.5" aria-label="Suggested follow-ups">
                      {item.suggestions.map((s) => (
                        <li key={s}>
                          <button
                            type="button"
                            onClick={() => void send(s)}
                            className="animate-fade-up rounded-full border border-emerald-500/30 bg-emerald-500/5 px-2.5 py-1 text-left text-xs text-emerald-800 transition-colors hover:bg-emerald-500/15 dark:text-emerald-200"
                          >
                            {s}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ),
            )}
          </div>

          <form onSubmit={onSubmit} className="border-t border-[var(--glass-border)] p-3">
            <div className="flex items-end gap-2 rounded-xl border border-[var(--glass-border)] bg-white/60 p-1.5 focus-within:ring-2 focus-within:ring-emerald-500/50 dark:bg-white/5">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onInputKey}
                rows={1}
                maxLength={1500}
                placeholder={voice.listening ? 'Listening…' : 'Ask about projects, skills, the models…'}
                aria-label="Ask Smith a question"
                className="field-sizing-content max-h-28 min-h-9 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-zinc-400"
              />
              {listenSupported && !busy && (
                <button
                  type="button"
                  onClick={voice.listening ? voice.stop : voice.start}
                  aria-pressed={voice.listening}
                  aria-label={voice.listening ? 'Stop listening' : 'Ask by voice'}
                  title={voice.listening ? 'Listening… click to stop' : 'Ask by voice'}
                  className={`relative grid size-9 shrink-0 place-items-center rounded-lg transition-colors ${
                    voice.listening ? 'bg-rose-500 text-white' : 'text-zinc-500 hover:bg-zinc-900/5 hover:text-zinc-900 dark:hover:bg-white/10 dark:hover:text-white'
                  }`}
                >
                  {voice.listening && <span aria-hidden className="animate-ping-slow absolute inset-0 rounded-lg bg-rose-500/50" />}
                  <Mic className="relative size-4" />
                </button>
              )}
              {busy ? (
                <button
                  type="button"
                  onClick={() => abortRef.current?.abort()}
                  className="grid size-9 shrink-0 place-items-center rounded-lg bg-zinc-200 text-zinc-800 dark:bg-white/15 dark:text-white"
                  aria-label="Stop"
                >
                  <Square className="size-3.5 fill-current" />
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!input.trim()}
                  className="grid size-9 shrink-0 place-items-center rounded-lg bg-zinc-950 text-white transition-opacity disabled:opacity-30 dark:bg-white dark:text-zinc-950"
                  aria-label="Send"
                >
                  <ArrowUp className="size-4" />
                </button>
              )}
            </div>
            {voice.error && <p className="mt-2 px-1 text-[11px] text-rose-600 dark:text-rose-400">{voice.error}</p>}
            <p className="mt-2 flex items-center justify-between gap-2 px-1 text-[11px] text-zinc-500">
              <span>Open model on Groq’s free tier. It can make mistakes.</span>
              <Link to="/smith" viewTransition className="shrink-0 font-medium text-emerald-700 hover:underline dark:text-emerald-400">
                How Smith works →
              </Link>
            </p>
          </form>
        </section>
      )}
    </>
  )
}
