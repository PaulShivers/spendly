# Spec: Profile and Reporting Routes

## Overview
Turn Spendly's read-only profile into a real financial home base by building the
**query/reporting backend** on top of the seeded `expenses` data. Step 4 gave the
signed-in user a profile page that shows only two headline numbers (total spent and
expense count) pulled from a single aggregate helper. This step adds the backend
routes and DB helpers that surface the rest of the user's spending: a full
**transaction history**, an **enriched summary** (this-month total, average
expense, top category alongside the existing count/total), and a **category
breakdown** (spend grouped per category). The profile page is enriched to preview a
few recent transactions plus the category breakdown, and a dedicated
`/transactions` page lists the complete history. This is the read layer that the
add/edit/delete expense features (Steps 7–9) will later feed into, so it sits at
Step 5 — after authentication and the basic profile, before any write operations on
expenses exist.

## Depends on
- Step 1 — Database setup (`expenses` table, `get_db()`, `init_db()`, seed data).
- Step 3 — Login and Logout (the Flask session that identifies the current user via
  `session["user_id"]`).
- Step 4 — Profile Page (the login-protected `/profile` route and `profile.html`
  that this step enriches; the existing `get_expense_summary()` helper).

## Routes
- `GET /profile` — **modify existing** — logged-in — in addition to the current
  user + summary, also pass recent transactions and the category breakdown to the
  template. Keep the existing anonymous-visitor redirect to `/login`.
- `GET /transactions` — **new** — logged-in — render the full transaction history
  for the signed-in user (all expenses, newest first) plus the category breakdown.
  If there is no active session (`session.user_id` missing), redirect to `/login`.

No other new routes. (Expense create/edit/delete stay as the Step 7–9 placeholders.)

## Database changes
No schema changes. The `expenses` table from Step 1 already provides every column
needed (`user_id`, `amount`, `category`, `date`, `description`, `created_at`).
Verified against `database/db.py`.

Three read-only DB helpers must be added to `database/db.py` (all parameterised, all
closing the connection in every path via the existing `try/finally` pattern):

- `get_expenses(user_id, limit=None)` — returns a list of the user's expense rows
  ordered by `date DESC, id DESC` (newest first). When `limit` is provided, return at
  most that many rows (used for the "recent transactions" preview on the profile);
  when `None`, return the full history. Use a parameterised `LIMIT` — never string
  formatting.
- `get_category_breakdown(user_id)` — returns rows of
  `category, SUM(amount) AS total, COUNT(*) AS count` for the user, grouped by
  `category` and ordered by `total DESC`. Only categories that have expenses appear.
- `get_summary(user_id)` — returns a single enriched summary row for the user with:
  - `count` — total number of expenses,
  - `total` — `COALESCE(SUM(amount), 0)`,
  - `month_total` — `COALESCE(SUM(amount), 0)` for the current calendar month, using
    `strftime('%Y-%m', date) = strftime('%Y-%m', 'now')`,
  - `average` — `COALESCE(AVG(amount), 0)`,
  - `top_category` — the category with the highest summed amount, or `NULL`/empty
    when the user has no expenses.

  The existing `get_expense_summary()` stays in place (unchanged) so nothing that
  currently calls it breaks; the `/profile` route switches to `get_summary()` for the
  richer figures.

## Templates
- **Create:** `templates/transactions.html`
  - Extends `base.html`; overrides `{% block title %}` (e.g. "Transactions — Spendly").
  - Lists every expense (date, category, description, amount), newest first.
  - Shows the category breakdown section (category, count, total) beside/above the list.
  - Renders an empty state ("No transactions yet") when the user has no expenses.
  - Formats money as `${{ "{:,.2f}".format(amount) }}` and reuses existing card/stat
    classes + CSS variables — no hardcoded colours.
- **Create:** `static/css/transactions.css`
  - Styling for the transaction list / breakdown, using only CSS variables defined in
    `static/css/style.css`. Linked via the `{% block head %}` of `transactions.html`
    (same pattern `profile.html` uses for `profile.css`).
- **Modify:** `templates/profile.html`
  - Add a "Recent transactions" section (the `limit`-ed list) and a "Spending by
    category" section (the breakdown), plus the enriched summary figures
    (this-month total, average, top category).
  - Include a link to `/transactions` ("View all"). Reuse existing profile/stat
    classes and CSS variables — introduce no hardcoded colours.
- **Modify:** `templates/base.html`
  - Add a session-aware "Transactions" nav link (visible only when
    `session.user_id` is set), pointing at `url_for('transactions')`. Keep all
    existing markup, classes, and the signed-out links unchanged.

## Files to change
- `app.py` — enrich the `/profile` route (fetch `get_summary`, `get_expenses(..., limit=5)`,
  `get_category_breakdown`) and add the new `GET /transactions` route (login-protected,
  fetching `get_expenses` + `get_category_breakdown`). Add imports for `get_expenses`,
  `get_category_breakdown`, and `get_summary` from `database.db`.
- `database/db.py` — add `get_expenses()`, `get_category_breakdown()`, and
  `get_summary()` helpers.
- `templates/base.html` — add the session-aware Transactions nav link.
- `templates/profile.html` — add recent-transactions, category-breakdown, and enriched
  summary sections plus the "View all" link.

## File to create
- `templates/transactions.html` — the full transaction history + breakdown page.
- `static/css/transactions.css` — styles for that page.

## New dependencies
No new dependencies. Uses Flask (`session`, `redirect`, `url_for`, `render_template`)
and `sqlite3`, all already available. Current-month filtering uses SQLite's built-in
`strftime` — no Python date libraries required in the query layer.

## Rules for implementation
- No SQLAlchemy or ORMs — use `sqlite3` via `get_db()` only.
- Parameterised queries only — never use string formatting / f-strings in SQL
  (including the `LIMIT` value and the month filter).
- Password hashed with werkzeug — this step never touches credentials; never expose,
  render, or log `password_hash`.
- Use CSS variables — never hardcode hex values; reuse existing tokens/classes from
  `static/css/style.css`.
- All templates extend `base.html`.
- Protect both data views: treat a missing `session.user_id` as "not logged in" and
  redirect to `/login` — never render another user's data. Every query is scoped by
  `user_id = ?`; a user must only ever see their own expenses.
- Read-only step: do not add, edit, or delete any expenses here; the create/edit/delete
  routes remain the Step 7–9 placeholders.
- Handle the empty case everywhere: zero expenses must show `0` / `$0.00` and an empty
  state, never `None` or a crash (use `COALESCE`).
- Format money and dates in the template/route for display only — do not change how
  values are stored (amount stays REAL, dates stay `YYYY-MM-DD`).
- Close the DB connection in every path (handled inside the helpers via `try/finally`).

## Definition of done
- [ ] Signed in as the seeded demo account (`demo@spendly.com` / `demo123`), `/profile`
      shows the enriched summary (count, total, this-month total, average, top category)
      matching the 8 seeded expenses.
- [ ] `/profile` shows a "Recent transactions" preview (at most 5, newest first) and a
      "Spending by category" breakdown, with a working "View all" link to `/transactions`.
- [ ] `/transactions` while signed in lists all of that user's expenses, newest first,
      with date, category, description, and amount, plus the category breakdown.
- [ ] The category breakdown totals sum to the same overall total shown in the summary.
- [ ] A user with no expenses sees `0` / `$0.00`, an empty state on `/transactions`, and
      no crash or `None` anywhere.
- [ ] Visiting `/transactions` (or `/profile`) while signed out redirects to `/login` —
      no expense data is shown to anonymous visitors.
- [ ] A signed-in user only ever sees their own expenses (queries scoped by `user_id`).
- [ ] The navbar shows a "Transactions" link only when signed in.
- [ ] Pages extend `base.html`, and no new markup/CSS introduces hardcoded hex values.
- [ ] All new SQL uses parameterised queries (including `LIMIT` and the month filter).
- [ ] App starts and serves `/profile` and `/transactions` without a 500 error.
