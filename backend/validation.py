"""Input validation for deployment requests (the rules live in agents/skills/github_url.py)."""

from agents.skills.github_url import normalize_github_url

__all__ = ["normalize_github_url"]
