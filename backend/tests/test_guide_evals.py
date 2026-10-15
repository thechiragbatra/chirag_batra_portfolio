from guide_fakes import ScriptedModel, Turn

from agents.guide.evals import Transcript, evaluate, grade, load_cases, summary


def test_cases_are_well_formed() -> None:
    cases = load_cases()
    assert len(cases) >= 20
    assert len({c["id"] for c in cases}) == len(cases)
    assert {c["group"] for c in cases} == {"facts", "honesty", "off-topic", "tools"}
    known = {
        "id",
        "group",
        "question",
        "cite_any",
        "contain_any",
        "not_match",
        "tools",
        "no_tools",
        "network",
        "page",
        "view",
    }
    assert all(set(c) <= known for c in cases)


def test_grade_checks_citations_content_and_tools() -> None:
    case = {
        "id": "x",
        "group": "facts",
        "cite_any": ["contact"],
        "contain_any": ["gmail"],
        "tools": ["open_page"],
    }
    good = Transcript(
        "Email him at a@gmail.com [S1].", ["search_portfolio", "open_page"], {"contact"}
    )
    assert grade(case, good).passed
    bad = grade(case, Transcript("No idea.", ["search_portfolio"], set()))
    assert not bad.passed and len(bad.failures) == 3


def test_grade_catches_fabrication_and_off_topic_tool_use() -> None:
    case = {
        "id": "y",
        "group": "honesty",
        "not_match": [r"\b[1-9]\d*\+? years of (professional|work) experience"],
    }
    assert not grade(case, Transcript("He has 5 years of professional experience.")).passed
    assert grade(case, Transcript("He is a student with two internships.")).passed
    off = {"id": "z", "group": "off-topic", "no_tools": True}
    assert not grade(off, Transcript("Sure!", ["score_customer"])).passed
    assert not grade(off, Transcript("   ")).passed


async def test_evaluate_runs_cases_through_the_agent() -> None:
    model = ScriptedModel(
        Turn(calls=[("search_portfolio", {"query": "contact email"})]),
        Turn(text="Email batrachirag1123@gmail.com [S1]."),
    )
    case = {
        "id": "contact",
        "group": "facts",
        "question": "How do I contact him?",
        "cite_any": ["contact"],
    }
    [verdict] = await evaluate(model, [case], pause=0)
    assert verdict.passed, verdict.failures
    assert "facts         1/1" in summary([verdict])


def test_grade_treats_curly_and_straight_apostrophes_alike() -> None:
    case = {"id": "g", "group": "honesty", "contain_any": ["isn't listed"]}
    assert grade(case, Transcript("His GPA isn’t listed here.")).passed
