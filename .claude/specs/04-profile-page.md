# Spec: Profile Page

## Overview
Give signed-in users a real profile page. Step 3 (Login and Logout) established a
Flask session and made the navbar session-aware — the "◈ {{ session.user_name }}"
link already points at `/profile` — but that route is still a placeholder returning
the string `"Profile page — coming in Step 4"`. This step replaces the placeholder
with a proper, login-protected page that shows the authenticated user's account
details (name, email, member-since date) alongside a small, read-only summary of
their spending so far (number of expenses and total amount). It is also where route
protection is introduced: `/profile` must redirect anonymous visitors to `/login`.
This sits at Step 4 of the roadmap, immediately after authentication and before the
expense-tracking features (add/edit/delete) that arrive in Steps 7–9, giving users a
home base once they can sign in.

## Depends on
- Step 1 — Database setup (`users` and `expenses` tables, `get_db()`, `init_db()`).
- Step 2 — Registration (`create_user()` — a way to have accounts to view).
- Step 3 — Login and Logout (the Flask session that identifies the current user via
  `session["user_id"]`; the session-aware navbar link to `/profile`).

## Routes
- `GET /profile` — render the current user's profile page; if there is no active
  session (`session.user_id` missing), redirect to `/login` — logged-in
  (replace the existing placeholder route that returns
  `"Profile page — coming in Step 4"`).

No other new routes.

## Database changes
No schema changes. The `users` table already provides `id`, `name`, `email`, and
`created_at`; the `expenses` table already provides `user_id` and `amount` for the
summary. Verified against `database/db.py`.

Two new read-only DB helpers must be added to `database/db.py`:
- `get_user_by_id(user_id)` — runs a parameterised `SELECT * FROM users WHERE id = ?`,
  returns the matching `sqlite3.Row` (`id`, `name`, `email`, `created_at`,
  `password_hash`) or `None` if no such user. Must close the connection in every path.
- `get_expense_summary(user_id)` — runs a parameterised aggregate
  `SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = ?`,
  returns the row (with `count` and `total`, `total` defaulting to `0` when the user
  has no expenses). Must close the connection in every path.

## Templates
- **Create:** `templates/profile.html`
  - Extends `base.html`; overrides `{% block title %}` (e.g. "Profile — Spendly").
  - Shows the user's `name`, `email`, and a formatted "Member since" value derived
    from `created_at`.
  - Shows a small summary section with the expense `count` and formatted `total`.
  - Reuses existing layout/card classes and CSS variables from `static/css/style.css`
    (e.g. the auth/card patterns) — introduce no hardcoded colours.
- **Modify:** none. `base.html` already links to `/profile` for signed-in users
  (Step 3) — leave it as-is.

## Files to change
- `app.py` — replace the `/profile` placeholder. On `GET`: if `session.get("user_id")`
  is falsy, `redirect(url_for("login"))`; otherwise fetch the user with
  `get_user_by_id(session["user_id"])` and the summary with
  `get_expense_summary(session["user_id"])`, then `render_template("profile.html", ...)`.
  Add imports for `get_user_by_id` and `get_expense_summary` from `database.db`.
- `database/db.py` — add the `get_user_by_id()` and `get_expense_summary()` helpers.

## File to create
- `templates/profile.html` — the profile page template.

## New dependencies
No new dependencies. Uses Flask (`session`, `redirect`, `url_for`, `render_template`)
and `sqlite3`, all already available.

## Rules for implementation
- No SQLAlchemy or ORMs — use `sqlite3` via `get_db()` only.
- Parameterised queries only — never use string formatting / f-strings in SQL.
- Password hashed with werkzeug — never expose, render, or log `password_hash`; the
  profile page must not display it.
- Use CSS variables — never hardcode hex values; reuse existing classes/tokens from
  `static/css/style.css`.
- All templates extend `base.html`.
- Protect the route: treat a missing `session.user_id` as "not logged in" and redirect
  to `/login` — do not render profile content for anonymous visitors.
- Defensive fetch: if `get_user_by_id` returns `None` (e.g. a stale session id),
  clear the session and redirect to `/login` rather than raising a 500.
- Close the DB connection in every path (handled inside the helpers).
- Format money and dates in the template/route for display only — do not change how
  values are stored.

## Definition of done
- [ ] Visiting `/profile` while signed in (seeded `demo@spendly.com` / `demo123`)
      shows that user's name, email, and a "Member since" date.
- [ ] The profile page shows an expense summary: a count and a total amount that match
      the seeded demo data (8 expenses).
- [ ] A user with no expenses sees a count of 0 and a total of 0 (no crash, no `None`).
- [ ] Visiting `/profile` while signed out redirects to `/login` (no profile content
      is shown).
- [ ] The rendered page never displays the `password_hash`.
- [ ] The navbar "{{ session.user_name }}" link reaches this page for signed-in users.
- [ ] The page extends `base.html` (shared navbar/footer present) and uses only
      existing CSS variables — no hardcoded hex values in any new markup/styles.
- [ ] All new SQL uses parameterised queries.
- [ ] App starts and serves `/profile` without a 500 error.
