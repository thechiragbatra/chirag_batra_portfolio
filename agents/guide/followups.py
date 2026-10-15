"""Follow-up suggestions after each answer, chosen from what the agent just did.

Deterministic (no extra model call), so they cost nothing against the free-tier quota.
"""

from __future__ import annotations

from agents.guide.corpus import Doc

# Starter questions per page, shown before the first message and as fallbacks.
PAGE_STARTERS: dict[str, tuple[str, ...]] = {
    "/projects": (
        "What has Chirag built with machine learning?",
        "Which project best shows his LLM skills?",
        "What is he building next?",
    ),
    "/lab": (
        "What am I looking at?",
        "Why is this customer at risk?",
        "What if this customer signed a two-year contract?",
    ),
    "/resume": (
        "What did he do at IBM?",
        "What are his strongest ML skills?",
        "How can I contact him?",
    ),
    "/deployer": (
        "How does DeploySmith deploy a repo?",
        "How is untrusted code kept contained?",
        "Deploy https://github.com/octocat/Spoon-Knife",
    ),
    "/apps": (
        "How does the sandbox engine work?",
        "How does rollback work?",
        "What can DeploySmith deploy?",
    ),
}
MAX_SUGGESTIONS = 3


def starters(page: str) -> list[str]:
    return list(PAGE_STARTERS.get(page, PAGE_STARTERS["/projects"]))


def follow_ups(question: str, tools: list[str], cited: list[Doc], page: str) -> list[str]:
    ideas: list[str] = []
    if "score_customer" in tools or "describe_view" in tools:
        ideas += [
            "Why is this customer at risk?",
            "What if they paid by automatic bank transfer?",
            "Which customers should get the offer?",
        ]
    if "profile_repo" in tools:
        ideas += ["Deploy it", "How is untrusted code kept contained?"]
    if "start_deployment" in tools:
        ideas += ["What do the four agents do?", "How does the healer fix failures?"]
    for doc in cited:
        if doc.id.startswith("planned-"):
            ideas.append("What has he already built?")
        elif doc.id.startswith("project-"):
            name = doc.title.split(":")[0]
            if doc.page == "/lab":
                ideas.append("Open the live Churn Lab")
            ideas.append(f"What results did {name} get?")
            ideas.append(f"What tech does {name} use?")
        elif doc.id.startswith("experience-"):
            ideas.append("What projects has he built?")
        elif doc.id.startswith("skills-"):
            ideas.append("Which project shows these skills best?")
    ideas += starters(page)

    asked = question.strip().lower().rstrip("?")
    out: list[str] = []
    for idea in ideas:
        if idea.lower().rstrip("?") != asked and idea not in out:
            out.append(idea)
        if len(out) == MAX_SUGGESTIONS:
            break
    return out
