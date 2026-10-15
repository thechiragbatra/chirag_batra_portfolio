import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, createRoutesFromElements, RouterProvider } from 'react-router-dom'
import { routes } from './App.tsx'
import './index.css'

// The data router is what makes <Link viewTransition> run page changes through the
// View Transitions API (the plain BrowserRouter ignores it).
const router = createBrowserRouter(createRoutesFromElements(routes))

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
