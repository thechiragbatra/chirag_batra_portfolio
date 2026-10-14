import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import Apps from './pages/Apps'
import Deployer from './pages/Deployer'
import NotFound from './pages/NotFound'
import Projects from './pages/Projects'
import Resume from './pages/Resume'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/projects" replace />} />
        <Route path="projects" element={<Projects />} />
        <Route path="resume" element={<Resume />} />
        <Route path="deployer" element={<Deployer />} />
        <Route path="apps" element={<Apps />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
