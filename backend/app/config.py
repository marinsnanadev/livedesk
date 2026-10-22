import os
from dataclasses import dataclass
from typing import Mapping

from dotenv import load_dotenv

load_dotenv()

DEFAULT_AGENT_TOKEN = "dev-only-agent-token"
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    agent_token: str
    cors_origins: list[str]

    @property
    def uses_default_token(self) -> bool:
        return self.agent_token == DEFAULT_AGENT_TOKEN


def normalize_database_url(url: str) -> str:
    # Render and Heroku hand out "postgres://", which SQLAlchemy rejects. And a
    # bare "postgresql://" picks psycopg2 on SQLAlchemy 2.0 but psycopg 3 on
    # 2.1, so name the driver instead of depending on the version installed.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def load_settings(env: Mapping[str, str]) -> Settings:
    app_env = env.get("APP_ENV", "development").strip().lower()

    # A blank value counts as unset: an empty token would match the empty
    # header every unauthenticated request sends, and let everyone in.
    agent_token = env.get("AGENT_TOKEN", "").strip() or DEFAULT_AGENT_TOKEN
    if agent_token == DEFAULT_AGENT_TOKEN and app_env == "production":
        raise RuntimeError("AGENT_TOKEN must be set to a real secret when APP_ENV=production")

    origins = env.get("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return Settings(
        app_env=app_env,
        database_url=normalize_database_url(env.get("DATABASE_URL", "sqlite:///./livedesk.db").strip()),
        agent_token=agent_token,
        cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
    )


settings = load_settings(os.environ)
