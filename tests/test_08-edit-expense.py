"""Tests for Step 8 — Edit Expense.

Spec: .claude/specs/08-edit-expense.md

Every assertion is derived from the spec's "Routes", "Database changes",
"Rules for implementation", and "Definition of done" sections — NOT from the
current implementation. The implementation is consulted only for wiring:

* route path ``/expenses/<int:id>/edit`` + endpoint ``edit_expense`` (GET+POST),
* form field names ``amount`` / ``category`` / ``date`` / ``description``,
* the ``get_expense_by_id`` / ``update_expense`` helper signatures,
* the ``CATEGORIES`` list, session key ``user_id``,
* the ``base.html`` flash block rendered as ``<div class="flash">``,
* the per-row transactions edit link (endpoint ``edit_expense``).

Where the implementation diverges from the spec, the test is written to the
spec and left failing; such divergences are reported, never masked.

Money/date are display-only (spec): ``amount`` stays REAL, ``date`` stays
``YYYY-MM-DD``; pre-fill and save must not reformat stored values, and
``created_at`` is never touched.
"""

import re

import database.db as db
from tests.conftest import login_session


# --------------------------------------------------------------------------- #
# Local helpers — read the isolated test DB directly (parameterised).          #
# --------------------------------------------------------------------------- #
def _get_expense(expense_id):
    """Return one expense row by id (unscoped) straight from the DB."""
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    finally:
        conn.close()


def _count_expenses(user_id=None):
    conn = db.get_db()
    try:
        if user_id is None:
            return conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
        return conn.execute(
            "SELECT COUNT(*) AS c FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()["c"]
    finally:
        conn.close()


def _fields(row):
    """The editable fields of a row, for unchanged-vs-changed comparisons."""
    return (row["amount"], row["category"], row["date"], row["description"])


def _signed_in(client, make_user, email="u@spendly.com", name="U"):
    uid = make_user(email=email)
    login_session(client, uid, name)
    return uid


def _seed_expense(user_id, amount=12.50, category="Food",
                  date="2026-06-15", description="Lunch"):
    """Insert one expense via the real create_expense helper; return its id."""
    return db.create_expense(user_id, amount, category, date, description)


def _post(client, expense_id, amount="20.00", category="Transport",
          date_="2026-06-20", description="Taxi"):
    """POST to the edit route. Any field passed as None is omitted entirely."""
    payload = {}
    if amount is not None:
        payload["amount"] = amount
    if category is not None:
        payload["category"] = category
    if date_ is not None:
        payload["date"] = date_
    if description is not None:
        payload["description"] = description
    return client.post(f"/expenses/{expense_id}/edit", data=payload)


def _option_selected(data, category):
    """True if the given category's <option> carries the `selected` attribute."""
    pattern = rf'<option value="{re.escape(category)}"[^>]*\bselected\b'
    return re.search(pattern, data) is not None


# =========================================================================== #
# DoD #1 — Each /transactions row shows an "Edit" link to /expenses/<id>/edit. #
# =========================================================================== #
class TestTransactionsEditLink:
    def test_row_shows_edit_link_to_edit_route(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, description="Groceries run")
        data = client.get("/transactions").data.decode()
        assert f"/expenses/{eid}/edit" in data

    def test_edit_link_present_for_each_expense(self, client, make_user):
        uid = _signed_in(client, make_user)
        e1 = _seed_expense(uid, description="one")
        e2 = _seed_expense(uid, category="Bills", description="two")
        data = client.get("/transactions").data.decode()
        assert f"/expenses/{e1}/edit" in data
        assert f"/expenses/{e2}/edit" in data


# =========================================================================== #
# DoD #2 — GET the edit page for your own expense renders a form pre-filled     #
#          with amount, the selected category option, date, and description.    #
# =========================================================================== #
class TestGetPreFilledForm:
    def test_get_returns_200_for_owned_expense(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        assert client.get(f"/expenses/{eid}/edit").status_code == 200

    def test_form_posts_back_to_edit_route(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        data = client.get(f"/expenses/{eid}/edit").data.decode().lower()
        assert 'method="post"' in data
        assert f"/expenses/{eid}/edit" in data

    def test_amount_prefilled(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, amount=73.25)
        data = client.get(f"/expenses/{eid}/edit").data.decode()
        assert 'name="amount"' in data
        assert 'value="73.25"' in data

    def test_correct_category_option_selected(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, category="Health")
        data = client.get(f"/expenses/{eid}/edit").data.decode()
        # every category is offered, but only the stored one is pre-selected
        for category in db.CATEGORIES:
            assert category in data
        assert _option_selected(data, "Health")
        assert not _option_selected(data, "Food")

    def test_date_prefilled_unreformatted(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, date="2026-03-09")
        data = client.get(f"/expenses/{eid}/edit").data.decode()
        assert 'name="date"' in data
        assert 'value="2026-03-09"' in data          # YYYY-MM-DD, not reformatted

    def test_description_prefilled(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, description="Weekly groceries")
        data = client.get(f"/expenses/{eid}/edit").data.decode()
        assert 'name="description"' in data
        assert "Weekly groceries" in data

    def test_null_description_prefills_blank_not_none(self, client, make_user):
        # A row with NULL description must not render the literal "None".
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, description=None)
        data = client.get(f"/expenses/{eid}/edit").data.decode()
        assert 'value="None"' not in data


# =========================================================================== #
# DoD #3 — Valid POST updates exactly that one row (no new row), redirects to   #
#          /transactions with a confirmation flash, change reflected across     #
#          transactions / profile totals / category breakdown.                  #
# =========================================================================== #
class TestValidUpdate:
    def test_update_changes_the_single_row(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, amount=12.50, category="Food",
                            date="2026-06-15", description="Lunch")
        _post(client, eid, amount="99.99", category="Bills",
              date_="2026-06-30", description="Electric")
        row = _get_expense(eid)
        assert _fields(row) == (99.99, "Bills", "2026-06-30", "Electric")

    def test_update_creates_no_new_row(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        before = _count_expenses(uid)
        _post(client, eid, amount="55.00", category="Shopping",
              date_="2026-06-18", description="Shoes")
        assert _count_expenses(uid) == before          # updated in place, not inserted

    def test_update_redirects_to_transactions(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        resp = _post(client, eid)
        assert resp.status_code == 302
        assert "/transactions" in resp.headers["Location"]

    def test_update_flashes_confirmation(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        resp = _post(client, eid)
        followed = client.get(resp.headers["Location"])
        assert followed.status_code == 200
        assert b'class="flash"' in followed.data

    def test_change_reflected_in_transactions(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, description="old-desc")
        _post(client, eid, amount="41.00", category="Transport",
              date_="2026-06-21", description="new-desc")
        data = client.get("/transactions").data
        assert b"new-desc" in data
        assert b"old-desc" not in data
        assert b"$41.00" in data

    def test_change_reflected_in_profile_totals(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, amount=10.00, category="Food",
                            date="2026-06-15", description="cheap")
        _post(client, eid, amount="250.00", category="Bills",
              date_="2026-06-16", description="pricey")
        summary = db.get_summary(uid)
        assert round(summary["total"], 2) == 250.00
        assert b"$250.00" in client.get("/profile").data

    def test_change_reflected_in_category_breakdown(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, amount=30.00, category="Food")
        _post(client, eid, amount="30.00", category="Health",
              date_="2026-06-15", description="Meds")
        totals = {r["category"]: r["total"] for r in db.get_category_breakdown(uid)}
        assert "Health" in totals
        assert round(totals["Health"], 2) == 30.00
        assert "Food" not in totals                     # moved out of Food entirely


# =========================================================================== #
# DoD #4 — Clearing the description and saving stores NULL for that row.        #
# =========================================================================== #
class TestDescriptionNulling:
    def test_clearing_description_stores_null(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, description="had a note")
        _post(client, eid, amount="12.50", category="Food",
              date_="2026-06-15", description="")
        assert _get_expense(eid)["description"] is None

    def test_whitespace_description_stores_null(self, client, make_user):
        # Spec rule: strip whitespace and store None/NULL when blank.
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, description="had a note")
        _post(client, eid, amount="12.50", category="Food",
              date_="2026-06-15", description="   ")
        assert _get_expense(eid)["description"] is None

    def test_omitted_description_stores_null(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, description="had a note")
        _post(client, eid, amount="12.50", category="Food",
              date_="2026-06-15", description=None)
        assert _get_expense(eid)["description"] is None


# =========================================================================== #
# Edge case (spec: "created_at is never modified").                            #
# =========================================================================== #
class TestCreatedAtPreserved:
    def test_update_does_not_touch_created_at(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        before = _get_expense(eid)["created_at"]
        _post(client, eid, amount="88.00", category="Other",
              date_="2026-06-25", description="changed")
        assert _get_expense(eid)["created_at"] == before


# =========================================================================== #
# DoD #5 — Invalid submissions do NOT modify the row; the form re-renders with  #
#          a flash and preserves the user's entered values.                     #
# =========================================================================== #
class TestValidationErrors:
    def _assert_unchanged(self, resp, eid, original):
        assert resp.status_code == 200                  # re-render, not redirect
        assert b'class="flash"' in resp.data
        assert _fields(_get_expense(eid)) == original   # row never partially updated

    def test_missing_amount_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        original = _fields(_get_expense(eid))
        resp = _post(client, eid, amount=None)
        self._assert_unchanged(resp, eid, original)

    def test_empty_amount_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        original = _fields(_get_expense(eid))
        resp = _post(client, eid, amount="")
        self._assert_unchanged(resp, eid, original)

    def test_zero_amount_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        original = _fields(_get_expense(eid))
        resp = _post(client, eid, amount="0")
        self._assert_unchanged(resp, eid, original)

    def test_negative_amount_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        original = _fields(_get_expense(eid))
        resp = _post(client, eid, amount="-9.99")
        self._assert_unchanged(resp, eid, original)

    def test_non_numeric_amount_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        original = _fields(_get_expense(eid))
        resp = _post(client, eid, amount="abc")
        self._assert_unchanged(resp, eid, original)

    def test_category_not_in_list_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        original = _fields(_get_expense(eid))
        resp = _post(client, eid, category="Groceries")   # not in CATEGORIES
        self._assert_unchanged(resp, eid, original)

    def test_missing_category_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        original = _fields(_get_expense(eid))
        resp = _post(client, eid, category=None)
        self._assert_unchanged(resp, eid, original)

    def test_missing_date_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        original = _fields(_get_expense(eid))
        resp = _post(client, eid, date_=None)
        self._assert_unchanged(resp, eid, original)

    def test_empty_date_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        original = _fields(_get_expense(eid))
        resp = _post(client, eid, date_="")
        self._assert_unchanged(resp, eid, original)

    def test_malformed_date_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        original = _fields(_get_expense(eid))
        resp = _post(client, eid, date_="15-06-2026")      # wrong format
        self._assert_unchanged(resp, eid, original)

    def test_invalid_calendar_date_rejected(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        original = _fields(_get_expense(eid))
        resp = _post(client, eid, date_="2026-13-40")      # impossible date
        self._assert_unchanged(resp, eid, original)

    def test_bounce_preserves_submitted_values(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, amount=12.50, category="Food",
                            date="2026-06-15", description="Lunch")
        # Bad amount; the other submitted values must be echoed back.
        resp = _post(client, eid, amount="not-a-number", category="Health",
                     date_="2026-06-09", description="Pharmacy run")
        data = resp.data.decode()
        assert "not-a-number" in data                  # bad amount preserved
        assert "Pharmacy run" in data                  # description preserved
        assert 'value="2026-06-09"' in data            # date preserved
        assert _option_selected(data, "Health")        # submitted category preserved


# =========================================================================== #
# DoD #6 — Non-existent or non-owned id (GET or POST) does not reveal or modify #
#          the expense: flash a not-found message and redirect to /transactions #
#          (no 500, no data leak).                                              #
# =========================================================================== #
class TestOwnershipAndNotFound:
    def test_get_nonexistent_id_redirects_to_transactions(self, client, make_user):
        _signed_in(client, make_user)
        resp = client.get("/expenses/999999/edit")
        assert resp.status_code == 302
        assert "/transactions" in resp.headers["Location"]

    def test_get_nonexistent_id_flashes_not_found(self, client, make_user):
        _signed_in(client, make_user)
        resp = client.get("/expenses/999999/edit")
        followed = client.get(resp.headers["Location"])
        assert followed.status_code == 200
        assert b'class="flash"' in followed.data

    def test_post_nonexistent_id_redirects_no_500(self, client, make_user):
        _signed_in(client, make_user)
        resp = _post(client, 999999)
        assert resp.status_code == 302
        assert "/transactions" in resp.headers["Location"]

    def test_get_other_users_expense_redirects_and_hides_data(self, client, make_user):
        alice = make_user(email="alice@spendly.com")
        aid = _seed_expense(alice, category="Shopping", description="alice-secret")
        _signed_in(client, make_user, email="bob@spendly.com", name="Bob")
        resp = client.get(f"/expenses/{aid}/edit")
        assert resp.status_code == 302
        assert "/transactions" in resp.headers["Location"]
        # Following the redirect must never surface Alice's private data.
        assert b"alice-secret" not in client.get(resp.headers["Location"]).data

    def test_post_other_users_expense_does_not_modify(self, client, make_user):
        alice = make_user(email="alice@spendly.com")
        aid = _seed_expense(alice, amount=99.00, category="Shopping",
                            date="2026-06-01", description="alice-secret")
        original = _fields(_get_expense(aid))
        _signed_in(client, make_user, email="bob@spendly.com", name="Bob")
        resp = _post(client, aid, amount="1.00", category="Food",
                     date_="2026-06-15", description="bob-hijack")
        assert resp.status_code == 302
        assert "/transactions" in resp.headers["Location"]
        assert _fields(_get_expense(aid)) == original   # Alice's row untouched


# =========================================================================== #
# DoD #7 — Signed out, GET or POST to the edit route redirects to /login.       #
# =========================================================================== #
class TestAuthGuard:
    def test_get_signed_out_redirects_to_login(self, client, make_user):
        uid = make_user()
        eid = _seed_expense(uid)                        # exists, but no session
        resp = client.get(f"/expenses/{eid}/edit")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_post_signed_out_redirects_to_login(self, client, make_user):
        uid = make_user()
        eid = _seed_expense(uid)
        resp = _post(client, eid)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_post_signed_out_does_not_modify_row(self, client, make_user):
        uid = make_user()
        eid = _seed_expense(uid, amount=12.50, category="Food",
                            date="2026-06-15", description="Lunch")
        original = _fields(_get_expense(eid))
        _post(client, eid, amount="500.00", category="Bills",
              date_="2026-01-01", description="hacked")
        assert _fields(_get_expense(eid)) == original


# =========================================================================== #
# Database changes — get_expense_by_id / update_expense helper contracts.       #
# (Spec: both scoped by user_id, parameterised, get_db + try/finally pattern.)  #
# =========================================================================== #
class TestGetExpenseByIdHelper:
    def test_returns_owned_row(self, make_user):
        uid = make_user()
        eid = _seed_expense(uid, description="mine")
        row = db.get_expense_by_id(eid, uid)
        assert row is not None
        assert row["id"] == eid
        assert row["description"] == "mine"

    def test_returns_none_for_non_owner(self, make_user):
        owner = make_user(email="owner@spendly.com")
        other = make_user(email="other@spendly.com")
        eid = _seed_expense(owner)
        assert db.get_expense_by_id(eid, other) is None

    def test_returns_none_for_missing_id(self, make_user):
        uid = make_user()
        assert db.get_expense_by_id(999999, uid) is None


class TestUpdateExpenseHelper:
    def test_updates_owned_row_and_reports_one(self, make_user):
        uid = make_user()
        eid = _seed_expense(uid, amount=10.00, category="Food",
                            date="2026-06-15", description="old")
        rowcount = db.update_expense(eid, uid, 20.00, "Bills", "2026-07-01", "new")
        assert rowcount == 1
        assert _fields(_get_expense(eid)) == (20.00, "Bills", "2026-07-01", "new")

    def test_amount_persisted_as_real(self, make_user):
        uid = make_user()
        eid = _seed_expense(uid)
        db.update_expense(eid, uid, 42.75, "Food", "2026-06-15", None)
        row = _get_expense(eid)
        assert row["amount"] == 42.75
        assert isinstance(row["amount"], float)

    def test_description_none_stored_as_null(self, make_user):
        uid = make_user()
        eid = _seed_expense(uid, description="note")
        db.update_expense(eid, uid, 10.00, "Food", "2026-06-15", None)
        assert _get_expense(eid)["description"] is None

    def test_non_owner_update_is_a_noop(self, make_user):
        owner = make_user(email="owner@spendly.com")
        other = make_user(email="other@spendly.com")
        eid = _seed_expense(owner, amount=10.00, category="Food",
                            date="2026-06-15", description="safe")
        original = _fields(_get_expense(eid))
        rowcount = db.update_expense(eid, other, 999.00, "Bills",
                                     "2026-01-01", "stolen")
        assert rowcount == 0                            # scoped away by user_id
        assert _fields(_get_expense(eid)) == original


# =========================================================================== #
# Security — password hash / plaintext never rendered on the edit page.         #
# =========================================================================== #
class TestSecurity:
    def test_password_hash_not_exposed_on_form(self, client, make_user):
        uid = _signed_in(client, make_user, email="sec@spendly.com")
        eid = _seed_expense(uid)
        user = db.get_user_by_id(uid)
        data = client.get(f"/expenses/{eid}/edit").data
        assert user["password_hash"].encode() not in data
        assert b"password_hash" not in data
