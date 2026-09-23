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

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "test_livedesk.db")

if os.path.exists(TEST_DB_PATH):
    os.remove(TEST_DB_PATH)

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
