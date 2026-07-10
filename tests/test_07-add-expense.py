"""Tests for Step 7 — Add Expense.

Spec: .claude/specs/07-add-expense.md

Every assertion is derived from the spec's "Definition of done", "Routes",
"Database changes", and "Rules for implementation" sections — NOT from the
current implementation. The implementation is consulted only for wiring (route
name/path ``/expenses/add`` + ``add_expense`` endpoint, form field names
``amount`` / ``category`` / ``date`` / ``description``, the ``create_expense``
helper signature, the ``CATEGORIES`` list, session key ``user_id``, and the
``base.html`` flash block rendered as ``<div class="flash">``).

Where the implementation diverges from the spec, the test is written to the
spec and left failing; such divergences are reported, never masked.

Money/date are display-only (spec): ``amount`` is stored as REAL, ``date`` stays
``YYYY-MM-DD``. Default date is ``date.today()``, so tests that touch the default
compute "today" with stdlib ``datetime`` to stay deterministic on any calendar
day.
"""

from datetime import date

import database.db as db
from tests.conftest import login_session


# --------------------------------------------------------------------------- #
# Local helpers — read the isolated test DB directly (parameterised).          #
# --------------------------------------------------------------------------- #
def _all_expenses(user_id=None):
    """Return every expense row (optionally scoped to a user), newest id first."""
    conn = db.get_db()
    try:
        if user_id is None:
            return conn.execute(
                "SELECT * FROM expenses ORDER BY id DESC"
            ).fetchall()
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()


def _count_expenses(user_id=None):
    conn = db.get_db()
    try:
        if user_id is None:
            return conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
        return conn.execute(
            "SELECT COUNT(*) AS c FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()["c"]
    finally:
        conn.close()


def _signed_in(client, make_user, email="u@spendly.com", name="U"):
    uid = make_user(email=email)
    login_session(client, uid, name)
    return uid


def _post(client, amount="12.50", category="Food", date_="2026-06-15",
          description="Lunch"):
    """POST to /expenses/add. Any field passed as None is omitted entirely."""
    payload = {}
    if amount is not None:
        payload["amount"] = amount
    if category is not None:
        payload["category"] = category
    if date_ is not None:
        payload["date"] = date_
    if description is not None:
        payload["description"] = description
    return client.post("/expenses/add", data=payload)


# =========================================================================== #
# DoD #1 — Signed-in GET renders the form: Amount, 7 categories, Date=today,   #
#          optional Description.                                               #
# =========================================================================== #
class TestGetRendersForm:
    def test_get_returns_200_for_signed_in_user(self, client, make_user):
        _signed_in(client, make_user)
        assert client.get("/expenses/add").status_code == 200

    def test_form_posts_to_add_expense(self, client, make_user):
        _signed_in(client, make_user)
        data = client.get("/expenses/add").data.decode().lower()
        assert 'method="post"' in data
        assert "/expenses/add" in data

    def test_amount_field_present(self, client, make_user):
        _signed_in(client, make_user)
        data = client.get("/expenses/add").data.decode()
        assert 'name="amount"' in data

    def test_all_seven_categories_offered(self, client, make_user):
        _signed_in(client, make_user)
        data = client.get("/expenses/add").data.decode()
        assert 'name="category"' in data
        for category in db.CATEGORIES:
            assert category in data
        assert len(db.CATEGORIES) == 7

    def test_date_field_present_and_defaults_to_today(self, client, make_user):
        _signed_in(client, make_user)
        data = client.get("/expenses/add").data.decode()
        assert 'name="date"' in data
        assert date.today().isoformat() in data

    def test_description_field_present_and_optional(self, client, make_user):
        _signed_in(client, make_user)
        data = client.get("/expenses/add").data.decode()
        assert 'name="description"' in data
        # optional -> the input itself must not carry the `required` attribute.
        assert "optional" in data.lower()


# =========================================================================== #
# DoD #2 — Valid POST inserts exactly one row for the current user and         #
#          redirects to /profile with a confirmation flash.                    #
# =========================================================================== #
class TestValidPostInsertsAndRedirects:
    def test_valid_post_inserts_exactly_one_row(self, client, make_user):
        uid = _signed_in(client, make_user)
        assert _count_expenses(uid) == 0
        _post(client, amount="12.50", category="Food",
              date_="2026-06-15", description="Lunch")
        assert _count_expenses(uid) == 1

    def test_valid_post_redirects_to_profile(self, client, make_user):
        _signed_in(client, make_user)
        resp = _post(client)
        assert resp.status_code == 302
        assert "/profile" in resp.headers["Location"]

    def test_valid_post_flashes_a_confirmation(self, client, make_user):
        _signed_in(client, make_user)
        resp = _post(client)
        # Follow the redirect so the flash is consumed/rendered on /profile.
        followed = client.get(resp.headers["Location"])
        assert followed.status_code == 200
        assert b'class="flash"' in followed.data


# =========================================================================== #
# DoD #3 — The new expense immediately appears in profile totals/recent list   #
#          and in /transactions; category breakdown updates.                   #
# =========================================================================== #
class TestNewExpenseSurfaces:
    def test_new_expense_shows_in_profile_recent_and_total(self, client, make_user):
        _signed_in(client, make_user)
        _post(client, amount="77.00", category="Health",
              date_="2026-06-20", description="Dentist")
        data = client.get("/profile").data
        assert b"Dentist" in data
        assert b"$77.00" in data

    def test_new_expense_shows_in_transactions(self, client, make_user):
        _signed_in(client, make_user)
        _post(client, amount="34.00", category="Transport",
              date_="2026-06-21", description="Taxi ride")
        data = client.get("/transactions").data
        assert b"Taxi ride" in data
        assert b"$34.00" in data

    def test_new_expense_updates_category_breakdown(self, client, make_user):
        uid = _signed_in(client, make_user)
        _post(client, amount="50.00", category="Shopping",
              date_="2026-06-22", description="Shoes")
        breakdown = db.get_category_breakdown(uid)
        totals = {r["category"]: r["total"] for r in breakdown}
        assert "Shopping" in totals
        assert round(totals["Shopping"], 2) == 50.00


# =========================================================================== #
# DoD #4 — Inserted row has correct user_id, amount (REAL), category, date     #
#          (YYYY-MM-DD), and description (NULL when blank).                     #
# =========================================================================== #
class TestInsertedRowShape:
    def test_row_columns_match_submitted_values(self, client, make_user):
        uid = _signed_in(client, make_user)
        _post(client, amount="42.75", category="Bills",
              date_="2026-06-15", description="Water bill")
        row = _all_expenses(uid)[0]
        assert row["user_id"] == uid
        assert row["amount"] == 42.75
        assert isinstance(row["amount"], float)          # stored as REAL
        assert row["category"] == "Bills"
        assert row["date"] == "2026-06-15"               # YYYY-MM-DD, unreformatted
        assert row["description"] == "Water bill"

    def test_blank_description_stored_as_null(self, client, make_user):
        uid = _signed_in(client, make_user)
        _post(client, amount="9.99", category="Other",
              date_="2026-06-15", description="")
        row = _all_expenses(uid)[0]
        assert row["description"] is None

    def test_whitespace_only_description_stored_as_null(self, client, make_user):
        # Spec rule: strip whitespace and store None/NULL when blank.
        uid = _signed_in(client, make_user)
        _post(client, amount="9.99", category="Other",
              date_="2026-06-15", description="   ")
        row = _all_expenses(uid)[0]
        assert row["description"] is None

    def test_omitted_description_stored_as_null(self, client, make_user):
        uid = _signed_in(client, make_user)
        _post(client, amount="9.99", category="Other",
              date_="2026-06-15", description=None)
        row = _all_expenses(uid)[0]
        assert row["description"] is None


# =========================================================================== #
# DoD #5 — Invalid submissions do NOT insert a row; the form re-renders with a  #
#          flash and keeps the user's entered values.                          #
# =========================================================================== #
class TestValidationErrors:
    def _assert_rejected(self, resp, uid):
        """A rejected POST: no row inserted, form re-rendered (200) with a flash."""
        assert _count_expenses(uid) == 0
        assert resp.status_code == 200                   # re-render, not redirect
        assert b'class="flash"' in resp.data

    def test_missing_amount_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        resp = _post(client, amount=None, category="Food",
                     date_="2026-06-15", description="x")
        self._assert_rejected(resp, uid)

    def test_empty_amount_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        resp = _post(client, amount="", category="Food",
                     date_="2026-06-15", description="x")
        self._assert_rejected(resp, uid)

    def test_zero_amount_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        resp = _post(client, amount="0", category="Food",
                     date_="2026-06-15", description="x")
        self._assert_rejected(resp, uid)

    def test_negative_amount_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        resp = _post(client, amount="-5", category="Food",
                     date_="2026-06-15", description="x")
        self._assert_rejected(resp, uid)

    def test_non_numeric_amount_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        resp = _post(client, amount="abc", category="Food",
                     date_="2026-06-15", description="x")
        self._assert_rejected(resp, uid)

    def test_category_not_in_list_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        resp = _post(client, amount="10", category="Groceries",  # not in CATEGORIES
                     date_="2026-06-15", description="x")
        self._assert_rejected(resp, uid)

    def test_missing_category_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        resp = _post(client, amount="10", category=None,
                     date_="2026-06-15", description="x")
        self._assert_rejected(resp, uid)

    def test_missing_date_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        resp = _post(client, amount="10", category="Food",
                     date_=None, description="x")
        self._assert_rejected(resp, uid)

    def test_empty_date_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        resp = _post(client, amount="10", category="Food",
                     date_="", description="x")
        self._assert_rejected(resp, uid)

    def test_malformed_date_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        resp = _post(client, amount="10", category="Food",
                     date_="15-06-2026", description="x")   # wrong format
        self._assert_rejected(resp, uid)

    def test_invalid_calendar_date_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        resp = _post(client, amount="10", category="Food",
                     date_="2026-13-40", description="x")   # impossible date
        self._assert_rejected(resp, uid)

    def test_bounce_preserves_submitted_values(self, client, make_user):
        # Spec: on failure re-render with the user's submitted values preserved.
        _signed_in(client, make_user)
        # Bad amount, but a valid category/date/description that must be echoed back.
        resp = _post(client, amount="not-a-number", category="Health",
                     date_="2026-06-09", description="Pharmacy run")
        data = resp.data.decode()
        assert "not-a-number" in data          # bad amount preserved
        assert "Pharmacy run" in data          # description preserved
        assert 'value="2026-06-09"' in data    # date preserved
        # selected category preserved on its <option>
        assert "Health" in data


# =========================================================================== #
# DoD #6 — Auth guard + write is always scoped to the current user_id.         #
# =========================================================================== #
class TestAuthAndScoping:
    def test_get_signed_out_redirects_to_login(self, client):
        resp = client.get("/expenses/add")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_post_signed_out_redirects_to_login(self, client):
        resp = client.post("/expenses/add", data={
            "amount": "10", "category": "Food",
            "date": "2026-06-15", "description": "x",
        })
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_post_signed_out_inserts_nothing(self, client, make_user):
        # Ensure a user exists so the table is otherwise reachable.
        make_user()
        client.post("/expenses/add", data={
            "amount": "10", "category": "Food",
            "date": "2026-06-15", "description": "x",
        })
        assert _count_expenses() == 0

    def test_write_scoped_to_session_user_ignoring_form_user_id(
        self, client, make_user
    ):
        # Spec rule: never trust a user_id from the form; insert under the
        # session user only.
        me = _signed_in(client, make_user, email="me@spendly.com")
        other = make_user(email="other@spendly.com")
        client.post("/expenses/add", data={
            "amount": "10", "category": "Food", "date": "2026-06-15",
            "description": "mine", "user_id": other,   # attacker-supplied
        })
        assert _count_expenses(me) == 1
        assert _count_expenses(other) == 0
        assert _all_expenses(me)[0]["user_id"] == me

    def test_user_cannot_see_or_touch_another_users_rows(self, client, make_user):
        alice = make_user(email="alice@spendly.com")
        # Alice already has an expense.
        db.create_expense(alice, 99.00, "Shopping", "2026-06-01", "alice-secret")
        bob = _signed_in(client, make_user, email="bob@spendly.com", name="Bob")
        _post(client, amount="5.00", category="Food",
              date_="2026-06-15", description="bob-lunch")
        # Bob's write lands under Bob; Alice's row is untouched and unseen.
        assert _count_expenses(bob) == 1
        assert _count_expenses(alice) == 1
        data = client.get("/profile").data
        assert b"alice-secret" not in data


# =========================================================================== #
# Database changes — create_expense helper contract.                           #
# =========================================================================== #
class TestCreateExpenseHelper:
    def test_returns_new_row_id(self, make_user):
        uid = make_user()
        new_id = db.create_expense(uid, 25.00, "Food", "2026-06-15", "Snack")
        assert isinstance(new_id, int)
        row = _all_expenses(uid)[0]
        assert row["id"] == new_id

    def test_description_defaults_to_none(self, make_user):
        uid = make_user()
        db.create_expense(uid, 25.00, "Food", "2026-06-15")
        assert _all_expenses(uid)[0]["description"] is None

    def test_persisted_columns_are_exact(self, make_user):
        uid = make_user()
        db.create_expense(uid, 12.34, "Transport", "2026-01-02", "Bus")
        row = _all_expenses(uid)[0]
        assert row["user_id"] == uid
        assert row["amount"] == 12.34
        assert row["category"] == "Transport"
        assert row["date"] == "2026-01-02"
        assert row["description"] == "Bus"
        assert row["created_at"] is not None    # column default applied


# =========================================================================== #
# Security — password hash / plaintext never rendered on the add page.         #
# =========================================================================== #
class TestSecurity:
    def test_password_hash_not_exposed_on_form(self, client, make_user):
        uid = _signed_in(client, make_user, email="sec@spendly.com")
        user = db.get_user_by_id(uid)
        data = client.get("/expenses/add").data
        assert user["password_hash"].encode() not in data
        assert b"password_hash" not in data
