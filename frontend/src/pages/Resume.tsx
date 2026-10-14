import { Download, ExternalLink } from 'lucide-react'
import type { ReactNode } from 'react'
import { Tabs, type TabItem } from '../components/Tabs'
import { Tag } from '../components/Tag'
import resumeData from '../data/resume.json'
import type { Resume as ResumeData } from '../types/content'

const resume: ResumeData = resumeData

function Entry({ title, meta, children }: { title: string; meta?: string; children?: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <div className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
        <h3 className="font-semibold">{title}</h3>
        {meta && <p className="shrink-0 text-sm tabular-nums text-zinc-500">{meta}</p>}
      </div>
      {children}
    </div>
  )
}

const tabs: TabItem[] = [
  {
    id: 'experience',
    label: 'Experience',
    content: (
      <div className="space-y-8">
        {resume.experience.map((job) => (
          <Entry key={`${job.company}-${job.role}`} title={`${job.role} · ${job.company}`} meta={`${job.start} – ${job.end}`}>
            <p className="text-sm text-zinc-500">{job.location}</p>
            <ul className="list-disc space-y-1 pl-5 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
              {job.highlights.map((h) => (
                <li key={h}>{h}</li>
              ))}
            </ul>
          </Entry>
        ))}
      </div>
    ),
  },
  {
    id: 'education',
    label: 'Education',
    content: (
      <div className="space-y-8">
        {resume.education.map((ed) => (
          <Entry key={ed.school} title={ed.school} meta={`${ed.start} – ${ed.end}`}>
            <p className="text-sm text-zinc-700 dark:text-zinc-300">{ed.degree}</p>
            {ed.details && <p className="text-sm text-zinc-500">{ed.details}</p>}
          </Entry>
        ))}
      </div>
    ),
  },
  {
    id: 'projects',
    label: 'Projects',
    content: (
      <div className="space-y-8">
        {resume.projects.map((p) => (
          <Entry key={p.name} title={p.name}>
            <p className="text-sm text-zinc-700 dark:text-zinc-300">{p.description}</p>
            <div className="flex flex-wrap items-center gap-1.5">
              {p.tech.map((t) => (
                <Tag key={t}>{t}</Tag>
              ))}
              {p.url && (
                <a href={p.url} target="_blank" rel="noreferrer" className="ml-1 inline-flex items-center gap-1 text-xs font-medium text-emerald-700 hover:underline dark:text-emerald-400">
                  <ExternalLink className="size-3.5" /> View
                </a>
              )}
            </div>
          </Entry>
        ))}
      </div>
    ),
  },
  {
    id: 'skills',
    label: 'Skills',
    content: (
      <dl className="space-y-5">
        {resume.skills.map((group) => (
          <div key={group.category} className="sm:grid sm:grid-cols-[10rem_1fr] sm:gap-4">
            <dt className="mb-2 text-sm font-semibold sm:mb-0 sm:pt-0.5">{group.category}</dt>
            <dd className="flex flex-wrap gap-1.5">
              {group.items.map((item) => (
                <Tag key={item}>{item}</Tag>
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
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{basics.name}</h1>
          <p className="mt-1 text-zinc-600 dark:text-zinc-400">
            {basics.title} · {basics.location}
          </p>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">{basics.summary}</p>
          <ul className="mt-3 flex flex-wrap gap-4 text-sm">
            {basics.links.map((link) => (
              <li key={link.url}>
                <a href={link.url} target="_blank" rel="noreferrer" className="font-medium text-emerald-700 hover:underline dark:text-emerald-400">
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </div>
        <a
          href="/resume.pdf"
          download
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          <Download className="size-4" /> Download PDF
        </a>
      </div>
      <Tabs items={tabs} label="Resume sections" />
    </>
  )
}
