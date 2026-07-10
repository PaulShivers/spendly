"""Tests for Step 6 — Date Filter for Profile Page.

Spec: .claude/specs/06-date-filter-profile.md

Every assertion is derived from the spec's "Definition of done" and its
"Rules for implementation" / "Database changes" sections, NOT from the current
implementation. The implementation is read only for wiring (route name, form
field names, helper signatures, session keys). Where the implementation
diverges from the spec, the test is written to the spec and left failing; such
divergences are called out in the run report.

Preset windows (This month / Last 30 days / This year) are anchored to
``date.today()`` by the spec, so preset tests seed data *relative to today*
(computed here with stdlib ``datetime``) instead of relying on the demo seed,
keeping the date boundaries deterministic regardless of the calendar day.
Custom-range and helper tests use fixed ``YYYY-MM-DD`` dates.
"""

from datetime import date, timedelta

import database.db as db
from tests.conftest import login_session


# --------------------------------------------------------------------------- #
# Local helpers                                                               #
# --------------------------------------------------------------------------- #
def _seed(insert_expense, uid, rows):
    """rows: iterable of (amount, category, date, description)."""
    for amount, category, d, desc in rows:
        insert_expense(uid, amount, category, d, desc)


def _signed_in(client, make_user, insert_expense, rows, email="u@spendly.com"):
    """Create a user, seed `rows`, sign the client in, return the user id."""
    uid = make_user(email=email)
    _seed(insert_expense, uid, rows)
    login_session(client, uid, "U")
    return uid


# =========================================================================== #
# DoD #1 — Filter bar renders (four preset chips + start/end form + Apply)     #
# =========================================================================== #
class TestFilterBarRenders:
    def test_four_preset_chips_present(self, demo_client):
        data = demo_client.get("/profile").data
        for label in (b"This month", b"Last 30 days", b"This year", b"All time"):
            assert label in data

    def test_preset_chips_link_to_preset_query(self, demo_client):
        data = demo_client.get("/profile").data.decode()
        for key in ("month", "30d", "year", "all"):
            assert f"preset={key}" in data

    def test_custom_range_form_has_start_and_end_date_inputs(self, demo_client):
        data = demo_client.get("/profile").data.decode()
        assert 'name="start"' in data
        assert 'name="end"' in data
        assert 'type="date"' in data

    def test_apply_button_present(self, demo_client):
        data = demo_client.get("/profile").data
        assert b"Apply" in data

    def test_form_is_a_get_to_profile(self, demo_client):
        data = demo_client.get("/profile").data.decode().lower()
        assert 'method="get"' in data


# =========================================================================== #
# DoD #2 — Presets re-scope every section; active chip + caption               #
# =========================================================================== #
class TestPresetReScoping:
    def test_this_month_rescopes(self, client, make_user, insert_expense):
        today = date.today()
        first = today.replace(day=1)
        prev_last = first - timedelta(days=1)
        _signed_in(
            client, make_user, insert_expense,
            rows=[
                (100.00, "Food", first.isoformat(), "in-first"),
                (50.00, "Bills", today.isoformat(), "in-today"),
                (999.00, "Shopping", prev_last.isoformat(), "out-prevmonth"),
            ],
        )
        data = client.get("/profile?preset=month").data
        assert b"$150.00" in data          # 100 + 50, in-month only
        assert b"$999.00" not in data      # previous month excluded

    def test_this_year_rescopes(self, client, make_user, insert_expense):
        today = date.today()
        jan1 = today.replace(month=1, day=1)
        dec31_prev = date(today.year - 1, 12, 31)
        _signed_in(
            client, make_user, insert_expense,
            rows=[
                (200.00, "Food", jan1.isoformat(), "in-jan1"),
                (50.00, "Bills", today.isoformat(), "in-today"),
                (777.00, "Shopping", dec31_prev.isoformat(), "out-lastyear"),
            ],
        )
        data = client.get("/profile?preset=year").data
        assert b"$250.00" in data          # 200 + 50, this year only
        assert b"$777.00" not in data      # last year excluded

    def test_last_30_days_rescopes(self, client, make_user, insert_expense):
        today = date.today()
        _signed_in(
            client, make_user, insert_expense,
            rows=[
                (30.00, "Food", today.isoformat(), "in-today"),
                (20.00, "Bills", (today - timedelta(days=10)).isoformat(), "in-10ago"),
                (500.00, "Shopping", (today - timedelta(days=60)).isoformat(), "out-60ago"),
            ],
        )
        data = client.get("/profile?preset=30d").data
        assert b"$50.00" in data           # 30 + 20 inside window
        assert b"$500.00" not in data      # 60 days ago excluded

    def test_active_chip_is_highlighted(self, demo_client):
        data = demo_client.get("/profile?preset=month").data
        # Spec: active chip gets an --active modifier + aria-current="page".
        assert b"filter-chip--active" in data
        assert b'aria-current="page"' in data

    def test_caption_states_the_active_period(self, demo_client):
        assert b"Showing This month" in demo_client.get("/profile?preset=month").data
        assert b"Showing Last 30 days" in demo_client.get("/profile?preset=30d").data
        assert b"Showing This year" in demo_client.get("/profile?preset=year").data


# =========================================================================== #
# DoD #3 — All time restores full-history figures                              #
# =========================================================================== #
class TestAllTimeRestoresFullHistory:
    def test_preset_all_matches_unfiltered(self, client, make_user, insert_expense):
        _signed_in(
            client, make_user, insert_expense,
            rows=[
                (111.00, "Food", "2020-01-01", "very-old"),
                (222.00, "Bills", "2026-06-15", "midrange"),
            ],
        )
        default = client.get("/profile").data
        alltime = client.get("/profile?preset=all").data
        # Full history total = 333.00, present in both views.
        assert b"$333.00" in default
        assert b"$333.00" in alltime
        assert b"$111.00" in alltime       # the very-old expense is included

    def test_default_marks_all_time_active(self, demo_client):
        # No params -> All time default -> the All time chip is the active one.
        data = demo_client.get("/profile").data
        assert b'aria-current="page"' in data
        assert b"Showing All time" in data

    def test_all_time_full_total_matches_demo_history(self, demo_client):
        # Demo seed spans 2026-07-01..2026-07-15 summing to 386.25.
        data = demo_client.get("/profile?preset=all").data
        assert b"$386.25" in data


# =========================================================================== #
# DoD #4 — Custom start/end range filters inclusively; inputs stay populated    #
# =========================================================================== #
class TestCustomRange:
    def test_range_filters_every_section(self, client, make_user, insert_expense):
        _signed_in(
            client, make_user, insert_expense,
            rows=[
                (111.00, "Food", "2026-06-10", "in-a"),
                (222.00, "Bills", "2026-06-20", "in-b"),
                (888.00, "Shopping", "2026-05-31", "out-before"),
                (777.00, "Health", "2026-07-01", "out-after"),
            ],
        )
        data = client.get("/profile?start=2026-06-01&end=2026-06-30").data
        assert b"$333.00" in data          # 111 + 222 inside June
        assert b"$888.00" not in data      # before range excluded
        assert b"$777.00" not in data      # after range excluded

    def test_date_inputs_prefilled_with_submitted_values(self, demo_client):
        data = demo_client.get("/profile?start=2026-06-01&end=2026-06-30").data.decode()
        assert 'value="2026-06-01"' in data
        assert 'value="2026-06-30"' in data

    def test_active_period_caption_shown_for_custom_range(self, demo_client):
        data = demo_client.get("/profile?start=2026-06-01&end=2026-06-30").data
        assert b"Showing" in data
        # A custom range is not "all time".
        assert b"Showing All time" not in data


# =========================================================================== #
# DoD — inclusive boundary: start day and end day are both included            #
# =========================================================================== #
class TestInclusiveBoundary:
    def test_route_includes_start_and_end_days(self, client, make_user, insert_expense):
        _signed_in(
            client, make_user, insert_expense,
            rows=[
                (100.00, "Food", "2026-06-10", "on-start"),
                (200.00, "Bills", "2026-06-20", "on-end"),
                (55.00, "Shopping", "2026-06-09", "day-before"),
                (66.00, "Health", "2026-06-21", "day-after"),
            ],
        )
        data = client.get("/profile?start=2026-06-10&end=2026-06-20").data
        assert b"$55.00" not in data       # 06-09 excluded (before start)
        assert b"$66.00" not in data       # 06-21 excluded (after end)
        assert b"$100.00" in data          # start day included
        assert b"$200.00" in data          # end day included
        assert b"$300.00" in data          # range total = 100 + 200

    def test_helper_includes_both_boundaries(self, make_user, insert_expense):
        uid = make_user()
        _seed(insert_expense, uid, [
            (10.0, "Food", "2026-06-10", "on-start"),
            (20.0, "Bills", "2026-06-20", "on-end"),
            (99.0, "Shopping", "2026-06-09", "before"),
            (99.0, "Health", "2026-06-21", "after"),
        ])
        rows = db.get_expenses(uid, start_date="2026-06-10", end_date="2026-06-20")
        descs = {r["description"] for r in rows}
        assert descs == {"on-start", "on-end"}
        s = db.get_summary(uid, "2026-06-10", "2026-06-20")
        assert s["count"] == 2
        assert round(s["total"], 2) == 30.00


# =========================================================================== #
# DoD #5 — Breakdown totals sum to the "Total spent" figure for the same range #
# =========================================================================== #
class TestBreakdownSumsToTotal:
    def test_helper_breakdown_sum_equals_summary_total_for_range(
        self, make_user, insert_expense
    ):
        uid = make_user()
        _seed(insert_expense, uid, [
            (10.0, "Food", "2026-06-05", None),
            (20.0, "Food", "2026-06-06", None),
            (30.0, "Bills", "2026-06-07", None),
            (40.0, "Health", "2026-06-08", None),
            (999.0, "Shopping", "2026-05-01", "out-of-range"),
        ])
        s, e = "2026-06-01", "2026-06-30"
        breakdown = db.get_category_breakdown(uid, s, e)
        summary = db.get_summary(uid, s, e)
        assert round(sum(r["total"] for r in breakdown), 2) == round(summary["total"], 2)
        assert round(summary["total"], 2) == 100.00

    def test_rendered_total_card_matches_breakdown_total(
        self, client, make_user, insert_expense
    ):
        _signed_in(
            client, make_user, insert_expense,
            rows=[
                (111.00, "Food", "2026-06-10", "in-a"),
                (222.00, "Bills", "2026-06-20", "in-b"),
                (500.00, "Shopping", "2026-05-01", "out"),
            ],
        )
        data = client.get("/profile?start=2026-06-01&end=2026-06-30").data
        # Total-spent card and breakdown total both reflect 333.00 for the range.
        assert data.count(b"$333.00") >= 2


# =========================================================================== #
# DoD #6 — A range with no matching expenses -> zeros + empty states, no 500    #
# =========================================================================== #
class TestEmptyRange:
    def test_empty_range_shows_zeros_and_empty_states(self, demo_client):
        # Demo data is all in 2026; this window matches nothing.
        resp = demo_client.get("/profile?start=2999-01-01&end=2999-12-31")
        assert resp.status_code == 200
        data = resp.data
        assert b"$0.00" in data
        assert b"No transactions yet." in data
        assert b"No spending to break down yet." in data
        assert b"\xe2\x80\x94" in data     # em dash "—" for top category
        assert b"None" not in data

    def test_empty_range_helpers_return_defensive_zeros(self, make_user, insert_expense):
        uid = make_user()
        _seed(insert_expense, uid, [(50.0, "Food", "2026-06-15", None)])
        s = db.get_summary(uid, "2999-01-01", "2999-12-31")
        assert s["count"] == 0
        assert s["total"] == 0
        assert s["average"] == 0
        assert not s["top_category"]
        assert db.get_expenses(uid, start_date="2999-01-01", end_date="2999-12-31") == []
        assert db.get_category_breakdown(uid, "2999-01-01", "2999-12-31") == []


# =========================================================================== #
# DoD #7 — Missing/malformed start/end/preset fall back without crashing        #
# =========================================================================== #
class TestRobustInput:
    def test_malformed_dates_fall_back_to_all_time(self, client, make_user, insert_expense):
        _signed_in(
            client, make_user, insert_expense,
            rows=[
                (111.00, "Food", "2020-01-01", "old"),
                (222.00, "Bills", "2026-06-15", "mid"),
            ],
        )
        resp = client.get("/profile?start=not-a-date&end=also-bad")
        assert resp.status_code == 200
        # Both bounds ignored -> all time -> full history total 333.00.
        assert b"$333.00" in resp.data
        assert b"$111.00" in resp.data     # the old expense is still shown

    def test_unknown_preset_falls_back_to_all_time(self, client, make_user, insert_expense):
        _signed_in(
            client, make_user, insert_expense,
            rows=[
                (111.00, "Food", "2020-01-01", "old"),
                (222.00, "Bills", "2026-06-15", "mid"),
            ],
        )
        resp = client.get("/profile?preset=decade")
        assert resp.status_code == 200
        assert b"$333.00" in resp.data
        assert b"$111.00" in resp.data

    def test_one_valid_one_malformed_bound_ignores_bad_bound(
        self, client, make_user, insert_expense
    ):
        # Spec rule: a malformed bound is treated as absent (open-ended range).
        _signed_in(
            client, make_user, insert_expense,
            rows=[
                (500.00, "Food", "2026-05-01", "out-before"),
                (111.00, "Bills", "2026-06-15", "in-a"),
                (222.00, "Health", "2026-07-01", "in-b"),
            ],
        )
        resp = client.get("/profile?start=2026-06-01&end=garbage")
        assert resp.status_code == 200
        data = resp.data
        assert b"$500.00" not in data      # before valid start -> excluded
        assert b"$333.00" in data          # 111 + 222 from 06-01 onwards
        # Only the valid start bound is echoed back; the bad end stays empty.
        assert 'value="2026-06-01"' in data.decode()

    def test_valid_preset_wins_over_custom_range(self, client, make_user, insert_expense):
        # Resolution order: a valid preset beats custom start/end.
        _signed_in(
            client, make_user, insert_expense,
            rows=[
                (222.00, "Food", "2026-06-15", "june"),
                (777.00, "Bills", "2026-07-01", "july"),
            ],
        )
        data = client.get("/profile?preset=all&start=2026-06-01&end=2026-06-30").data
        # preset=all wins -> July row (outside the June custom range) still shows.
        assert b"$777.00" in data


# =========================================================================== #
# DoD #8 — Auth guard + /transactions unchanged (all-time)                      #
# =========================================================================== #
class TestAuthAndTransactionsUnchanged:
    def test_profile_signed_out_redirects_to_login(self, client):
        resp = client.get("/profile")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_profile_signed_out_with_filter_leaks_no_data(self, client, demo_user):
        resp = client.get("/profile?preset=all&start=2026-01-01&end=2026-12-31")
        assert resp.status_code == 302
        assert b"Restaurant" not in resp.data
        assert b"Groceries" not in resp.data

    def test_transactions_still_all_time(self, client, make_user, insert_expense):
        # A very old expense must still show on /transactions (no date filter).
        _signed_in(
            client, make_user, insert_expense,
            rows=[
                (12.00, "Food", "2000-01-01", "ancient"),
                (34.00, "Bills", date.today().isoformat(), "recent"),
            ],
        )
        data = client.get("/transactions").data
        assert b"ancient" in data
        assert b"recent" in data

    def test_transactions_ignores_filter_params(self, client, make_user, insert_expense):
        # /transactions is out of scope for filtering; params must not narrow it.
        _signed_in(
            client, make_user, insert_expense,
            rows=[(12.00, "Food", "2000-01-01", "ancient")],
        )
        data = client.get("/transactions?start=2026-01-01&end=2026-12-31").data
        assert b"ancient" in data


# =========================================================================== #
# Rules — user_id scoping still holds under a filter                            #
# =========================================================================== #
class TestScopingUnderFilter:
    def test_route_scopes_filtered_data_to_current_user(
        self, client, make_user, insert_expense
    ):
        a = make_user(email="a@spendly.com")
        b = make_user(email="b@spendly.com")
        insert_expense(a, 11.00, "Food", "2026-06-10", "alice-june")
        insert_expense(b, 22.00, "Bills", "2026-06-10", "bob-june")
        login_session(client, b, "Bob")
        data = client.get("/profile?start=2026-06-01&end=2026-06-30").data
        assert b"bob-june" in data
        assert b"alice-june" not in data
        assert b"$22.00" in data
        assert b"$11.00" not in data

    def test_helpers_scope_by_user_under_range(self, make_user, insert_expense):
        a = make_user(email="a@spendly.com")
        b = make_user(email="b@spendly.com")
        insert_expense(a, 11.00, "Food", "2026-06-10")
        insert_expense(b, 22.00, "Bills", "2026-06-10")
        s, e = "2026-06-01", "2026-06-30"
        assert round(db.get_summary(a, s, e)["total"], 2) == 11.00
        assert {r["category"] for r in db.get_category_breakdown(a, s, e)} == {"Food"}
        assert all(r["user_id"] == a for r in db.get_expenses(a, start_date=s, end_date=e))


# =========================================================================== #
# Database changes — optional args default None (regression) + range contracts  #
# =========================================================================== #
class TestHelperOptionalArgs:
    def test_get_expenses_defaults_unchanged(self, demo_user):
        # No date args -> full history (unchanged Step 5 behaviour).
        assert len(db.get_expenses(demo_user)) == 8

    def test_get_summary_defaults_unchanged(self, demo_user):
        s = db.get_summary(demo_user)
        assert s["count"] == 8
        assert round(s["total"], 2) == 386.25

    def test_get_category_breakdown_defaults_unchanged(self, demo_user):
        assert len(db.get_category_breakdown(demo_user)) == 7

    def test_get_summary_still_returns_month_total_key(self, make_user, insert_expense):
        # Spec: month_total key stays in the returned dict even with a range.
        uid = make_user()
        _seed(insert_expense, uid, [(10.0, "Food", "2026-06-15", None)])
        s = db.get_summary(uid, "2026-06-01", "2026-06-30")
        assert "month_total" in s

    def test_get_expenses_limit_still_parameterised_with_range(
        self, make_user, insert_expense
    ):
        uid = make_user()
        _seed(insert_expense, uid, [
            (1.0, "Food", "2026-06-01", "a"),
            (2.0, "Food", "2026-06-02", "b"),
            (3.0, "Food", "2026-06-03", "c"),
            (99.0, "Food", "2026-07-10", "out"),
        ])
        rows = db.get_expenses(uid, limit=2, start_date="2026-06-01", end_date="2026-06-30")
        assert len(rows) == 2
        # newest-first inside the range
        assert rows[0]["description"] == "c"
        descs = {r["description"] for r in rows}
        assert "out" not in descs

    def test_get_summary_average_reflects_range(self, make_user, insert_expense):
        uid = make_user()
        _seed(insert_expense, uid, [
            (10.0, "Food", "2026-06-10", None),
            (30.0, "Bills", "2026-06-20", None),
            (1000.0, "Shopping", "2026-05-01", "out"),
        ])
        s = db.get_summary(uid, "2026-06-01", "2026-06-30")
        assert s["count"] == 2
        assert round(s["total"], 2) == 40.00
        assert round(s["average"], 2) == 20.00

    def test_get_summary_top_category_reflects_range(self, make_user, insert_expense):
        uid = make_user()
        _seed(insert_expense, uid, [
            (5.0, "Food", "2026-06-10", None),
            (60.0, "Bills", "2026-06-11", None),
            (999.0, "Shopping", "2026-05-01", "out"),   # biggest overall, out of range
        ])
        s = db.get_summary(uid, "2026-06-01", "2026-06-30")
        assert s["top_category"] == "Bills"


# =========================================================================== #
# Security — password hash never rendered, even under a filter                  #
# =========================================================================== #
class TestSecurity:
    def test_password_hash_not_exposed_under_filter(self, demo_client, demo_user):
        user = db.get_user_by_id(demo_user)
        data = demo_client.get("/profile?start=2026-01-01&end=2026-12-31").data
        assert user["password_hash"].encode() not in data
        assert b"password_hash" not in data
        assert b"demo123" not in data
