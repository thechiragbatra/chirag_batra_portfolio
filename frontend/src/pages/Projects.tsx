import { Link } from 'react-router-dom'
import { PageHeader } from '../components/PageHeader'
import { ProjectCard } from '../components/ProjectCard'
import projectsData from '../data/projects.json'
import type { Project } from '../types/content'

const projects: Project[] = projectsData

export default function Projects() {
  return (
    <>
      <PageHeader title="Projects">
        Things I&apos;ve built. Try the{' '}
        <Link to="/deployer" className="font-medium text-emerald-700 hover:underline dark:text-emerald-400">
          deployer
        </Link>{' '}
        to see the agent pipeline run live.
      </PageHeader>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((project) => (
          <ProjectCard key={project.title} project={project} />
        ))}
      </div>
    </>
  )
}
