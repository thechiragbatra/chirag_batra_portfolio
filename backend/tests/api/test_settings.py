import os

from app.settings import load_env_file


def test_loads_values_without_overriding_real_env(tmp_path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n\nDS_TEST_A=one\nexport DS_TEST_B='two words'\n"
        "DS_TEST_C=\nDS_TEST_D=from-file\n"
    )
    monkeypatch.delenv("DEPLOYSMITH_NO_DOTENV", raising=False)
    for key in ("DS_TEST_A", "DS_TEST_B", "DS_TEST_C"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DS_TEST_D", "from-shell")
    assert load_env_file(env) == ["DS_TEST_A", "DS_TEST_B"]
    assert os.environ["DS_TEST_A"] == "one"
    assert os.environ["DS_TEST_B"] == "two words"
    assert "DS_TEST_C" not in os.environ  # empty means unset
    assert os.environ["DS_TEST_D"] == "from-shell"
    for key in ("DS_TEST_A", "DS_TEST_B"):
        monkeypatch.delenv(key)


def test_can_be_disabled_and_tolerates_a_missing_file(tmp_path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text("DS_TEST_E=x\n")
    monkeypatch.setenv("DEPLOYSMITH_NO_DOTENV", "1")
    assert load_env_file(env) == []
    monkeypatch.delenv("DEPLOYSMITH_NO_DOTENV")
    assert load_env_file(tmp_path / "missing") == []
