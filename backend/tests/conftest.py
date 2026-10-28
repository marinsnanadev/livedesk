"""
Points the test suite at its own SQLite file instead of the dev/prod one.

DATABASE_URL is read once, at import time, by app.database — so this has
to run before anything imports app.main (which imports app.database).
pytest always loads conftest.py before collecting test modules in the
same directory, which is what makes that ordering safe here.

Without this, every `pytest -v` run quietly INSERTed real rows into
whatever database.py's default (backend/livedesk.db) pointed at — the
same file the dev server and the agent dashboard read from. Running the
suite a few times is exactly how a ticket queue ends up with dozens of
tickets named "Persisted Ticket", "Bad Status", "Broadcast Ticket" etc.
— every one of them a name this suite uses for its own test data.

The stale test file is removed here, at module level, so the suite
always starts from a clean slate. Doing this as a fixture instead (even
an autouse, session-scoped one) runs too late: pytest imports app.main
during collection, which creates the tables on whatever engine/connection
app.database opened — deleting the file after that leaves that
connection pointing at a file that no longer exists, and every write
in the run fails with "attempt to write a readonly database".
"""
import os
import sys

import pytest

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "test_livedesk.db")

if os.path.exists(TEST_DB_PATH):
    os.remove(TEST_DB_PATH)

# Set TEST_DATABASE_URL to run the suite against another database (e.g. a
# throwaway Postgres) instead of the local SQLite file. Its name has to contain
# "test_livedesk": a test further down checks for it, so the suite can't be
# pointed at a real database by accident.
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{TEST_DB_PATH}"
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, BACKEND_DIR)

# The app no longer creates its own tables; the schema comes from the
# migrations, so the suite exercises them on every run.
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

command.upgrade(Config(os.path.join(BACKEND_DIR, "alembic.ini")), "head")


@pytest.fixture
def client():
    # Entering the TestClient runs every connection on one event loop, like
    # uvicorn does. Without it each websocket gets its own loop and thread,
    # and tests that wait on events crossing between sockets hang at random.
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
