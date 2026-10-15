import { ArrowRight, FileText, Plus, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AddProjectPanel } from '../components/AddProjectPanel'
import { AgentOrbit } from '../components/AgentOrbit'
import { CountUp } from '../components/fx/CountUp'
import { Magnetic } from '../components/fx/Magnetic'
import { Reveal } from '../components/fx/Reveal'
import { ScrambleText } from '../components/fx/ScrambleText'
import { TypeCycle } from '../components/fx/TypeCycle'
import { PlannedCard } from '../components/PlannedCard'
import { ProjectCard } from '../components/ProjectCard'
import highlightsData from '../data/highlights.json'
import plannedData from '../data/planned.json'
import projectsData from '../data/projects.json'
import resumeData from '../data/resume.json'
import type { Highlight, PlannedProject, Project, Resume } from '../types/content'

const projects: Project[] = projectsData
const highlights: Highlight[] = highlightsData
const planned: PlannedProject[] = plannedData
const resume: Resume = resumeData

const BUILDS = ['real-time ML systems', 'LLM agents', 'causal uplift models', 'self-healing deployers']

function Hero() {
  return (
    <section data-guide="hero" className="mb-20 grid items-center gap-12 lg:grid-cols-[1.25fr_1fr]">
      <div>
        <p className="animate-fade-up glass mb-6 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium text-zinc-700 dark:text-zinc-300">
          <Sparkles className="size-3.5 text-emerald-500" aria-hidden />
          {resume.basics.title} · {resume.basics.location}
        </p>
        <h1 className="font-display text-5xl leading-[0.95] font-bold sm:text-7xl">
          <ScrambleText text={resume.basics.name.split(' ')[0]} className="block" />
          <ScrambleText text={resume.basics.name.split(' ').slice(1).join(' ')} duration={1600} className="text-aurora block" />
        </h1>
        <p
          className="animate-fade-up mt-6 min-h-[2lh] font-mono text-lg text-zinc-700 sm:min-h-0 sm:text-xl dark:text-zinc-300"
          style={{ animationDelay: '300ms' }}
        >
          <span className="text-emerald-600 dark:text-emerald-400">&gt;</span> I build{' '}
          <TypeCycle phrases={BUILDS} className="font-semibold text-zinc-950 dark:text-white" />
        </p>
        <p
          className="animate-fade-up mt-4 max-w-xl leading-relaxed text-zinc-600 dark:text-zinc-400"
          style={{ animationDelay: '450ms' }}
        >
          Class of 2027 data science student who builds ML systems end to end: streaming fraud
          detection on AWS, causal uplift modeling, and this site&apos;s own multi-agent deployment
          pipeline. Looking for ML engineering and data science roles.
        </p>
        <div className="animate-fade-up mt-8 flex flex-wrap gap-3" style={{ animationDelay: '600ms' }}>
          <Magnetic>
            <Link
              to="/deployer"
              viewTransition
              className="shine-hover pressable group inline-flex items-center gap-2 rounded-xl bg-zinc-950 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-emerald-500/20 transition-shadow hover:shadow-emerald-500/40 dark:bg-white dark:text-zinc-950"
            >
              Launch the deployer
              <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" aria-hidden />
            </Link>
          </Magnetic>
          <Magnetic>
            <Link
              to="/resume"
              viewTransition
              className="glass inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold transition-colors hover:bg-white/80 dark:hover:bg-white/10"
            >
              <FileText className="size-4" aria-hidden /> Read résumé
            </Link>
          </Magnetic>
        </div>
      </div>
      <div className="animate-blur-in hidden sm:block" style={{ animationDelay: '250ms' }}>
        <AgentOrbit />
      </div>

      <dl className="grid grid-cols-2 gap-3 lg:col-span-2 lg:grid-cols-4">
        {highlights.map((h, i) => (
          <Reveal key={h.label} delay={i * 110} variant="scan" className="glass-strong glow-border rounded-2xl p-4">
            <dd className="font-display text-3xl font-bold sm:text-4xl">
              <span className="text-aurora">
                <CountUp value={h.value} decimals={h.decimals} prefix={h.prefix} suffix={h.suffix} />
              </span>
            </dd>
            <dt className="mt-1 text-xs leading-snug text-zinc-600 dark:text-zinc-400">{h.label}</dt>
          </Reveal>
        ))}
      </dl>
    </section>
  )
}

export default function Projects() {
  const [adding, setAdding] = useState(false)

  return (
    <>
      <Hero />
      <section data-guide="projects" aria-labelledby="work-heading">
        <Reveal className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="mb-2 font-mono text-xs tracking-[0.2em] text-emerald-600 uppercase dark:text-emerald-400">
              Selected work
            </p>
            <h2 id="work-heading" className="font-display text-3xl font-bold sm:text-4xl">
              Projects
            </h2>
          </div>
          {import.meta.env.DEV && !adding && (
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="glass inline-flex shrink-0 items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors hover:bg-white/80 dark:hover:bg-white/10"
            >
              <Plus className="size-4" aria-hidden /> Add project
            </button>
          )}
        </Reveal>
        {import.meta.env.DEV && adding && <AddProjectPanel onClose={() => setAdding(false)} />}
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project, i) => (
            <Reveal key={project.githubUrl} delay={(i % 3) * 110} variant="scan">
              <ProjectCard project={project} />
            </Reveal>
          ))}
        </div>
      </section>

      {planned.length > 0 && (
        <section data-guide="building" aria-labelledby="building-heading" className="mt-20">
          <Reveal className="mb-8">
            <p className="mb-2 font-mono text-xs tracking-[0.2em] text-violet-600 uppercase dark:text-violet-400">
              On the bench
            </p>
            <h2 id="building-heading" className="font-display text-3xl font-bold sm:text-4xl">
              Currently building
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
              Designed and scoped, with evaluation plans written before any code. These are works in
              progress, not finished results.
            </p>
          </Reveal>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
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
