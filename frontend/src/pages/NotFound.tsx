import { Link } from 'react-router-dom'
import { PageHeader } from '../components/ui/PageHeader'

export default function NotFound() {
  return (
    <PageHeader eyebrow="404" title={<span className="glitch inline-block"><span className="glitch-late text-aurora inline-block">Lost in the pipeline</span></span>}>
      Nothing lives here.{' '}
      <Link to="/projects" viewTransition className="font-medium text-emerald-700 hover:underline dark:text-emerald-400">
        Back to projects
      </Link>
    </PageHeader>
  )
}
