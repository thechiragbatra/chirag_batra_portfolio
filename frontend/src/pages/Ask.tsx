import { ArrowDown, ArrowUpRight, Check, Database, RotateCcw, Search, Sparkles, Waypoints } from 'lucide-react'
import { useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { PageHeader } from '../components/ui/PageHeader'
import { extractEvidenceSentence, retrievePortfolioPassages } from '../features/portfolio/retrieval'

const PROMPTS = [
  'What did I build at IBM?',
  'How does Hireloop use RAG?',
  'How did uplift modeling reduce spend?',
  'What have I deployed?',
]

function SourceLink({ href, children }: { href: string; children: string }) {
  if (href.startsWith('http')) {
    return (
      <a href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-zinc-300 transition-colors hover:text-cyan-200">
        {children} <ArrowUpRight className="size-3" aria-hidden />
      </a>
    )
  }
  return (
    <Link to={href} viewTransition className="inline-flex items-center gap-1 text-zinc-300 transition-colors hover:text-cyan-200">
      {children} <ArrowUpRight className="size-3" aria-hidden />
    </Link>
  )
}

export default function Ask() {
  const [question, setQuestion] = useState('')
  const [submitted, setSubmitted] = useState('')
  const results = useMemo(() => (submitted ? retrievePortfolioPassages(submitted, 3) : []), [submitted])
  const excerpts = useMemo(
    () => results.slice(0, 2).map((result) => extractEvidenceSentence(result.text, submitted)),
    [results, submitted],
  )

  function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const prompt = question.trim()
    if (prompt) setSubmitted(prompt)
  }

  function choosePrompt(prompt: string) {
    setQuestion(prompt)
    setSubmitted(prompt)
  }

  return (
    <div className="ask-page pb-10">
      <PageHeader eyebrow="Portfolio RAG · Browser-only demo" title={<>Ask the <span className="font-serif text-aurora">evidence.</span></>}>
        Ask about my projects, experience, and technical decisions. Each response is assembled from portfolio passages and linked to its source.
      </PageHeader>

      <section aria-labelledby="ask-heading" className="glass-strong glow-border relative isolate overflow-hidden rounded-[2rem] p-5 sm:p-8 lg:p-10">
        <div aria-hidden className="pointer-events-none absolute -top-36 right-[-4rem] -z-10 size-96 rounded-full bg-violet-500/10 blur-[100px]" />
        <div aria-hidden className="pointer-events-none absolute -bottom-44 left-[-5rem] -z-10 size-96 rounded-full bg-cyan-400/[0.08] blur-[110px]" />

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="eyebrow">Grounded answers, traceable sources</p>
            <h2 id="ask-heading" className="font-display mt-3 text-2xl font-bold text-white sm:text-3xl">Ask my portfolio</h2>
          </div>
          <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-300/[0.06] px-3 py-1.5 font-mono text-[10px] tracking-[0.13em] text-emerald-200 uppercase">
            <span className="led size-1.5 rounded-full bg-emerald-300" /> Local index · ready
          </span>
        </div>

        <form onSubmit={ask} className="mt-8">
          <label htmlFor="portfolio-question" className="sr-only">Ask a question about Chirag’s portfolio</label>
          <div className="group flex flex-col gap-3 rounded-2xl border border-white/10 bg-black/40 p-2 transition-colors focus-within:border-cyan-200/40 sm:flex-row sm:items-center">
            <Search aria-hidden className="ml-3 hidden size-5 shrink-0 text-cyan-200 sm:block" />
            <input
              id="portfolio-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Try: What did I build at IBM?"
              className="min-w-0 flex-1 bg-transparent px-3 py-3 text-sm text-white outline-none placeholder:text-zinc-600 sm:px-1"
            />
            <button
              type="submit"
              disabled={!question.trim()}
              className="shine-hover pressable inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-zinc-950 transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
            >
              Retrieve <ArrowDown className="size-4 -rotate-90" aria-hidden />
            </button>
          </div>
        </form>

        <div className="mt-4 flex flex-wrap gap-2" aria-label="Suggested questions">
          {PROMPTS.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => choosePrompt(prompt)}
              className="rounded-full border border-white/[0.09] px-3 py-1.5 text-left text-xs text-zinc-400 transition-colors hover:border-cyan-200/30 hover:text-white"
            >
              {prompt}
            </button>
          ))}
        </div>

        <div className="mt-8 grid grid-cols-[1fr_auto_1fr_auto_1fr] items-center gap-2 sm:gap-4" aria-label="Retrieval pipeline">
          <PipelineStep icon={<Search className="size-4" />} label="Query" active={Boolean(submitted)} />
          <span aria-hidden className={`packet-track relative h-px ${submitted ? 'bg-cyan-200/20' : 'bg-white/10'}`}>
            {submitted && <span className="packet" />}
          </span>
          <PipelineStep icon={<Database className="size-4" />} label="Retrieve" active={Boolean(results.length)} />
          <span aria-hidden className={`packet-track relative h-px ${results.length ? 'bg-violet-200/20' : 'bg-white/10'}`}>
            {results.length > 0 && <span className="packet" style={{ animationDelay: '180ms' }} />}
          </span>
          <PipelineStep icon={<Sparkles className="size-4" />} label="Cite evidence" active={Boolean(results.length)} />
        </div>
      </section>

      <section aria-live="polite" aria-busy={false} className="mt-8 min-h-48">
        {!submitted ? (
          <div className="grid gap-5 rounded-3xl border border-dashed border-white/10 p-6 sm:grid-cols-[1fr_auto] sm:items-center sm:p-8">
            <div>
              <p className="eyebrow">Retrieval is ready</p>
              <p className="mt-3 max-w-xl text-sm leading-relaxed text-zinc-400">
                Choose a prompt or ask your own. The local BM25 index searches résumé and project passages, then returns the best-matching evidence with source links.
              </p>
            </div>
            <div className="hidden size-20 place-items-center rounded-full border border-cyan-200/15 bg-cyan-200/[0.04] text-cyan-100 sm:grid">
              <Waypoints className="size-8" aria-hidden />
            </div>
          </div>
        ) : results.length ? (
          <div className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
            <article className="animate-fade-up rounded-3xl border border-cyan-200/15 bg-cyan-200/[0.035] p-6 sm:p-8">
              <div className="flex items-center gap-2 font-mono text-[10px] tracking-[0.16em] text-cyan-200 uppercase">
                <Sparkles className="size-3.5" aria-hidden /> Retrieved answer
              </div>
              <p className="mt-5 font-display text-xl leading-relaxed font-semibold text-white sm:text-2xl">
                {excerpts.map((excerpt, index) => (
                  <span key={`${results[index]?.id}-${excerpt}`}>
                    {index > 0 && <span className="text-zinc-500"> </span>}
                    {excerpt}
                  </span>
                ))}
              </p>
              <p className="mt-6 border-t border-white/[0.08] pt-4 text-xs leading-relaxed text-zinc-500">
                Extractive answer · selected directly from {results.length > 1 ? 'the retrieved portfolio passages' : 'a retrieved portfolio passage'}; no external model or unsupported claims.
              </p>
            </article>

            <div className="space-y-3">
              <div className="mb-4 flex items-center justify-between gap-4">
                <div>
                  <p className="eyebrow">Evidence</p>
                  <h3 className="font-display mt-1 text-lg font-semibold text-white">Top matches</h3>
                </div>
                <button type="button" onClick={() => { setQuestion(''); setSubmitted('') }} className="inline-flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-white">
                  <RotateCcw className="size-3" aria-hidden /> Reset
                </button>
              </div>
              {results.map((result, index) => (
                <article key={result.id} className="animate-fade-up rounded-2xl border border-white/[0.08] bg-black/25 p-4 sm:p-5" style={{ animationDelay: `${index * 90}ms` }}>
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="font-mono text-[10px] tracking-[0.14em] text-violet-200/80 uppercase">{result.kind}</p>
                      <h4 className="mt-1 font-medium text-white">{result.title}</h4>
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5 font-mono text-[10px] text-zinc-500" aria-label={`Match ${Math.round((result.score / results[0].score) * 100)} percent`}>
                      <span className="size-1.5 rounded-full bg-cyan-200" />{Math.round((result.score / results[0].score) * 100)}%
                    </div>
                  </div>
                  <p className="mt-3 text-sm leading-relaxed text-zinc-400">{extractEvidenceSentence(result.text, submitted)}</p>
                  <p className="mt-3 border-t border-white/[0.06] pt-3 font-mono text-[10px] tracking-wide text-zinc-600">
                    <SourceLink href={result.href}>{result.sourceLabel}</SourceLink>
                  </p>
                </article>
              ))}
            </div>
          </div>
        ) : (
          <div className="rounded-3xl border border-amber-200/15 bg-amber-200/[0.035] p-6 sm:p-8">
            <p className="font-display text-lg font-semibold text-white">No matching passage found.</p>
            <p className="mt-2 text-sm text-zinc-400">Try a project name, technology, or result such as “IBM”, “LangGraph”, or “56%”.</p>
            <button type="button" onClick={() => { setQuestion(''); setSubmitted('') }} className="mt-4 inline-flex items-center gap-2 text-sm text-cyan-200 hover:text-white">
              <RotateCcw className="size-3.5" aria-hidden /> Ask another question
            </button>
          </div>
        )}
      </section>

      <p className="mt-10 text-center font-mono text-[10px] tracking-[0.12em] text-zinc-600 uppercase">
        Static-site safe · no API key · nothing leaves this browser
      </p>
    </div>
  )
}

function PipelineStep({ icon, label, active }: { icon: ReactNode; label: string; active: boolean }) {
  return (
    <div className={`flex min-w-0 items-center gap-2 ${active ? 'text-cyan-100' : 'text-zinc-600'}`}>
      <span className={`grid size-8 shrink-0 place-items-center rounded-full border ${active ? 'node-lock border-cyan-200/30 bg-cyan-100/[0.08]' : 'border-white/[0.08] bg-white/[0.02]'}`}>
        {active ? <Check className="size-3.5" aria-hidden /> : icon}
      </span>
      <span className="hidden truncate font-mono text-[10px] tracking-wide uppercase sm:inline">{label}</span>
    </div>
  )
}
