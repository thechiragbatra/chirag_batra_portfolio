import { ExternalLink, FolderGit2 } from 'lucide-react'
import type { Project } from '../types/content'
import { Tag } from './Tag'

const linkClass =
  'inline-flex items-center gap-1.5 text-sm font-medium text-zinc-700 hover:text-emerald-700 dark:text-zinc-300 dark:hover:text-emerald-400'

export function ProjectCard({ project }: { project: Project }) {
  return (
    <article className="flex flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white transition-shadow hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900">
      {project.diagram && (
        <img
          src={project.diagram}
          alt={`${project.title} architecture diagram`}
          className="aspect-video w-full border-b border-zinc-200 object-cover dark:border-zinc-800"
          loading="lazy"
        />
      )}
      <div className="flex flex-1 flex-col gap-3 p-5">
        <h2 className="text-lg font-semibold tracking-tight">{project.title}</h2>
        <p className="flex-1 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
          {project.description}
        </p>
        <ul className="flex flex-wrap gap-1.5" aria-label="Technologies">
          {project.tags.map((tag) => (
            <li key={tag}>
              <Tag>{tag}</Tag>
            </li>
          ))}
        </ul>
        <div className="flex gap-4 pt-1">
          <a href={project.githubUrl} target="_blank" rel="noreferrer" className={linkClass}>
            <FolderGit2 className="size-4" /> Source
          </a>
          {project.liveUrl && (
            <a href={project.liveUrl} target="_blank" rel="noreferrer" className={linkClass}>
              <ExternalLink className="size-4" /> Live
            </a>
          )}
        </div>
      </div>
    </article>
  )
}
