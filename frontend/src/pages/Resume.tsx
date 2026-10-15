import { Award, Download, ExternalLink, FolderGit2, GraduationCap, Link2, Mail, MapPin } from 'lucide-react'
import type { CSSProperties, ReactNode } from 'react'
import { Magnetic } from '../components/fx/Magnetic'
import { ScrambleText } from '../components/fx/ScrambleText'
import { Tabs, type TabItem } from '../components/ui/Tabs'
import resumeData from '../data/resume.json'
import type { Resume as ResumeData } from '../types/content'

const resume: ResumeData = resumeData

const LINK_ICONS: Record<string, typeof Mail> = { Email: Mail, GitHub: FolderGit2 }

const stagger = (i: number, step = 90): CSSProperties => ({ animationDelay: `${i * step}ms` })

/** Vertical timeline whose line draws itself downward; nodes pulse in turn. */
function Timeline({ children }: { children: ReactNode }) {
  return (
    <ol className="relative space-y-10 pl-8">
      <span
        aria-hidden
        className="animate-draw timeline-line absolute top-2 bottom-2 left-[7px] w-px origin-top bg-gradient-to-b from-emerald-400 via-cyan-400 to-violet-400"
      />
      {children}
    </ol>
  )
}

function TimelineItem({
  index,
  title,
  subtitle,
  meta,
  children,
}: {
  index: number
  title: string
  subtitle: string
  meta: string
  children?: ReactNode
}) {
  return (
    <li className="animate-fade-up relative" style={stagger(index, 220)}>
      <span aria-hidden className="absolute top-1.5 -left-8 grid size-[15px] place-items-center">
        <span className="animate-ping-slow absolute size-full rounded-full bg-emerald-400/60" style={stagger(index, 400)} />
        <span className="relative size-[9px] rounded-full bg-emerald-500 ring-4 ring-emerald-500/20" />
      </span>
      <div className="glass-strong glow-border rounded-2xl p-5">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
          <h3 className="font-display text-lg font-semibold">{title}</h3>
          <p className="shrink-0 font-mono text-xs text-emerald-700 tabular-nums dark:text-emerald-400">{meta}</p>
        </div>
        <p className="mt-0.5 text-sm text-zinc-500">{subtitle}</p>
        {children}
      </div>
    </li>
  )
}

const tabs: TabItem[] = [
  {
    id: 'experience',
    label: 'Experience',
    content: (
      <Timeline>
        {resume.experience.map((job, i) => (
          <TimelineItem
            key={`${job.company}-${job.role}`}
            index={i}
            title={job.role}
            subtitle={`${job.company} · ${job.location}`}
            meta={`${job.start} – ${job.end}`}
          >
            <ul className="mt-3 space-y-2 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
              {job.highlights.map((h) => (
                <li key={h} className="flex gap-2.5">
                  <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-gradient-to-br from-emerald-400 to-cyan-400" />
                  {h}
                </li>
              ))}
            </ul>
          </TimelineItem>
        ))}
      </Timeline>
    ),
  },
  {
    id: 'education',
    label: 'Education',
    content: (
      <div className="space-y-8">
        <Timeline>
          {resume.education.map((ed, i) => (
            <TimelineItem key={ed.school} index={i} title={ed.school} subtitle={ed.degree} meta={`${ed.start} – ${ed.end}`}>
              {ed.details && <p className="mt-2 text-sm text-zinc-500">{ed.details}</p>}
            </TimelineItem>
          ))}
        </Timeline>
        {resume.certifications.length > 0 && (
          <div>
            <h3 className="font-display mb-3 flex items-center gap-2 text-lg font-semibold">
              <Award className="size-5 text-amber-500" aria-hidden /> Certifications
            </h3>
            <ul className="grid gap-3 sm:grid-cols-3">
              {resume.certifications.map((c, i) => (
                <li
                  key={c}
                  className="glass-strong glow-border animate-fade-up rounded-2xl p-4 text-sm leading-snug text-zinc-700 dark:text-zinc-300"
                  style={stagger(i + 2, 120)}
                >
                  {c}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    ),
  },
  {
    id: 'projects',
    label: 'Projects',
    content: (
      <div className="grid gap-5 md:grid-cols-2">
        {resume.projects.map((p, i) => (
          <article key={p.name} className="glass-strong glow-border animate-fade-up flex flex-col rounded-2xl p-5" style={stagger(i, 150)}>
            <h3 className="font-display text-lg font-semibold">{p.name}</h3>
            <p className="mt-2 flex-1 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">{p.description}</p>
            <div className="mt-4 flex flex-wrap items-center gap-1.5">
              {p.tech.map((t) => (
                <span key={t} className="rounded-full border border-[var(--glass-border)] bg-white/50 px-2.5 py-0.5 font-mono text-[11px] dark:bg-white/5">
                  {t}
                </span>
              ))}
              {p.url && (
                <a href={p.url} target="_blank" rel="noreferrer" className="ml-1 inline-flex items-center gap-1 text-xs font-medium text-emerald-700 hover:underline dark:text-emerald-400">
                  <ExternalLink className="size-3.5" /> View
                </a>
              )}
            </div>
          </article>
        ))}
      </div>
    ),
  },
  {
    id: 'skills',
    label: 'Skills',
    content: (
      <dl className="grid gap-4 md:grid-cols-2">
        {resume.skills.map((group, g) => (
          <div key={group.category} className="glass-strong rounded-2xl p-5">
            <dt className="font-display mb-3 text-sm font-semibold tracking-wide">{group.category}</dt>
            <dd className="flex flex-wrap gap-1.5">
              {group.items.map((item, i) => (
                <span
                  key={item}
                  className="animate-pop cursor-default rounded-lg border border-[var(--glass-border)] bg-white/60 px-2.5 py-1 text-xs font-medium text-zinc-700 transition-all duration-200 hover:-translate-y-0.5 hover:border-emerald-400/60 hover:text-emerald-700 hover:shadow-[0_0_18px_-4px_var(--glow-a)] dark:bg-white/5 dark:text-zinc-300 dark:hover:text-emerald-300"
                  style={{ animationDelay: `${g * 80 + i * 35}ms` }}
                >
                  {item}
                </span>
              ))}
            </dd>
          </div>
        ))}
      </dl>
    ),
  },
]

export default function Resume() {
  const { basics } = resume
  return (
    <>
      <section className="glass-strong glow-border relative mb-10 overflow-hidden rounded-3xl p-6 sm:p-8" data-glow>
        <div
          aria-hidden
          className="absolute -top-24 -right-24 size-72 rounded-full opacity-40 blur-3xl"
          style={{ background: 'conic-gradient(var(--glow-a), var(--glow-b), var(--glow-c), var(--glow-a))' }}
        />
        <div className="relative flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="mb-3 font-mono text-xs tracking-[0.2em] text-emerald-600 uppercase dark:text-emerald-400">Résumé</p>
            <h1 className="font-display text-4xl font-bold sm:text-5xl">
              <ScrambleText text={basics.name} />
            </h1>
            <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-zinc-600 dark:text-zinc-400">
              <span className="inline-flex items-center gap-1.5">
                <GraduationCap className="size-4" aria-hidden /> {basics.title}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <MapPin className="size-4" aria-hidden /> {basics.location}
              </span>
            </p>
            <p className="mt-4 max-w-2xl text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">{basics.summary}</p>
            <ul className="mt-5 flex flex-wrap gap-2 text-sm">
              {basics.links.map((link) => {
                const Icon = LINK_ICONS[link.label] ?? Link2
                return (
                  <li key={link.url}>
                    <a
                      href={link.url}
                      target={link.url.startsWith('mailto:') ? undefined : '_blank'}
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 rounded-full border border-[var(--glass-border)] bg-white/60 px-3 py-1.5 font-medium transition-all hover:-translate-y-0.5 hover:border-emerald-400/60 hover:text-emerald-700 dark:bg-white/5 dark:hover:text-emerald-300"
                    >
                      <Icon className="size-4" aria-hidden /> {link.label}
                    </a>
                  </li>
                )
              })}
            </ul>
          </div>
          <Magnetic>
            <a
              href="/resume.pdf"
              download
              className="shine-hover pressable inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-zinc-950 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-emerald-500/25 transition-shadow hover:shadow-emerald-500/50 dark:bg-white dark:text-zinc-950"
            >
              <Download className="size-4" /> Download PDF
            </a>
          </Magnetic>
        </div>
      </section>
      <Tabs items={tabs} label="Resume sections" />
    </>
  )
}
