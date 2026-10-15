"""GitHub repository URL validation, shared by the deployment API and the guide agent."""

from __future__ import annotations

import re

# Owner: GitHub username/org rules (alphanumeric + single hyphens, max 39).
# Repo: letters, digits, '.', '_', '-' (max 100). Optional '.git' and trailing slash.
_GITHUB_REPO_URL = re.compile(
    r"^https://(?:www\.)?github\.com/"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38})/"
    r"(?P<repo>[A-Za-z0-9._-]{1,100}?)"
    r"(?:\.git)?/?$"
)


def normalize_github_url(url: str) -> str:
    """Validate a public GitHub repo URL and return it as https://github.com/owner/repo.

    Raises ValueError for anything else: other hosts, schemes, sub-paths
    (/tree/main, /issues), query strings, or malformed owner/repo names.
    """
    match = _GITHUB_REPO_URL.match(url.strip())
    if match is None:
        raise ValueError("repo_url must look like https://github.com/<owner>/<repo>")
    owner, repo = match["owner"], match["repo"]
    if repo in {".", ".."}:
        raise ValueError("repo_url has an invalid repository name")
    return f"https://github.com/{owner}/{repo}"
