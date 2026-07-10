"""Tests for Step 5 — Profile & reporting routes.

Spec: .claude/specs/05-profile-reporting-routes.md

Every assertion is derived from the spec's "Definition of done" and its
"Rules for implementation", NOT from the current implementation. Where the
implementation diverges from the spec the test is written to the spec and is
expected to fail (those divergences are called out in the run report).
"""

import database.db as db
from tests.conftest import (
    DEMO_COUNT,
    DEMO_TOTAL,
    login_session,
)


# =========================================================================== #
# DB helper contracts: get_expenses                                           #
# =========================================================================== #
class TestGetExpenses:
    def test_returns_all_rows_for_user(self, demo_user):
        rows = db.get_expenses(demo_user)
        assert len(rows) == DEMO_COUNT

    def test_newest_first_ordering(self, demo_user):
        # Ordered by date DESC, id DESC -> newest date first.
        rows = db.get_expenses(demo_user)
        dates = [r["date"] for r in rows]
        assert dates == sorted(dates, reverse=True)
        assert rows[0]["date"] == "2026-07-15"
        assert rows[0]["description"] == "Restaurant"
        assert rows[-1]["date"] == "2026-07-01"

    def test_date_tiebreak_uses_id_desc(self, insert_expense, make_user):
        uid = make_user()
        first = insert_expense  # alias for readability
        first(uid, 1.00, "Food", "2026-05-01", "first")
        first(uid, 2.00, "Food", "2026-05-01", "second")
        rows = db.get_expenses(uid)
        # Same date -> higher id (inserted later) comes first.
        assert rows[0]["description"] == "second"
        assert rows[1]["description"] == "first"

    def test_limit_returns_at_most_n_newest(self, demo_user):
        rows = db.get_expenses(demo_user, limit=5)
        assert len(rows) == 5
        assert rows[0]["description"] == "Restaurant"  # newest
        descriptions = [r["description"] for r in rows]
        assert "Groceries" not in descriptions  # oldest excluded

    def test_limit_larger_than_count_returns_all(self, demo_user):
        rows = db.get_expenses(demo_user, limit=100)
        assert len(rows) == DEMO_COUNT

    def test_none_limit_returns_full_history(self, demo_user):
        assert len(db.get_expenses(demo_user, limit=None)) == DEMO_COUNT

    def test_empty_user_returns_empty_list(self, make_user):
        uid = make_user()
        assert db.get_expenses(uid) == []

    def test_scoped_to_user(self, insert_expense, make_user):
        a = make_user(email="a@spendly.com")
        b = make_user(email="b@spendly.com")
        insert_expense(a, 10.0, "Food", "2026-01-01", "a-only")
        insert_expense(b, 20.0, "Bills", "2026-01-02", "b-only")
        a_rows = db.get_expenses(a)
        assert len(a_rows) == 1
        assert a_rows[0]["description"] == "a-only"
        assert all(r["user_id"] == a for r in a_rows)


# =========================================================================== #
# DB helper contracts: get_category_breakdown                                 #
# =========================================================================== #
class TestGetCategoryBreakdown:
    def test_returns_named_columns(self, demo_user):
        rows = db.get_category_breakdown(demo_user)
        keys = rows[0].keys()
        assert "category" in keys
        assert "total" in keys
        assert "count" in keys

    def test_grouped_and_counts_per_category(self, demo_user):
        rows = {r["category"]: r for r in db.get_category_breakdown(demo_user)}
        # Food appears twice in the seed data (42.50 + 33.75).
        assert rows["Food"]["count"] == 2
        assert round(rows["Food"]["total"], 2) == 76.25
        assert rows["Bills"]["count"] == 1
        assert round(rows["Bills"]["total"], 2) == 120.00

    def test_ordered_by_total_desc(self, demo_user):
        totals = [r["total"] for r in db.get_category_breakdown(demo_user)]
        assert totals == sorted(totals, reverse=True)
        assert db.get_category_breakdown(demo_user)[0]["category"] == "Bills"

    def test_only_categories_with_expenses_appear(self, demo_user):
        cats = {r["category"] for r in db.get_category_breakdown(demo_user)}
        # 7 distinct categories used (Food twice) -> 7 rows, no empty ones.
        assert cats == {
            "Food", "Transport", "Bills", "Health",
            "Entertainment", "Shopping", "Other",
        }

    def test_empty_user_returns_empty_list(self, make_user):
        uid = make_user()
        assert db.get_category_breakdown(uid) == []

    def test_scoped_to_user(self, insert_expense, make_user):
        a = make_user(email="a@spendly.com")
        b = make_user(email="b@spendly.com")
        insert_expense(a, 10.0, "Food", "2026-01-01")
        insert_expense(b, 99.0, "Bills", "2026-01-02")
        cats = {r["category"] for r in db.get_category_breakdown(a)}
        assert cats == {"Food"}


# =========================================================================== #
# DB helper contracts: get_summary (enriched)                                 #
# =========================================================================== #
class TestGetSummary:
    def test_count_and_total(self, demo_user):
        s = db.get_summary(demo_user)
        assert s["count"] == DEMO_COUNT
        assert round(s["total"], 2) == DEMO_TOTAL  # 386.25

    def test_average(self, demo_user):
        s = db.get_summary(demo_user)
        assert round(s["average"], 2) == round(DEMO_TOTAL / DEMO_COUNT, 2)  # 48.28

    def test_top_category_is_highest_summed(self, demo_user):
        # Bills (120) is the single largest category total.
        assert db.get_summary(demo_user)["top_category"] == "Bills"

    def test_top_category_uses_sum_not_count(self, insert_expense, make_user):
        uid = make_user()
        # Food occurs 3x but sums to 30; Bills occurs once summing to 25.
        insert_expense(uid, 10.0, "Food", "2026-01-01")
        insert_expense(uid, 10.0, "Food", "2026-01-02")
        insert_expense(uid, 10.0, "Food", "2026-01-03")
        insert_expense(uid, 25.0, "Bills", "2026-01-04")
        assert db.get_summary(uid)["top_category"] == "Food"

    def test_month_total_filters_current_month(
        self, insert_expense, make_user, current_month
    ):
        uid = make_user()
        this_month_date = f"{current_month}-15"
        insert_expense(uid, 40.0, "Food", this_month_date, "this month")
        insert_expense(uid, 100.0, "Bills", "2000-01-15", "old month")
        s = db.get_summary(uid)
        assert round(s["month_total"], 2) == 40.00
        assert round(s["total"], 2) == 140.00

    def test_empty_user_defensive_zeros(self, make_user):
        uid = make_user()
        s = db.get_summary(uid)
        assert s["count"] == 0
        assert s["total"] == 0
        assert s["average"] == 0
        assert s["month_total"] == 0
        # Spec: top_category is NULL/empty (never a crash) when no expenses.
        assert not s["top_category"]

    def test_scoped_to_user(self, insert_expense, make_user):
        a = make_user(email="a@spendly.com")
        b = make_user(email="b@spendly.com")
        insert_expense(a, 10.0, "Food", "2026-01-01")
        insert_expense(b, 500.0, "Bills", "2026-01-02")
        assert round(db.get_summary(a)["total"], 2) == 10.00
        assert db.get_summary(a)["count"] == 1

    def test_breakdown_totals_sum_to_summary_total(self, demo_user):
        # DoD: category breakdown totals sum to the overall summary total.
        breakdown = db.get_category_breakdown(demo_user)
        summary = db.get_summary(demo_user)
        assert round(sum(r["total"] for r in breakdown), 2) == round(
            summary["total"], 2
        )


# =========================================================================== #
# Auth / login-protection of the reporting routes                             #
# =========================================================================== #
class TestAuthProtection:
    def test_profile_anonymous_redirects_to_login(self, client):
        resp = client.get("/profile")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_transactions_anonymous_redirects_to_login(self, client):
        resp = client.get("/transactions")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_anonymous_transactions_leaks_no_expense_data(self, client, demo_user):
        # Even though demo data exists, an anonymous visitor gets a redirect,
        # never rendered expense rows.
        resp = client.get("/transactions")
        assert resp.status_code == 302
        assert b"Restaurant" not in resp.data
        assert b"Groceries" not in resp.data


# =========================================================================== #
# /profile route (enriched)                                                   #
# =========================================================================== #
class TestProfileRoute:
    def test_renders_ok(self, demo_client):
        assert demo_client.get("/profile").status_code == 200

    def test_shows_summary_figures(self, demo_client):
        data = demo_client.get("/profile").data
        assert b"$386.25" in data      # total
        assert b"48.28" in data        # average
        assert b"Bills" in data        # top category

    def test_has_view_all_link_to_transactions(self, demo_client):
        data = demo_client.get("/profile").data
        assert b"/transactions" in data
        assert b"View all" in data

    def test_shows_recent_transactions_preview(self, demo_client):
        # DoD: /profile shows a "Recent transactions" preview (<=5, newest first).
        data = demo_client.get("/profile").data
        assert b"Restaurant" in data          # newest expense description
        assert b"Groceries" not in data       # 8th oldest -> excluded from top 5

    def test_shows_category_breakdown_section(self, demo_client):
        # DoD: /profile shows a "Spending by category" breakdown. Food's summed
        # total (76.25) never equals any single seeded amount, so it is a clean
        # signal that a grouped breakdown is rendered.
        data = demo_client.get("/profile").data
        assert b"$76.25" in data

    def test_empty_user_shows_zeroes(self, client, make_user):
        uid = make_user(email="empty@spendly.com")
        login_session(client, uid, "Empty User")
        resp = client.get("/profile")
        assert resp.status_code == 200
        assert b"$0.00" in resp.data
        assert b"None" not in resp.data

    def test_never_exposes_password_hash(self, demo_client, demo_user):
        user = db.get_user_by_id(demo_user)
        data = demo_client.get("/profile").data
        assert user["password_hash"].encode() not in data
        assert b"password_hash" not in data
        assert b"demo123" not in data


# =========================================================================== #
# /transactions route                                                         #
# =========================================================================== #
class TestTransactionsRoute:
    def test_renders_ok(self, demo_client):
        assert demo_client.get("/transactions").status_code == 200

    def test_lists_all_expenses(self, demo_client):
        data = demo_client.get("/transactions").data
        # Descriptions across the full history (not just the recent 5).
        for desc in (b"Restaurant", b"Groceries", b"Electricity", b"Bus pass"):
            assert desc in data

    def test_shows_date_category_description_amount(self, demo_client):
        data = demo_client.get("/transactions").data
        assert b"2026-07-15" in data      # date
        assert b"Bills" in data           # category
        assert b"Electricity" in data     # description
        assert b"$120.00" in data         # amount (formatted)

    def test_newest_first_order(self, demo_client):
        data = demo_client.get("/transactions").data.decode()
        assert data.index("2026-07-15") < data.index("2026-07-01")

    def test_shows_category_breakdown(self, demo_client):
        # DoD: /transactions shows the category breakdown alongside the list.
        # Food's grouped total 76.25 is the breakdown signal.
        data = demo_client.get("/transactions").data
        assert b"$76.25" in data

    def test_empty_state(self, client, make_user):
        uid = make_user(email="empty@spendly.com")
        login_session(client, uid, "Empty User")
        resp = client.get("/transactions")
        assert resp.status_code == 200
        assert b"No transactions" in resp.data

    def test_scoped_to_current_user(self, client, insert_expense, make_user):
        a = make_user(email="a@spendly.com")
        b = make_user(email="b@spendly.com")
        insert_expense(a, 11.0, "Food", "2026-03-01", "alice-lunch")
        insert_expense(b, 22.0, "Bills", "2026-03-02", "bob-rent")
        login_session(client, b, "Bob")
        data = client.get("/transactions").data
        assert b"bob-rent" in data
        assert b"alice-lunch" not in data

    def test_never_exposes_password_hash(self, demo_client, demo_user):
        user = db.get_user_by_id(demo_user)
        data = demo_client.get("/transactions").data
        assert user["password_hash"].encode() not in data
        assert b"password_hash" not in data


# =========================================================================== #
# Session-aware navbar                                                         #
# =========================================================================== #
class TestNavbar:
    def test_transactions_link_hidden_when_signed_out(self, client):
        data = client.get("/").data
        assert b"Transactions</a>" not in data

    def test_transactions_link_shown_when_signed_in(self, demo_client):
        data = demo_client.get("/profile").data
        assert b"Transactions</a>" in data
        assert b"/transactions" in data
