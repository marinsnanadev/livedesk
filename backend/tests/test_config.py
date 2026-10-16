import pytest
from fastapi.testclient import TestClient

from app.config import DEFAULT_AGENT_TOKEN, load_settings, normalize_database_url
from app.main import app


def test_postgres_scheme_is_rewritten_for_sqlalchemy():
    # Regression test: Render and Heroku hand out postgres://, which
    # SQLAlchemy 2 refuses ("Can't load plugin: sqlalchemy.dialects:postgres").
    assert normalize_database_url("postgres://u:p@host:5432/db") == "postgresql://u:p@host:5432/db"
    assert normalize_database_url("postgresql://u:p@host/db") == "postgresql://u:p@host/db"
    assert normalize_database_url("sqlite:///./livedesk.db") == "sqlite:///./livedesk.db"


def test_database_url_from_the_environment_is_normalized():
    settings = load_settings({"DATABASE_URL": "postgres://u:p@host/db"})
    assert settings.database_url == "postgresql://u:p@host/db"


def test_production_refuses_to_start_on_the_default_token():
    with pytest.raises(RuntimeError):
        load_settings({"APP_ENV": "production"})
    with pytest.raises(RuntimeError):
        load_settings({"APP_ENV": "Production", "AGENT_TOKEN": DEFAULT_AGENT_TOKEN})


def test_production_starts_with_a_real_token():
    settings = load_settings({"APP_ENV": "production", "AGENT_TOKEN": "a-real-secret"})
    assert settings.agent_token == "a-real-secret"
    assert not settings.uses_default_token


def test_development_falls_back_to_the_default_token():
    settings = load_settings({})
    assert settings.app_env == "development"
    assert settings.uses_default_token


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_agent_token_never_becomes_the_secret(blank):
    # Regression test: AGENT_TOKEN= (set but empty) used to become the secret
    # itself, and an unauthenticated request sends an empty header — so it
    # matched, and anyone could list every conversation.
    assert load_settings({"AGENT_TOKEN": blank}).uses_default_token
    with pytest.raises(RuntimeError):
        load_settings({"APP_ENV": "production", "AGENT_TOKEN": blank})


def test_cors_origins_are_parsed_from_a_comma_separated_list():
    settings = load_settings({"CORS_ORIGINS": " https://app.example.com ,, https://www.example.com "})
    assert settings.cors_origins == ["https://app.example.com", "https://www.example.com"]


def test_cors_defaults_to_the_local_vite_origins():
    assert load_settings({}).cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_cors_only_allows_the_configured_origins():
    # Regression test: allow_origins used to be ["*"], hardcoded.
    client = TestClient(app)

    allowed = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"

    stranger = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in stranger.headers
