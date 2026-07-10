"""Shared pytest fixtures for the Spendly test suite.

The database is fully isolated from the real ``expense_tracker.db``:

* Before ``app`` is imported we repoint ``database.db.DB_PATH`` at a throwaway
  temp file, so the module-level ``init_db()`` / ``seed_db()`` that runs on
  import never touches (or creates) the real project database.
* Each test then gets its own fresh temp DB via the ``app`` fixture, which
  monkeypatches ``database.db.DB_PATH`` and runs ``init_db()`` against it.

All seeding goes through the ``database.db`` helpers / parameterised queries,
never against the real DB path.
"""

import os
import tempfile

import pytest

import database.db as db

# --------------------------------------------------------------------------- #
# Redirect the DB to a throwaway temp file BEFORE importing the app module,    #
# so its import-time init_db()/seed_db() never hit the real project database.  #
# --------------------------------------------------------------------------- #
_BOOTSTRAP_DIR = tempfile.mkdtemp(prefix="spendly-bootstrap-")
db.DB_PATH = os.path.join(_BOOTSTRAP_DIR, "bootstrap.db")

import app as app_module  # noqa: E402  (import must follow the DB_PATH patch)


# --------------------------------------------------------------------------- #
# Core Flask fixtures                                                          #
# --------------------------------------------------------------------------- #
@pytest.fixture
def app(tmp_path, monkeypatch):
    """The Flask app wired to a fresh, isolated per-test SQLite file."""
    db_path = str(tmp_path / "test_expense_tracker.db")
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()

    flask_app = app_module.app
    flask_app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
        WTF_CSRF_ENABLED=False,
    )
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# --------------------------------------------------------------------------- #
# Seeding helpers                                                             #
# --------------------------------------------------------------------------- #
def _insert_expense(user_id, amount, category, date, description=None):
    """Insert one expense row directly through get_db() (parameterised)."""
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def insert_expense(app):
    """Callable to insert an expense into the isolated test DB."""
    return _insert_expense


@pytest.fixture
def make_user(app):
    """Create a user via the real helper and return their id."""
    def _make(name="Test User", email="test@spendly.com", password="password123"):
        return db.create_user(name, email.lower(), password)

    return _make


@pytest.fixture
def current_month(app):
    """The current calendar month as SQLite computes it ('YYYY-MM')."""
    conn = db.get_db()
    try:
        return conn.execute("SELECT strftime('%Y-%m', 'now') AS m").fetchone()["m"]
    finally:
        conn.close()


# Seeded demo dataset (mirrors seed_db in database/db.py). Kept here so tests
# have deterministic, known figures independent of import-time seeding.
DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
DEMO_EXPENSES = [
    (42.50, "Food", "2026-07-01", "Groceries"),
    (15.00, "Transport", "2026-07-02", "Bus pass"),
    (120.00, "Bills", "2026-07-03", "Electricity"),
    (60.00, "Health", "2026-07-05", "Pharmacy"),
    (25.00, "Entertainment", "2026-07-08", "Movie tickets"),
    (80.00, "Shopping", "2026-07-10", "Clothes"),
    (10.00, "Other", "2026-07-12", "Misc"),
    (33.75, "Food", "2026-07-15", "Restaurant"),
]
DEMO_TOTAL = round(sum(e[0] for e in DEMO_EXPENSES), 2)  # 386.25
DEMO_COUNT = len(DEMO_EXPENSES)                            # 8


@pytest.fixture
def demo_user(app):
    """Create the seeded demo account with its 8 sample expenses."""
    user_id = db.create_user("Demo User", DEMO_EMAIL, DEMO_PASSWORD)
    for amount, category, date, description in DEMO_EXPENSES:
        _insert_expense(user_id, amount, category, date, description)
    return user_id


def login_session(client, user_id, user_name="Demo User"):
    """Put a user into the Flask session, mimicking a successful login."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = user_name


@pytest.fixture
def demo_client(client, demo_user):
    """A client signed in as the seeded demo user."""
    login_session(client, demo_user, "Demo User")
    return client
