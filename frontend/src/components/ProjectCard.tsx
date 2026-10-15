import { ArrowUpRight, ExternalLink, FlaskConical, FolderGit2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Project } from '../types/content'
import { TiltCard } from './fx/TiltCard'

const linkClass =
  'relative z-[3] inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-sm font-medium text-zinc-700 transition-colors hover:bg-emerald-500/10 hover:text-emerald-700 dark:text-zinc-300 dark:hover:text-emerald-300'

export function ProjectCard({ project }: { project: Project }) {
  return (
    <TiltCard>
      <article className="glass-strong flex h-full flex-col overflow-hidden rounded-2xl">
        {project.diagram ? (
          <div className="overflow-hidden border-b border-[var(--glass-border)]">
            <img
              src={project.diagram}
              alt={`${project.title} preview`}
              className="aspect-video w-full object-cover transition-transform duration-700 ease-out group-hover/tilt:scale-[1.06]"
              loading="lazy"
            />
          </div>
        ) : (
          <div
            aria-hidden
            className="relative aspect-[16/6] overflow-hidden border-b border-[var(--glass-border)]"
          >
            <div
              className="absolute inset-0 opacity-60 transition-transform duration-700 group-hover/tilt:scale-125 group-hover/tilt:rotate-6"
              style={{
                background: `conic-gradient(from ${(project.title.length * 37) % 360}deg at 30% 60%, var(--glow-a), var(--glow-b), var(--glow-c), var(--glow-a))`,
                filter: 'blur(28px)',
              }}
            />
            <span className="font-display absolute bottom-3 left-5 text-5xl font-bold text-white/80 mix-blend-overlay">
              {project.title
                .split(/\s+/)
                .filter((w) => /^[A-Za-z]/.test(w))
                .slice(0, 2)
                .map((w) => w[0])
                .join('')}
            </span>
          </div>
        )}
        <div className="flex flex-1 flex-col gap-3 p-5" style={{ transform: 'translateZ(30px)' }}>
          <h2 className="font-display flex items-start justify-between gap-2 text-lg font-semibold">
            {project.title}
            <ArrowUpRight
              aria-hidden
              className="size-5 shrink-0 text-zinc-400 transition-all duration-300 group-hover/tilt:-translate-y-0.5 group-hover/tilt:translate-x-0.5 group-hover/tilt:text-emerald-500"
            />
          </h2>
          <p className="flex-1 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
            {project.description}
          </p>
          <ul className="flex flex-wrap gap-1.5" aria-label="Technologies">
            {project.tags.map((tag) => (
              <li
                key={tag}
                className="rounded-full border border-[var(--glass-border)] bg-white/50 px-2.5 py-0.5 font-mono text-[11px] text-zinc-700 dark:bg-white/5 dark:text-zinc-300"
              >
                {tag}
              </li>
            ))}
          </ul>
          <div className="-ml-2 flex gap-2 pt-1">
            <a href={project.githubUrl} target="_blank" rel="noreferrer" className={linkClass}>
              <FolderGit2 className="size-4" /> Source
            </a>
            {project.demo && (
              <Link to={project.demo} viewTransition className={`${linkClass} text-emerald-700 dark:text-emerald-400`}>
                <FlaskConical className="size-4" /> Try the model
              </Link>
            )}
            {project.liveUrl && (
              <a href={project.liveUrl} target="_blank" rel="noreferrer" className={linkClass}>
                <ExternalLink className="size-4" /> Live
              </a>
            )}
          </div>
        </div>
      </article>
    </TiltCard>
  )
}
