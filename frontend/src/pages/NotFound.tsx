import { Link } from 'react-router-dom'
import { PageHeader } from '../components/PageHeader'

export default function NotFound() {
  return (
    <PageHeader title="Page not found">
      Nothing lives here.{' '}
      <Link to="/projects" className="font-medium text-emerald-700 hover:underline dark:text-emerald-400">
        Back to projects
      </Link>
    </PageHeader>
  )
}
