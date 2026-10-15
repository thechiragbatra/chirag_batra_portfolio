from agents.guide.corpus import Doc, load_corpus
from agents.guide.search import Index, stem, tokenize


def test_stem_handles_plurals_and_verb_endings() -> None:
    assert stem("models") == "model"
    assert stem("deploying") == "deploy"
    assert stem("libraries") == "library"
    assert stem("classes") == "class"
    assert stem("class") == "class"
    assert stem("aws") == "aws"  # short tokens are left alone


def test_tokenize_drops_stopwords_and_keeps_tech_tokens() -> None:
    tokens = tokenize("What is his experience with Node.js and XGBoost models?")
    assert tokens == ["experience", "node.js", "xgboost", "model"]


def test_bm25_ranks_the_matching_document_first() -> None:
    docs = (
        Doc("a", "Fraud detection", "XGBoost fraud scoring on a stream", "/projects"),
        Doc("b", "Churn", "Uplift modeling for churn retention", "/lab"),
        Doc("c", "Contact", "Email and LinkedIn", "/resume"),
    )
    index = Index(docs)
    assert [h.doc.id for h in index.search("uplift retention")] == ["b"]
    assert index.search("fraud")[0].doc.id == "a"
    assert index.search("quantum chromodynamics") == []


def test_real_corpus_is_complete_and_honest() -> None:
    docs = load_corpus()
    ids = {d.id for d in docs}
    assert {"resume-summary", "contact", "experience-1", "highlights", "lab-method"} <= ids
    planned = [d for d in docs if d.id.startswith("planned-")]
    assert planned and all("not built yet" in d.text for d in planned)
    assert all(d.page.startswith("/") for d in docs)


def test_real_corpus_search_finds_the_obvious_answers() -> None:
    index = Index(load_corpus())
    assert index.search("contact email")[0].doc.id == "contact"
    assert index.search("IBM internship")[0].doc.id in {"experience-1", "resume-summary"}
    assert any(h.doc.id == "experience-1" for h in index.search("IBM internship"))
    assert index.search("planned fine-tuning text-to-SQL")[0].doc.id.startswith("planned-")
    assert index.search("docker sandbox hardened containers")[0].doc.id == "deploysmith-sandbox"
