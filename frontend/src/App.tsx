import { Navigate, Route } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import Apps from './pages/Apps'
import Deployer from './pages/Deployer'
import Lab from './pages/Lab'
import NotFound from './pages/NotFound'
import Projects from './pages/Projects'
import Resume from './pages/Resume'
import Smith from './pages/Smith'

export const routes = (
  <Route element={<Layout />}>
    <Route index element={<Navigate to="/projects" replace />} />
    <Route path="projects" element={<Projects />} />
    <Route path="lab" element={<Lab />} />
    <Route path="resume" element={<Resume />} />
    <Route path="deployer" element={<Deployer />} />
    <Route path="apps" element={<Apps />} />
    <Route path="smith" element={<Smith />} />
    <Route path="*" element={<NotFound />} />
  </Route>
)
