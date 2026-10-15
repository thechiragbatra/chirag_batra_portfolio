import { ArrowDown, ArrowUpRight, ExternalLink, FileText, FlaskConical, FolderGit2, Plus, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AddProjectPanel } from '../features/portfolio/AddProjectPanel'
import { CountUp } from '../components/fx/CountUp'
import { KineticText } from '../components/fx/KineticText'
import { Magnetic } from '../components/fx/Magnetic'
import { Reveal } from '../components/fx/Reveal'
import { PlannedCard } from '../features/portfolio/PlannedCard'
import highlightsData from '../data/highlights.json'
import plannedData from '../data/planned.json'
import projectsData from '../data/projects.json'
import resumeData from '../data/resume.json'
import { openSmith } from '../features/guide/client'
import type { Highlight, PlannedProject, Project, Resume } from '../types/content'

const projects: Project[] = projectsData
const highlights: Highlight[] = highlightsData
const planned: PlannedProject[] = plannedData
const resume: Resume = resumeData

// The ticker: a few of the strongest skills from each résumé group.
const TICKER = resume.skills.flatMap((g) => g.items.slice(0, 3)).slice(0, 18)

function Hero() {
  return (
    <section data-guide="hero" className="relative flex min-h-[calc(100svh-9rem)] flex-col justify-center pb-10">
      <p className="eyebrow animate-fade-up">
        {resume.basics.name} — ML engineer &amp; data scientist · {resume.basics.location}
      </p>
      <h1 className="font-display mt-6 text-[clamp(2.7rem,7.2vw,7.8rem)] leading-[0.9] font-extrabold text-white">
        <KineticText text="I build systems" delay={150} />
        <br />
        <KineticText text="that" delay={600} />{' '}
        <KineticText text="think." delay={760} by="word" unitClassName="font-serif text-aurora pr-[0.08em]" />
      </h1>
      <p
        className="animate-fade-up mt-8 max-w-xl text-lg leading-relaxed text-zinc-400"
        style={{ animationDelay: '1100ms' }}
      >
        Class of 2027 data science student shipping ML systems end to end: streaming fraud detection on AWS, causal
        uplift models, and this site&apos;s own multi-agent deployment platform, with an AI guide you can talk to.
      </p>
      <div className="animate-fade-up mt-9 flex flex-wrap gap-3" style={{ animationDelay: '1250ms' }}>
        <Magnetic>
          <a
            href="#work"
            className="shine-hover pressable group inline-flex items-center gap-2 rounded-full bg-white px-6 py-3.5 text-sm font-semibold text-zinc-950 shadow-[0_0_50px_-10px_var(--glow-a)]"
          >
            See the work <ArrowDown className="size-4 transition-transform group-hover:translate-y-0.5" aria-hidden />
          </a>
        </Magnetic>
        <button
          type="button"
          onClick={openSmith}
          className="pressable inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.04] px-6 py-3.5 text-sm font-semibold text-white backdrop-blur transition-colors hover:border-cyan-300/50"
        >
          <Sparkles className="size-4 text-cyan-300" aria-hidden /> Ask Smith
          <kbd className="ml-1 hidden rounded border border-white/15 px-1.5 font-mono text-[10px] text-zinc-400 sm:inline">⌘K</kbd>
        </button>
        <Link
          to="/resume"
          viewTransition
          className="pressable inline-flex items-center gap-2 rounded-full px-5 py-3.5 text-sm font-semibold text-zinc-300 transition-colors hover:text-white"
        >
          <FileText className="size-4" aria-hidden /> Résumé
        </Link>
      </div>

      <dl className="mt-16 grid grid-cols-2 border-t border-white/10 lg:grid-cols-4">
        {highlights.map((h, i) => (
          <Reveal
            key={h.label}
            delay={i * 110}
            className={`border-white/10 py-6 pr-4 ${i % 2 ? 'pl-4 border-l' : ''} ${i > 0 && i % 2 === 0 ? 'lg:border-l lg:pl-4' : ''} ${i > 1 ? 'border-t lg:border-t-0' : ''}`}
          >
            <dd className="font-display text-3xl font-extrabold text-white sm:text-5xl">
              <CountUp value={h.value} decimals={h.decimals} prefix={h.prefix} suffix={h.suffix} />
            </dd>
            <dt className="mt-2 max-w-[16rem] text-xs leading-snug text-zinc-500">{h.label}</dt>
          </Reveal>
        ))}
      </dl>
    </section>
  )
}

function Ticker() {
  const items = [...TICKER, ...TICKER]
  return (
    <div aria-hidden className="relative -mx-4 overflow-hidden border-y border-white/[0.07] py-5 sm:-mx-6 [mask-image:linear-gradient(90deg,transparent,#000_8%,#000_92%,transparent)]">
      <div className="marquee-track">
        {items.map((item, i) => (
          <span key={i} className="font-display flex items-center gap-8 pr-8 text-2xl font-bold whitespace-nowrap text-zinc-600 sm:text-3xl">
            {item}
            <span className="text-cyan-300/70">✦</span>
          </span>
        ))}
      </div>
    </div>
  )
}

function Scene({ project, index }: { project: Project; index: number }) {
  const flip = index % 2 === 1
  const number = String(index + 1).padStart(2, '0')
  // "RADAR: Real-time Agentic ..." shows RADAR big and the expansion as a subtitle.
  const [name, subtitle] = project.title.includes(':')
    ? [project.title.split(':')[0].trim(), project.title.split(':').slice(1).join(':').trim()]
    : [project.title, null]
  const link =
    'inline-flex items-center gap-1.5 rounded-full border border-white/12 px-4 py-2 text-sm font-medium text-zinc-200 transition-colors hover:border-white/35 hover:text-white'
  return (
    <article className="relative grid items-center gap-10 py-16 sm:py-24 lg:grid-cols-2 lg:gap-16">
      <div className={flip ? 'lg:order-2' : ''}>
        <Reveal>
          <div className="flex items-baseline gap-4">
            <span
              aria-hidden
              className="scene-index font-display text-7xl leading-none font-extrabold text-transparent [-webkit-text-stroke:1px_rgb(255_255_255/0.25)] sm:text-8xl"
            >
              {number}
            </span>
            <span className="eyebrow">{project.tags.slice(0, 2).join(' · ')}</span>
          </div>
          <h3
            className={`font-display mt-5 leading-[0.95] font-extrabold text-white ${
              name.length > 22 ? 'text-3xl sm:text-4xl' : 'text-4xl sm:text-6xl'
            }`}
          >
            {name}
          </h3>
          {subtitle && <p className="mt-3 font-serif text-2xl text-zinc-300">{subtitle}</p>}
          {project.metric && (
            <p className="mt-6 flex items-baseline gap-3">
              <span className="font-display text-aurora text-6xl font-extrabold sm:text-7xl">{project.metric.value}</span>
              <span className="max-w-[14rem] text-sm leading-snug text-zinc-400">{project.metric.label}</span>
            </p>
          )}
          <p className="mt-6 max-w-xl leading-relaxed text-zinc-400">{project.description}</p>
          <ul className="mt-6 flex flex-wrap gap-1.5" aria-label="Technologies">
            {project.tags.map((tag) => (
              <li key={tag} className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 font-mono text-[11px] text-zinc-300">
                {tag}
              </li>
            ))}
          </ul>
          <div className="mt-7 flex flex-wrap gap-2">
            {project.demo && (
              <Link
                to={project.demo}
                viewTransition
                className="shine-hover pressable inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold text-zinc-950"
              >
                <FlaskConical className="size-4" aria-hidden /> {project.demo === '/lab' ? 'Try the model' : 'Launch it'}
              </Link>
            )}
            <a href={project.githubUrl} target="_blank" rel="noreferrer" className={link}>
              <FolderGit2 className="size-4" aria-hidden /> Source
            </a>
            {project.liveUrl && (
              <a href={project.liveUrl} target="_blank" rel="noreferrer" className={link}>
                <ExternalLink className="size-4" aria-hidden /> Live
              </a>
            )}
          </div>
        </Reveal>
      </div>
      <div className={flip ? 'lg:order-1' : ''}>
        {project.diagram && (
          <div className="scene-media group relative">
            <div
              aria-hidden
              className="absolute -inset-6 -z-10 rounded-[2rem] opacity-60 blur-3xl"
              style={{ background: 'conic-gradient(from 200deg, var(--glow-a), var(--glow-b), var(--glow-c), var(--glow-a))' }}
            />
            <div className="overflow-hidden rounded-3xl border border-white/10 bg-black/40 shadow-2xl">
              <img
                src={project.diagram}
                alt={`${project.title} preview`}
                loading="lazy"
                className="aspect-video w-full object-cover transition-transform duration-[1.2s] ease-out group-hover:scale-[1.04]"
              />
            </div>
            <a
              href={project.githubUrl}
              target="_blank"
              rel="noreferrer"
              aria-label={`${project.title} on GitHub`}
              className="absolute top-4 right-4 grid size-11 place-items-center rounded-full border border-white/20 bg-black/50 text-white opacity-0 backdrop-blur transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
            >
              <ArrowUpRight className="size-5" />
            </a>
          </div>
        )}
      </div>
    </article>
  )
}

export default function Projects() {
  const [adding, setAdding] = useState(false)

  return (
    <>
      <Hero />
      <Ticker />

      <section id="work" data-guide="projects" aria-labelledby="work-heading" className="scroll-mt-28 pt-20">
        <Reveal className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="eyebrow">Selected work</p>
            <h2 id="work-heading" className="font-display mt-3 text-5xl font-extrabold text-white sm:text-7xl">
              Things I&apos;ve <span className="font-serif text-aurora">shipped</span>
            </h2>
          </div>
          {import.meta.env.DEV && !adding && (
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="inline-flex shrink-0 items-center justify-center gap-2 rounded-full border border-white/15 px-4 py-2 text-sm font-medium text-zinc-200 hover:border-white/35"
            >
              <Plus className="size-4" aria-hidden /> Add project
            </button>
          )}
        </Reveal>
        {import.meta.env.DEV && adding && <AddProjectPanel onClose={() => setAdding(false)} />}
        <div className="divide-y divide-white/[0.07]">
          {projects.map((project, i) => (
            <Scene key={project.githubUrl} project={project} index={i} />
          ))}
        </div>
      </section>

      {planned.length > 0 && (
        <section data-guide="building" aria-labelledby="building-heading" className="mt-16">
          <Reveal className="mb-10">
            <p className="eyebrow">On the bench</p>
            <h2 id="building-heading" className="font-display mt-3 text-5xl font-extrabold text-white sm:text-6xl">
              Building <span className="font-serif text-aurora">next</span>
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-relaxed text-zinc-400">
              Designed and scoped, with evaluation plans written before any code. These are works in progress, not
              finished results.
            </p>
          </Reveal>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {planned.map((project, i) => (
              <Reveal key={project.title} delay={(i % 3) * 110} variant="scan">
                <PlannedCard project={project} />
              </Reveal>
            ))}
          </div>
        </section>
      )}
    </>
  )
}
