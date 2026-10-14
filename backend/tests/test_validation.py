import pytest

from validation import normalize_github_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/acme/shop", "https://github.com/acme/shop"),
        ("https://github.com/acme/shop/", "https://github.com/acme/shop"),
        ("https://github.com/acme/shop.git", "https://github.com/acme/shop"),
        ("https://www.github.com/acme/shop", "https://github.com/acme/shop"),
        ("  https://github.com/a-b/my_repo.v2  ", "https://github.com/a-b/my_repo.v2"),
        ("https://github.com/x/.github", "https://github.com/x/.github"),
    ],
)
def test_accepts_github_repo_urls(url: str, expected: str) -> None:
    assert normalize_github_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "github.com/acme/shop",
        "http://github.com/acme/shop",
        "git@github.com:acme/shop.git",
        "https://gitlab.com/acme/shop",
        "https://github.com.evil.com/acme/shop",
        "https://evil.com/github.com/acme/shop",
        "https://github.com/acme",
        "https://github.com/acme/shop/tree/main",
        "https://github.com/acme/shop?tab=readme",
        "https://github.com/acme/shop#readme",
        "https://github.com/-acme/shop",
        "https://github.com/ac--me/shop",
        "https://github.com/acme/sh op",
        "https://github.com/acme/..",
        "https://user:pass@github.com/acme/shop",
    ],
)
def test_rejects_non_repo_urls(url: str) -> None:
    with pytest.raises(ValueError):
        normalize_github_url(url)
