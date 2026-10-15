// Fast client-side check for instant feedback. The backend (agents/skills/github_url.py)
// is authoritative for deployments and rejects anything this lets through.
const GITHUB_REPO_URL =
  /^https:\/\/(?:www\.)?github\.com\/(?<owner>[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38})\/(?<repo>[A-Za-z0-9._-]{1,100}?)(?:\.git)?\/?$/

export interface GithubRepoRef {
  owner: string
  repo: string
}

export function parseGithubRepoUrl(url: string): GithubRepoRef | null {
  const groups = GITHUB_REPO_URL.exec(url.trim())?.groups
  if (!groups || groups.repo === '.' || groups.repo === '..') return null
  return { owner: groups.owner, repo: groups.repo }
}

export function isGithubRepoUrl(url: string): boolean {
  return parseGithubRepoUrl(url) !== null
}
