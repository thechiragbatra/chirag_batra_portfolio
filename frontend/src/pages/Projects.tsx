import { ArrowDown, ArrowUpRight, Award, ExternalLink, FileText, FlaskConical, FolderGit2, GraduationCap, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AddProjectPanel } from '../features/portfolio/AddProjectPanel'
import { CountUp } from '../components/fx/CountUp'
import { KineticText } from '../components/fx/KineticText'
import { Magnetic } from '../components/fx/Magnetic'
import { Reveal } from '../components/fx/Reveal'
import highlightsData from '../data/highlights.json'
import projectsData from '../data/projects.json'
import resumeData from '../data/resume.json'
import type { Highlight, Project, Resume } from '../types/content'

const projects: Project[] = projectsData
const highlights: Highlight[] = highlightsData
const resume: Resume = resumeData

// The ticker: a few of the strongest skills from each résumé group.
const TICKER = resume.skills.flatMap((g) => g.items.slice(0, 3)).slice(0, 18)

function Hero() {
  return (
    <section className="relative flex min-h-[calc(100svh-9rem)] flex-col justify-center pb-10">
      <p className="eyebrow animate-fade-up">
        AI Engineer candidate · B.Tech CS (Data Science), 2027 · {resume.basics.location}
      </p>
      <h1 className="font-display mt-6 text-[clamp(2.7rem,7.2vw,7.8rem)] leading-[0.9] font-extrabold text-white">
        <KineticText text="I build AI" delay={150} />
        <br />
        <KineticText text="that thinks." delay={760} by="word" unitClassName="font-serif text-aurora pr-[0.08em]" />
      </h1>
      <p
        className="animate-fade-up mt-8 max-w-xl text-lg leading-relaxed text-zinc-400"
        style={{ animationDelay: '1100ms' }}
      >
        Computer Science student building end-to-end AI products, from explainable machine learning to careful,
        retrieval-powered LLM applications.
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

function Toolkit() {
  const education = resume.education[0]

  return (
    <section id="toolkit" aria-labelledby="toolkit-heading" className="scroll-mt-28 pt-28">
      <Reveal>
        <p className="eyebrow">Skills · certifications · education</p>
        <h2 id="toolkit-heading" className="font-display mt-3 max-w-3xl text-5xl leading-[0.95] font-extrabold text-white sm:text-7xl">
          The tools behind <span className="font-serif text-aurora">the work.</span>
        </h2>
        <p className="mt-5 max-w-2xl text-sm leading-relaxed text-zinc-400">
          A practical toolkit for taking machine-learning ideas from data preparation to evaluation and deployment.
        </p>
      </Reveal>

      <div className="mt-10 grid items-start gap-8 lg:grid-cols-[1.25fr_0.75fr] lg:gap-12">
        <section aria-labelledby="skills-heading">
          <div className="mb-4 flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-xl border border-cyan-200/15 bg-cyan-200/[0.06] font-mono text-xs text-cyan-100">01</span>
            <h3 id="skills-heading" className="font-display text-xl font-semibold text-white">Technical skills</h3>
          </div>
          <dl className="grid gap-3 sm:grid-cols-2">
            {resume.skills.map((group, index) => (
              <Reveal key={group.category} delay={index * 70} className="glass-strong glow-border rounded-2xl p-4 sm:p-5">
                <dt className="font-mono text-[10px] tracking-[0.14em] text-cyan-100/75 uppercase">{group.category}</dt>
                <dd className="mt-3 flex flex-wrap gap-1.5">
                  {group.items.map((item) => (
                    <span key={item} className="rounded-full border border-white/[0.08] bg-white/[0.035] px-2.5 py-1 text-[11px] text-zinc-300">
                      {item}
                    </span>
                  ))}
                </dd>
              </Reveal>
            ))}
          </dl>
        </section>

        <div className="space-y-8">
          <section aria-labelledby="certifications-heading">
            <div className="mb-4 flex items-center gap-3">
              <span className="grid size-9 place-items-center rounded-xl border border-amber-200/15 bg-amber-200/[0.06] text-amber-100">
                <Award className="size-4" aria-hidden />
              </span>
              <h3 id="certifications-heading" className="font-display text-xl font-semibold text-white">Certifications</h3>
            </div>
            <ul className="space-y-2.5">
              {resume.certifications.map((certification, index) => (
                <li key={`${certification.issuer}-${certification.name}`} className="glass-strong flex gap-3 rounded-2xl p-4" style={{ animationDelay: `${index * 80}ms` }}>
                  <span aria-hidden className="mt-1.5 size-1.5 shrink-0 rounded-full bg-gradient-to-r from-amber-200 to-violet-300" />
                  <span>
                    <span className="block text-sm font-medium leading-snug text-zinc-100">{certification.name}</span>
                    <span className="mt-1 block font-mono text-[10px] tracking-wide text-zinc-500">
                      {certification.issuer}{certification.date ? ` · ${certification.date}` : ''}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </section>

          {education && (
            <section aria-labelledby="education-heading">
              <div className="mb-4 flex items-center gap-3">
                <span className="grid size-9 place-items-center rounded-xl border border-violet-200/15 bg-violet-200/[0.06] text-violet-100">
                  <GraduationCap className="size-4" aria-hidden />
                </span>
                <h3 id="education-heading" className="font-display text-xl font-semibold text-white">Education</h3>
              </div>
              <div className="glass-strong rounded-2xl p-5">
                <p className="font-display text-lg font-semibold text-white">{education.school}</p>
                <p className="mt-1 text-sm leading-relaxed text-zinc-300">{education.degree}</p>
                <p className="mt-3 font-mono text-[10px] tracking-[0.12em] text-zinc-500 uppercase">
                  {education.start} – {education.end}{education.details ? ` · ${education.details}` : ''}
                </p>
              </div>
            </section>
          )}
        </div>
      </div>
    </section>
  )
}

function Scene({ project, index }: { project: Project; index: number }) {
  const flip = index % 2 === 1
  const number = String(index + 1).padStart(2, '0')
  // Keep a short lead title and render the expansion as a subtitle.
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
            {project.status && (
              <span className="rounded-full border border-cyan-300/25 bg-cyan-300/[0.07] px-2.5 py-1 font-mono text-[10px] tracking-[0.12em] text-cyan-200 uppercase">
                {project.status}
              </span>
            )}
          </div>
          <h3
            className={`font-display mt-5 leading-[0.95] font-extrabold text-white ${
              name.length > 22 ? 'text-3xl sm:text-4xl' : 'text-4xl sm:text-6xl'
            }`}
          >
            {name}
          </h3>
          {subtitle && <p className="mt-3 font-serif text-2xl text-zinc-300">{subtitle}</p>}
          {project.context && <p className="mt-2 font-mono text-xs tracking-wide text-zinc-500">{project.context}</p>}
          {project.metric && (
            <p className="mt-6 flex items-baseline gap-3">
              <span className="font-display text-aurora text-6xl font-extrabold sm:text-7xl">{project.metric.value}</span>
              <span className="max-w-[14rem] text-sm leading-snug text-zinc-400">{project.metric.label}</span>
            </p>
          )}
          <p className="mt-6 max-w-xl leading-relaxed text-zinc-400">{project.description}</p>
          {(project.contribution || project.keyDecision) && (
            <dl className="mt-6 grid gap-4 border-l border-cyan-300/20 pl-4 sm:grid-cols-2 sm:gap-6">
              {project.contribution && (
                <div>
                  <dt className="font-mono text-[10px] tracking-[0.18em] text-cyan-200/75 uppercase">Contribution</dt>
                  <dd className="mt-1.5 text-sm leading-relaxed text-zinc-300">{project.contribution}</dd>
                </div>
              )}
              {project.keyDecision && (
                <div>
                  <dt className="font-mono text-[10px] tracking-[0.18em] text-violet-200/75 uppercase">Key design choice</dt>
                  <dd className="mt-1.5 text-sm leading-relaxed text-zinc-300">{project.keyDecision}</dd>
                </div>
              )}
            </dl>
          )}
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
            {project.githubUrl && (
              <a href={project.githubUrl} target="_blank" rel="noreferrer" className={link}>
                <FolderGit2 className="size-4" aria-hidden /> Source
              </a>
            )}
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
          <>
            <div className="scene-media group relative">
              <div
                aria-hidden
                className="absolute -inset-6 -z-10 rounded-[2rem] opacity-60 blur-3xl"
                style={{ background: 'conic-gradient(from 200deg, var(--glow-a), var(--glow-b), var(--glow-c), var(--glow-a))' }}
              />
              <div className="overflow-hidden rounded-3xl border border-white/10 bg-black/40 shadow-2xl">
                <img
                  src={`${import.meta.env.BASE_URL}${project.diagram.replace(/^\//, '')}`}
                  alt={project.diagramAlt ?? `${project.title} preview`}
                  loading="lazy"
                  className="aspect-video w-full object-cover transition-transform duration-[1.2s] ease-out group-hover:scale-[1.04]"
                />
              </div>
              {project.githubUrl && (
                <a
                  href={project.githubUrl}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={`${project.title} on GitHub`}
                  className="absolute top-4 right-4 grid size-11 place-items-center rounded-full border border-white/20 bg-black/50 text-white opacity-0 backdrop-blur transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
                >
                  <ArrowUpRight className="size-5" />
                </a>
              )}
            </div>
            {project.diagramCaption && <p className="mt-3 text-xs text-zinc-500">{project.diagramCaption}</p>}
          </>
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

      <section id="work" aria-labelledby="work-heading" className="scroll-mt-28 pt-20">
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
            <Scene key={project.githubUrl ?? project.title} project={project} index={i} />
          ))}
        </div>
      </section>
      <Toolkit />
    </>
  )
}
