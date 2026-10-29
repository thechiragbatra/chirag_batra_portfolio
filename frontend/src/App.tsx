import { Route } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import Lab from './pages/Lab'
import NotFound from './pages/NotFound'
import Projects from './pages/Projects'
import Resume from './pages/Resume'

export const routes = (
  <Route element={<Layout />}>
    <Route index element={<Projects />} />
    <Route path="projects" element={<Projects />} />
    <Route path="lab" element={<Lab />} />
    <Route path="resume" element={<Resume />} />
    <Route path="*" element={<NotFound />} />
  </Route>
)
