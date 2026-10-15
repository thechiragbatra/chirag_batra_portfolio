from agents.guide.corpus import Doc
from agents.guide.followups import MAX_SUGGESTIONS, follow_ups, starters

PROJECT = Doc("project-2", "Customer Churn MLOps", "...", "/lab", None, "https://x")
PLANNED = Doc("planned-1", "Filing Lens (planned, not built yet)", "...", "/projects", "building")


def test_project_answers_suggest_its_results_and_demo() -> None:
    items = follow_ups("Tell me about churn", ["search_portfolio"], [PROJECT], "/projects")
    assert items[0] == "Open the live Churn Lab"
    assert "What results did Customer Churn MLOps get?" in items
    assert len(items) <= MAX_SUGGESTIONS


def test_tool_specific_follow_ups_come_first() -> None:
    assert follow_ups("x", ["profile_repo"], [], "/deployer")[0] == "Deploy it"
    assert "Why is this customer at risk?" in follow_ups("x", ["score_customer"], [], "/lab")


def test_never_repeats_the_question_and_falls_back_to_page_starters() -> None:
    items = follow_ups("What did he do at IBM?", [], [], "/resume")
    assert "What did he do at IBM?" not in items
    assert items == [s for s in starters("/resume") if s != "What did he do at IBM?"][:3]
    assert follow_ups("x", [], [PLANNED], "/projects")[0] == "What has he already built?"
    assert starters("/unknown") == starters("/projects")
