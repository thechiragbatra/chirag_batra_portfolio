// Fast client-side check for instant feedback. The backend (backend/validation.py)
// is authoritative and rejects anything this lets through.
const GITHUB_REPO_URL =
  /^https:\/\/(?:www\.)?github\.com\/[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}\/[A-Za-z0-9._-]{1,100}?(?:\.git)?\/?$/

export function isGithubRepoUrl(url: string): boolean {
  return GITHUB_REPO_URL.test(url.trim())
}
