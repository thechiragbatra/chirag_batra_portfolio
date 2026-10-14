import os
from pathlib import Path

import pytest

from agents.skills.analyze import (
    MAX_FILE_BYTES,
    analyze_repo,
    parse_env_names,
    parse_pyproject,
    parse_requirements,
    read_text,
)
from tests.repo_fixtures import VITE_FASTAPI_MONOREPO, write


def by_name(profile):
    return {c.name: c for c in profile.components}


def test_monorepo_frontend_backend_and_database(tmp_path: Path) -> None:
    profile = analyze_repo(write(tmp_path, VITE_FASTAPI_MONOREPO), "acme/shop")
    components = by_name(profile)

    assert set(components) == {"frontend", "api", "db"}
    web, api, db = components["frontend"], components["api"], components["db"]
    assert (web.kind, web.framework, web.path, web.build_command) == (
        "frontend",
        "vite",
        "frontend",
        "npm run build",
    )
    assert (api.kind, api.framework, api.path) == ("backend", "fastapi", "api")
    assert api.build_command == "pip install -r requirements.txt"
    assert api.start_command == "uvicorn main:app --host 0.0.0.0 --port $PORT"
    assert api.port == 8000
    assert (db.kind, db.framework) == ("database", "postgres")

    assert profile.default_branch == "develop"
    # Repo root first, then component dirs in discovery order (alphabetical).
    assert profile.env_vars == ["DATABASE_URL", "SECRET_KEY", "VITE_API_URL"]
    assert profile.frameworks == ["fastapi", "vite"]
    assert set(profile.languages) >= {"TypeScript", "Python"}


def test_env_example_values_are_never_kept(tmp_path: Path) -> None:
    profile = analyze_repo(write(tmp_path, VITE_FASTAPI_MONOREPO), "acme/shop")
    assert "secret" not in profile.model_dump_json()


def test_next_app_at_root(tmp_path: Path) -> None:
    write(tmp_path, {
        "package.json": {"scripts": {"build": "next build", "start": "next start"},
                         "dependencies": {"next": "15", "react": "19"}},
        "pnpm-lock.yaml": "",
    })  # fmt: skip
    (component,) = analyze_repo(tmp_path, "acme/site").components
    assert (component.name, component.kind, component.framework) == ("web", "frontend", "next")
    assert component.build_command == "pnpm run build"


def test_express_backend_with_mongo(tmp_path: Path) -> None:
    manifest = {
        "scripts": {"start": "node index.js"},
        "dependencies": {"express": "4", "mongoose": "8"},
    }
    write(tmp_path, {"package.json": manifest})
    components = by_name(analyze_repo(tmp_path, "acme/api"))
    assert components["api"].framework == "express"
    assert components["api"].start_command == "npm start"
    assert components["db"].framework == "mongodb"


def test_bare_react_package_is_a_library_not_a_site(tmp_path: Path) -> None:
    write(tmp_path, {
        "packages/emails/package.json": {"dependencies": {"react": "19"}},
        "web/package.json": {"scripts": {"build": "vite build"}, "devDependencies": {"vite": "8"}},
    })  # fmt: skip
    assert [c.name for c in analyze_repo(tmp_path, "acme/x").components] == ["web"]


def test_streamlit_entry_with_nonstandard_name_is_named_app(tmp_path: Path) -> None:
    write(tmp_path, {"requirements.txt": "streamlit\n", "streamlit_app.py": "import streamlit\n"})
    (component,) = analyze_repo(tmp_path, "acme/dash").components
    assert component.name == "app"
    assert component.start_command == (
        "streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0"
    )


@pytest.mark.parametrize(
    ("files", "framework", "start", "port"),
    [
        (
            {"requirements.txt": "streamlit\npandas\n", "app.py": "import streamlit as st\n"},
            "streamlit",
            "streamlit run app.py --server.port $PORT --server.address 0.0.0.0",
            8501,
        ),
        (
            {
                "requirements.txt": "Flask==3.0\n",
                "app.py": "from flask import Flask\napp = Flask(__name__)\n",
            },
            "flask",
            "gunicorn app:app --bind 0.0.0.0:$PORT",
            8000,
        ),
        (
            {"requirements.txt": "Django>=5\n", "manage.py": "", "mysite/wsgi.py": ""},
            "django",
            "gunicorn mysite.wsgi --bind 0.0.0.0:$PORT",
            8000,
        ),
        (
            {
                "pyproject.toml": '[project]\nname = "x"\ndependencies = ["gradio>=4"]\n',
                "app.py": "import gradio as gr\n",
            },
            "gradio",
            "python app.py",
            7860,
        ),
    ],
)
def test_python_frameworks(tmp_path: Path, files, framework, start, port) -> None:
    (component,) = analyze_repo(write(tmp_path, files), "acme/app").components
    assert (component.kind, component.framework, component.start_command, component.port) == (
        "backend",
        framework,
        start,
        port,
    )


def test_static_site_and_dockerfile_fallbacks(tmp_path: Path) -> None:
    static = analyze_repo(write(tmp_path / "s", {"index.html": "<h1>hi</h1>"}), "a/s")
    assert [(c.kind, c.framework) for c in static.components] == [("frontend", "static")]
    docker = analyze_repo(write(tmp_path / "d", {"Dockerfile": "FROM scratch"}), "a/d")
    assert [(c.kind, c.framework) for c in docker.components] == [("backend", "docker")]


def test_library_repo_is_not_deployable(tmp_path: Path) -> None:
    write(tmp_path, {"pyproject.toml": '[project]\nname = "lib"\ndependencies = ["requests"]\n'})
    with pytest.raises(ValueError, match="No deployable app"):
        analyze_repo(tmp_path, "acme/lib")


def test_workspace_root_and_vendored_dirs_are_skipped(tmp_path: Path) -> None:
    write(tmp_path, {
        "package.json": {"workspaces": ["apps/*"], "dependencies": {"react": "19"}},
        "node_modules/express/package.json": {"dependencies": {"express": "4"}},
        "apps/web/package.json": {"dependencies": {"vite": "8"}},
    })  # fmt: skip
    profile = analyze_repo(tmp_path, "acme/mono")
    assert [(c.name, c.path) for c in profile.components] == [("web", "apps/web")]


def test_symlinks_are_never_followed(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    write(outside, {"package.json": {"dependencies": {"express": "4"}}, "secret.txt": "TOKEN"})
    repo = write(tmp_path / "repo", {"index.html": "<p>"})
    os.symlink(outside / "package.json", repo / "package.json")
    os.symlink(outside, repo / "linked-dir")

    assert read_text(repo, "package.json") is None
    assert read_text(repo, "linked-dir/secret.txt") is None
    assert read_text(repo, "../outside/secret.txt") is None
    profile = analyze_repo(repo, "acme/evil")
    assert [c.framework for c in profile.components] == ["static"]


def test_oversized_files_are_skipped(tmp_path: Path) -> None:
    write(tmp_path, {"requirements.txt": "fastapi\n" + "#" * MAX_FILE_BYTES})
    assert read_text(tmp_path, "requirements.txt") is None


def test_parsers() -> None:
    assert parse_requirements("Django>=5\n-r base.txt\nuvicorn[standard]  # x\n\n") == {
        "django", "uvicorn"
    }  # fmt: skip
    assert parse_pyproject('[tool.poetry.dependencies]\npython = "^3.11"\nFastAPI = "*"\n') == {
        "fastapi"
    }
    assert parse_pyproject("not = [valid") == set()
    assert parse_env_names("A=1\n# B=2\nexport C_D=3\nlower=4\n  E =5") == ["A", "C_D", "E"]
