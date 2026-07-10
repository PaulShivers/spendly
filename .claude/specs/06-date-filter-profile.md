# Spec: Date Filter for Profile Page

## Overview
Give the signed-in user control over the time window their profile reports on. Today the
profile's stat cards, recent-transactions preview, and category breakdown (all built in
Step 5) summarise a user's *entire* history with no way to narrow the period. This step
adds a **date filter** to `/profile`: a row of quick preset chips (This month, Last 30
days, This year, All time) plus a custom **start/end** date-range form. Choosing a period
re-scopes the whole profile reporting — every stat card, the recent list, and the
breakdown reflect only expenses inside the selected range. It is a read-only enhancement
of the Step 5 reporting layer (no new data, no writes), so it sits at Step 6, after the
reporting routes and before the add/edit/delete expense features.

## Depends on
- Step 1 — Database setup (`expenses` table, `get_db()`, parameterised-query pattern).
- Step 3 — Login and Logout (`session["user_id"]` identifies the current user).
- Step 5 — Profile & reporting routes (the `/profile` route and the `get_summary`,
  `get_expenses`, `get_category_breakdown` helpers this step extends).

## Routes
- `GET /profile` — **modify existing** — logged-in — now reads optional query parameters
  and passes the resolved date range to the reporting helpers:
  - `preset` — one of `month`, `30d`, `year`, `all`.
  - `start`, `end` — custom bounds, each `YYYY-MM-DD`.
  Resolution order: if `preset` is present and valid, compute `start_date`/`end_date`
  from it; else use the custom `start`/`end` if present; else default to **All time**
  (`start_date = end_date = None`, i.e. current Step 5 behaviour). The route passes the
  resolved range, the active preset, and the raw `start`/`end` strings to the template so
  the filter UI can show its active state and keep the inputs populated. Keep the existing
  anonymous-visitor redirect to `/login`.

No other new routes. `/transactions` and the Step 7–9 placeholders are unchanged.

## Database changes
No schema changes. `expenses` already has the `date` column (`YYYY-MM-DD` TEXT); because
dates are zero-padded ISO strings, `date >= ?` / `date <= ?` compares correctly and stays
parameterised. Verified against `database/db.py`.

Extend three existing read helpers in `database/db.py` with two optional keyword args,
`start_date=None` and `end_date=None`, appended as parameterised `AND date >= ?` /
`AND date <= ?` clauses only when provided (all keep the existing `user_id = ?` scope and
`try/finally` close):
- `get_expenses(user_id, limit=None, start_date=None, end_date=None)` — add the date
  bounds before the `ORDER BY`; `LIMIT` stays a parameter.
- `get_category_breakdown(user_id, start_date=None, end_date=None)` — add the date bounds
  before `GROUP BY`.
- `get_summary(user_id, start_date=None, end_date=None)` — apply the date bounds to both
  the aggregate row (`count`, `total`, `average`, and the `top_category` sub-query) so the
  headline figures reflect the range. `total`/`average`/`count` keep their `COALESCE`
  zero-defaults. The existing `month_total` key stays in the returned dict (computed as
  before) but is no longer rendered by the profile — the "This month" card is replaced by
  a range-aware "Expenses" (count) card.

Because the new args default to `None`, all current callers (including `/transactions`)
behave exactly as before.

## Templates
- **Modify:** `templates/profile.html`
  - Add a **filter bar** above the stat grid:
    - Preset chips rendered as links to `/profile?preset=month|30d|year|all`; the active
      one gets an `--active` modifier class and `aria-current="page"`.
    - A custom-range `<form method="get" action="/profile">` with two
      `<input type="date" name="start">` / `name="end">` (pre-filled from the current
      values) and an **Apply** button reusing `.btn-primary`.
    - A short caption stating the active period (e.g. "Showing Jul 1 – Jul 10, 2026" or
      "Showing all time").
  - Replace the "This month" stat card with an **Expenses** card bound to
    `summary["count"]`; the four cards (Total spent, Expenses, Average expense, Top
    category) now all reflect the active range.
  - Recent list and breakdown markup are unchanged structurally — they just receive
    range-filtered data. Ensure the empty states ("No transactions yet." / "No spending to
    break down yet.") also cover "no expenses in this range".
  - Money stays `${{ "{:,.2f}".format(x) }}`; no hardcoded colours.
- **Modify:** `static/css/profile.css`
  - Add styles for `.filter-bar`, the preset chips (default + active), the range form and
    its inputs, and the period caption, using only `style.css` CSS variables
    (`--accent`, `--accent-light`, `--paper-card`, `--border`, `--radius-md`/`--radius-sm`,
    `--ink-muted`, etc.). Make it wrap cleanly on the ≤600px breakpoint alongside the
    existing responsive block.

No new template files. (Filtering `/transactions` is explicitly out of scope for this step.)

## Files to change
- `app.py` — `/profile` route: parse `preset`/`start`/`end`, resolve to `start_date`/
  `end_date` (using `datetime`/`date`/`timedelta`, already importable), pass the range to
  `get_summary`, `get_expenses(..., limit=5, ...)`, and `get_category_breakdown`, and pass
  `active_preset` + raw `start`/`end` + a human period label to the template.
- `database/db.py` — add `start_date`/`end_date` params to `get_expenses`,
  `get_category_breakdown`, and `get_summary`.
- `templates/profile.html` — filter bar + range-aware stat cards.
- `static/css/profile.css` — filter-bar styles.

## File to create
No new files.

## New dependencies
No new dependencies. Preset date maths uses the standard-library `datetime`/`date`/
`timedelta`; date filtering uses `sqlite3` parameters. Flask (`request.args`,
`render_template`, `redirect`, `url_for`) is already imported.

## Rules for implementation
- No SQLAlchemy or ORMs — `sqlite3` via `get_db()` only.
- Parameterised queries only — the date bounds and `LIMIT` are bound parameters, never
  string-formatted / f-strings.
- Every reporting query stays scoped by `user_id = ?`; a user only ever sees their own
  expenses.
- Passwords hashed with werkzeug — untouched here; never expose/log `password_hash`.
- Use CSS variables — never hardcode hex; reuse tokens/classes from `style.css`.
- All templates extend `base.html`; the profile page keeps doing so.
- Login-protect `/profile` — a missing `session["user_id"]` redirects to `/login` before
  any query runs.
- Display-only formatting — dates stay stored as `YYYY-MM-DD`, amount stays REAL; format
  money/period labels in the route/template.
- Defensive/empty cases — an empty range shows `0` / `$0.00`, "—" for top category, and
  the empty states, never `None` or a 500 (keep `COALESCE`).
- Robust input handling — `start`/`end` that are missing or not valid `YYYY-MM-DD` are
  ignored (that bound is treated as absent); an unknown `preset` falls back to All time.
  No user input reaches SQL except as a bound parameter.
- Keep the new helper args optional (default `None`) so `/transactions` and any other
  caller keep working unchanged.

## Definition of done
- [ ] Signed in as the demo account (`demo@spendly.com` / `demo123`), `/profile` shows the
      filter bar: four preset chips + a start/end date form + an Apply button.
- [ ] Clicking **This month** / **Last 30 days** / **This year** re-scopes all four stat
      cards, the recent list, and the breakdown to that period; the active chip is
      visibly highlighted and a caption states the period.
- [ ] **All time** restores the full-history figures (identical to the pre-filter
      profile).
- [ ] Submitting a custom start/end range filters every profile section to that inclusive
      range, and the date inputs stay populated with the submitted values.
- [ ] The breakdown totals still sum to the "Total spent" figure shown for the same range.
- [ ] A range with no matching expenses shows `0` / `$0.00`, "—" top category, and the
      empty states — no `None`, no 500.
- [ ] Missing/malformed `start`, `end`, or `preset` values do not crash the page (they
      fall back to All time / an ignored bound).
- [ ] `/profile` while signed out still redirects to `/login`; `/transactions` is
      unchanged (still all-time).
- [ ] All new/edited SQL is parameterised (date bounds + `LIMIT`); queries stay scoped by
      `user_id`.
- [ ] No hardcoded hex values in the new markup/CSS; the page still extends `base.html`
      and the filter bar wraps cleanly on mobile.
- [ ] App starts and serves `/profile` (filtered and unfiltered) without a 500.
