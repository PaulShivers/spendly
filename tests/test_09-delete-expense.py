"""Tests for Step 9 — Delete Expense.

Spec: .claude/specs/09-delete-expense.md

Every assertion is derived from the spec's "Routes", "Database changes",
"Rules for implementation", and "Definition of done" sections — NOT from the
current implementation. The implementation is consulted only for wiring:

* route path ``/expenses/<int:id>/delete`` + endpoint ``delete_expense``,
  POST-only (``methods=["POST"]``),
* the ``delete_expense_by_id(expense_id, user_id)`` / ``get_expense_by_id``
  helper signatures, and ``create_expense`` for seeding,
* session key ``user_id``,
* the ``base.html`` flash block rendered as ``<div class="flash">``,
* the per-row transactions delete control (``.txn-delete`` button inside a
  ``.txn-delete-form`` POST form whose action is the delete endpoint).

Where the implementation diverges from the spec, the test is written to the
spec and left failing; such divergences are reported, never masked.

Untestable gap: the JS ``confirm("Delete this expense?")`` dialog (spec DoD
item and Templates/JS notes) is browser-only progressive enhancement and cannot
be exercised through the Flask test client — it is intentionally not tested
here, consistent with the Step 8 suite's handling of untestable structural
items. The server-side POST guarantees (deletion happens on POST, never on GET)
are covered below.
"""

import re

import database.db as db
from tests.conftest import login_session


# --------------------------------------------------------------------------- #
# Local helpers — read the isolated test DB directly (parameterised).          #
# --------------------------------------------------------------------------- #
def _get_expense(expense_id):
    """Return one expense row by id (unscoped) straight from the DB, or None."""
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


def _signed_in(client, make_user, email="u@spendly.com", name="U"):
    uid = make_user(email=email)
    login_session(client, uid, name)
    return uid


def _seed_expense(user_id, amount=12.50, category="Food",
                  date="2026-06-15", description="Lunch"):
    """Insert one expense via the real create_expense helper; return its id."""
    return db.create_expense(user_id, amount, category, date, description)


def _delete(client, expense_id):
    """POST to the delete route (the spec's state-changing action)."""
    return client.post(f"/expenses/{expense_id}/delete")


# =========================================================================== #
# DoD #1 — Each /transactions row shows a "Delete" control (a POST form/button) #
#          beside the Edit link, targeting /expenses/<id>/delete.               #
# =========================================================================== #
class TestTransactionsDeleteControl:
    def test_row_shows_delete_form_posting_to_delete_route(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, description="Groceries run")
        data = client.get("/transactions").data.decode()
        # A form that POSTs to this row's delete endpoint.
        assert f"/expenses/{eid}/delete" in data
        assert re.search(
            r'<form[^>]*\bmethod="POST"[^>]*action="[^"]*/expenses/%d/delete"'
            % eid,
            data,
            re.IGNORECASE,
        ) or re.search(
            r'<form[^>]*action="[^"]*/expenses/%d/delete"[^>]*\bmethod="POST"'
            % eid,
            data,
            re.IGNORECASE,
        )

    def test_delete_control_uses_txn_delete_class(self, client, make_user):
        uid = _signed_in(client, make_user)
        _seed_expense(uid)
        data = client.get("/transactions").data.decode()
        assert 'class="txn-delete"' in data

    def test_delete_is_a_submit_button_not_a_link(self, client, make_user):
        # Spec: destructive action is a POST form/button, never a GET link.
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        data = client.get("/transactions").data.decode()
        # No anchor navigates to the delete URL (that would be a destructive GET).
        assert not re.search(
            r'<a[^>]*href="[^"]*/expenses/%d/delete"' % eid, data, re.IGNORECASE
        )
        # There is a submit control for the delete form.
        assert re.search(r'<button[^>]*type="submit"[^>]*class="txn-delete"', data) \
            or re.search(r'<button[^>]*class="txn-delete"[^>]*type="submit"', data)

    def test_delete_control_present_beside_edit_for_each_expense(self, client, make_user):
        uid = _signed_in(client, make_user)
        e1 = _seed_expense(uid, description="one")
        e2 = _seed_expense(uid, category="Bills", description="two")
        data = client.get("/transactions").data.decode()
        for eid in (e1, e2):
            assert f"/expenses/{eid}/edit" in data      # Edit link
            assert f"/expenses/{eid}/delete" in data     # Delete control beside it


# =========================================================================== #
# DoD #2 — Valid POST delete of your own expense removes exactly that row,      #
#          redirects to /transactions with an "Expense deleted." flash; the     #
#          row disappears and totals / category breakdown update accordingly.   #
# =========================================================================== #
class TestValidDelete:
    def test_delete_removes_the_row(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        _delete(client, eid)
        assert _get_expense(eid) is None

    def test_delete_redirects_to_transactions(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        resp = _delete(client, eid)
        assert resp.status_code == 302
        assert "/transactions" in resp.headers["Location"]

    def test_delete_flashes_confirmation(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        resp = _delete(client, eid)
        followed = client.get(resp.headers["Location"])
        assert followed.status_code == 200
        assert b'class="flash"' in followed.data
        assert b"Expense deleted." in followed.data

    def test_deleted_row_disappears_from_transactions(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, description="soon-gone")
        assert b"soon-gone" in client.get("/transactions").data
        _delete(client, eid)
        data = client.get("/transactions").data
        assert b"soon-gone" not in data
        assert f"/expenses/{eid}/delete".encode() not in data

    def test_delete_reflected_in_summary_total(self, client, make_user):
        uid = _signed_in(client, make_user)
        keep = _seed_expense(uid, amount=40.00, category="Food",
                             date="2026-06-10", description="keep")
        drop = _seed_expense(uid, amount=60.00, category="Bills",
                             date="2026-06-11", description="drop")
        assert round(db.get_summary(uid)["total"], 2) == 100.00
        _delete(client, drop)
        summary = db.get_summary(uid)
        assert round(summary["total"], 2) == 40.00
        assert summary["count"] == 1
        assert keep is not None                          # the kept row still counts

    def test_delete_reflected_in_category_breakdown(self, client, make_user):
        uid = _signed_in(client, make_user)
        _seed_expense(uid, amount=40.00, category="Food", description="food")
        drop = _seed_expense(uid, amount=60.00, category="Bills", description="bills")
        _delete(client, drop)
        totals = {r["category"]: r["total"] for r in db.get_category_breakdown(uid)}
        assert "Bills" not in totals                     # whole category gone
        assert round(totals["Food"], 2) == 40.00


# =========================================================================== #
# DoD #3 — Only the targeted row is deleted: the user's other expenses and      #
#          other users' expenses are untouched; total count drops by exactly 1. #
# =========================================================================== #
class TestSingleRowEffect:
    def test_only_targeted_row_of_same_user_removed(self, client, make_user):
        uid = _signed_in(client, make_user)
        target = _seed_expense(uid, description="target")
        other = _seed_expense(uid, category="Health", description="keep-mine")
        _delete(client, target)
        assert _get_expense(target) is None
        assert _get_expense(other) is not None           # sibling untouched

    def test_total_expense_count_drops_by_exactly_one(self, client, make_user):
        uid = _signed_in(client, make_user)
        target = _seed_expense(uid, description="target")
        _seed_expense(uid, category="Health")
        _seed_expense(uid, category="Bills")
        before = _count_expenses()                        # global count
        _delete(client, target)
        assert _count_expenses() == before - 1

    def test_other_users_rows_untouched(self, client, make_user):
        alice = make_user(email="alice@spendly.com")
        a1 = _seed_expense(alice, description="alice-one")
        a2 = _seed_expense(alice, category="Shopping", description="alice-two")
        bob = _signed_in(client, make_user, email="bob@spendly.com", name="Bob")
        bob_eid = _seed_expense(bob, description="bob-row")
        _delete(client, bob_eid)
        # Bob's own row gone, both of Alice's rows remain.
        assert _get_expense(bob_eid) is None
        assert _get_expense(a1) is not None
        assert _get_expense(a2) is not None
        assert _count_expenses(alice) == 2


# =========================================================================== #
# DoD #5 — A plain GET to /expenses/<id>/delete does not delete anything;        #
#          the route is POST-only and returns 405.                              #
# =========================================================================== #
class TestMethodGuard:
    def test_get_returns_405(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        resp = client.get(f"/expenses/{eid}/delete")
        assert resp.status_code == 405

    def test_get_does_not_delete(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid, description="still-here")
        client.get(f"/expenses/{eid}/delete")
        assert _get_expense(eid) is not None             # untouched by GET


# =========================================================================== #
# DoD #4 — Deleting a non-existent id, or one owned by another user, removes     #
#          nothing: flash a not-found message and redirect to /transactions      #
#          (no 500, no other user's data affected).                             #
# =========================================================================== #
class TestOwnershipAndNotFound:
    def test_post_nonexistent_id_redirects_no_500(self, client, make_user):
        _signed_in(client, make_user)
        resp = _delete(client, 999999)
        assert resp.status_code == 302
        assert "/transactions" in resp.headers["Location"]

    def test_post_nonexistent_id_flashes_not_found(self, client, make_user):
        _signed_in(client, make_user)
        resp = _delete(client, 999999)
        followed = client.get(resp.headers["Location"])
        assert followed.status_code == 200
        assert b'class="flash"' in followed.data
        assert b"Expense deleted." not in followed.data  # nothing was deleted

    def test_post_nonexistent_id_deletes_nothing(self, client, make_user):
        uid = _signed_in(client, make_user)
        eid = _seed_expense(uid)
        before = _count_expenses()
        _delete(client, 999999)
        assert _count_expenses() == before
        assert _get_expense(eid) is not None

    def test_post_other_users_expense_redirects_no_500(self, client, make_user):
        alice = make_user(email="alice@spendly.com")
        aid = _seed_expense(alice, description="alice-secret")
        _signed_in(client, make_user, email="bob@spendly.com", name="Bob")
        resp = _delete(client, aid)
        assert resp.status_code == 302
        assert "/transactions" in resp.headers["Location"]

    def test_post_other_users_expense_deletes_nothing(self, client, make_user):
        alice = make_user(email="alice@spendly.com")
        aid = _seed_expense(alice, amount=99.00, category="Shopping",
                            date="2026-06-01", description="alice-secret")
        _signed_in(client, make_user, email="bob@spendly.com", name="Bob")
        _delete(client, aid)
        assert _get_expense(aid) is not None             # Alice's row survives
        assert _count_expenses(alice) == 1

    def test_post_other_users_expense_not_confirmed_as_deleted(self, client, make_user):
        # Spec: flash a not-found message, not the deletion confirmation.
        alice = make_user(email="alice@spendly.com")
        aid = _seed_expense(alice, description="alice-secret")
        _signed_in(client, make_user, email="bob@spendly.com", name="Bob")
        resp = _delete(client, aid)
        followed = client.get(resp.headers["Location"])
        assert b"Expense deleted." not in followed.data


# =========================================================================== #
# DoD #6 — Posting while signed out redirects to /login and deletes nothing.    #
# =========================================================================== #
class TestAuthGuard:
    def test_post_signed_out_redirects_to_login(self, client, make_user):
        uid = make_user()
        eid = _seed_expense(uid)                          # exists, but no session
        resp = _delete(client, eid)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_post_signed_out_deletes_nothing(self, client, make_user):
        uid = make_user()
        eid = _seed_expense(uid, description="protected")
        _delete(client, eid)
        assert _get_expense(eid) is not None             # untouched while signed out


# =========================================================================== #
# DoD #7 / Database changes — delete_expense_by_id helper contract.             #
# (Spec: parameterised DELETE scoped by user_id, get_db + try/finally, returns  #
#  the affected row count; 1 = deleted, 0 = not found / not owned.)             #
# =========================================================================== #
class TestDeleteExpenseByIdHelper:
    def test_deletes_owned_row_and_returns_one(self, make_user):
        uid = make_user()
        eid = _seed_expense(uid, description="mine")
        rowcount = db.delete_expense_by_id(eid, uid)
        assert rowcount == 1
        assert _get_expense(eid) is None

    def test_non_owner_delete_is_noop_returns_zero(self, make_user):
        owner = make_user(email="owner@spendly.com")
        other = make_user(email="other@spendly.com")
        eid = _seed_expense(owner, description="safe")
        rowcount = db.delete_expense_by_id(eid, other)
        assert rowcount == 0                              # scoped away by user_id
        assert _get_expense(eid) is not None             # owner's row survives

    def test_missing_id_is_noop_returns_zero(self, make_user):
        uid = make_user()
        assert db.delete_expense_by_id(999999, uid) == 0

    def test_delete_only_affects_named_row(self, make_user):
        uid = make_user()
        keep = _seed_expense(uid, description="keep")
        drop = _seed_expense(uid, description="drop")
        db.delete_expense_by_id(drop, uid)
        assert _get_expense(drop) is None
        assert _get_expense(keep) is not None


# =========================================================================== #
# Security — password hash / plaintext never rendered on the transactions page  #
# that hosts the delete control.                                                #
# =========================================================================== #
class TestSecurity:
    def test_password_hash_not_exposed_on_transactions(self, client, make_user):
        uid = _signed_in(client, make_user, email="sec@spendly.com")
        _seed_expense(uid)
        user = db.get_user_by_id(uid)
        data = client.get("/transactions").data
        assert user["password_hash"].encode() not in data
        assert b"password_hash" not in data
