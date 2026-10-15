import json

from agents.guide.feedback import draft_cases, read_feedback


def test_only_thumbs_down_become_drafts_one_per_question(tmp_path) -> None:
    path = tmp_path / "feedback.jsonl"
    lines = [
        {"id": "a" * 32, "rating": "up", "question": "Good?", "answer": "yes"},
        {"id": "b" * 32, "rating": "down", "question": "What is his GPA?", "answer": "8.5"},
        {
            "id": "c" * 32,
            "rating": "down",
            "question": "what is his gpa?",
            "answer": "9.0",
            "page": "/resume",
        },
    ]
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    drafts = draft_cases(read_feedback(path))
    assert len(drafts) == 1
    assert drafts[0]["_disliked_answer"] == "9.0" and drafts[0]["page"] == "/resume"
    assert drafts[0]["id"] == "feedback-cccccccc"


def test_missing_file_means_no_feedback(tmp_path) -> None:
    assert read_feedback(tmp_path / "none.jsonl") == []
