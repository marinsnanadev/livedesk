import os

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app import models  # noqa: F401
from app.database import Base

ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")


def _migrate(connection, action, revision):
    config = Config(ALEMBIC_INI)
    config.attributes["connection"] = connection
    getattr(command, action)(config, revision)


def test_migrations_match_the_models(tmp_path):
    # Regression test: a column added to a model without a migration works
    # in local SQLite and in tests, then breaks the deployed database.
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    with engine.begin() as connection:
        _migrate(connection, "upgrade", "head")
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert diff == []


def test_messages_are_indexed_by_conversation(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    with engine.begin() as connection:
        _migrate(connection, "upgrade", "head")
        indexes = inspect(connection).get_indexes("messages")

    assert any(index["column_names"] == ["conversation_id"] for index in indexes)


def test_migrations_can_be_rolled_back(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    with engine.begin() as connection:
        _migrate(connection, "upgrade", "head")
        _migrate(connection, "downgrade", "base")
        tables = set(inspect(connection).get_table_names())

    assert not tables - {"alembic_version"}
