import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import { projectEditor } from './plugins/projectEditor.ts'

// Read .env from the repo root so frontend and backend share one file.
const envDir = '..'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, envDir, '')
  return {
    base: process.env.GITHUB_ACTIONS ? '/deploysmith/' : '/',
    plugins: [
      react(),
      tailwindcss(),
      projectEditor({
        dataFile: fileURLToPath(new URL('./src/data/projects.json', import.meta.url)),
        githubToken: env.GITHUB_TOKEN || undefined,
      }),
    ],
    envDir,
  }
})
