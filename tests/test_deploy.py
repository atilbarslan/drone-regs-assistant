"""render.yaml stays consistent with the app: settings it sets exist and parse, and the start
command keeps the choices the app depends on."""

import re
from pathlib import Path

import yaml

from app.config import Settings

ROOT = Path(__file__).resolve().parent.parent
SERVICE = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))["services"][0]
ENV = {item["key"]: item for item in SERVICE["envVars"]}


def test_start_command():
    command = SERVICE["startCommand"].split()
    assert command[:3] == ["uvicorn", "--factory", "app.main:create_app"]
    assert command[command.index("--workers") + 1] == "1"  # limits are counted in memory
    assert "--no-access-log" in command  # no client addresses in the platform's console
    assert "--no-proxy-headers" in command and "--proxy-headers" not in command
    assert command[command.index("--port") + 1] == "$PORT"


def test_service_basics():
    assert (SERVICE["runtime"], SERVICE["plan"], SERVICE["region"]) == (
        "python",
        "free",
        "frankfurt",
    )
    assert SERVICE["healthCheckPath"] == "/health"


def test_secrets_are_not_in_the_file():
    for key in ("DATABASE_URL", "GEMINI_API_KEY"):
        assert ENV[key] == {"key": key, "sync": False}


def test_settings_in_the_file_exist_and_parse():
    values = {
        key.lower(): item["value"]
        for key, item in ENV.items()
        if "value" in item and key != "PYTHON_VERSION"
    }
    assert set(values) <= set(Settings.model_fields)
    settings = Settings(_env_file=None, database_url="postgresql://x@localhost/x", **values)
    assert settings.api_docs is False and settings.hsts is True


def test_python_version_matches_ci():
    pinned = ENV["PYTHON_VERSION"]["value"]
    assert re.fullmatch(r"3\.12\.\d+", pinned)  # fully qualified, as Render requires
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert 'python-version: "3.12"' in ci
