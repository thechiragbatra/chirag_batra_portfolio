import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AddProjectPanel } from '../components/AddProjectPanel'
import { PageHeader } from '../components/PageHeader'
import { ProjectCard } from '../components/ProjectCard'
import projectsData from '../data/projects.json'
import type { Project } from '../types/content'

const projects: Project[] = projectsData

export default function Projects() {
  const [adding, setAdding] = useState(false)

  return (
    <>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <PageHeader title="Projects">
          Things I&apos;ve built. Try the{' '}
          <Link to="/deployer" className="font-medium text-emerald-700 hover:underline dark:text-emerald-400">
            deployer
          </Link>{' '}
          to see the agent pipeline run live.
        </PageHeader>
        {import.meta.env.DEV && !adding && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="mb-8 inline-flex shrink-0 items-center justify-center gap-2 rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
          >
            <Plus className="size-4" aria-hidden /> Add project
          </button>
        )}
      </div>
      {import.meta.env.DEV && adding && <AddProjectPanel onClose={() => setAdding(false)} />}
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((project) => (
          <ProjectCard key={project.githubUrl} project={project} />
        ))}
      </div>
    </>
  )
}
