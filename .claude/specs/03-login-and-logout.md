# Spec: Login and Logout

## Overview
Give registered users a working session. Step 2 (Registration) lets people create
an account, but the `/login` route only renders a form and `/logout` is a
placeholder — there is no way to actually sign in or out. This step wires up
authentication: `POST /login` looks up the user by email, verifies the submitted
password against the stored werkzeug hash, and — on success — establishes a Flask
session; `/logout` clears that session. The navigation bar becomes session-aware so
signed-in users see a "Sign out" link instead of "Sign in / Get started". Sessions
are the foundation every authenticated feature (profile, expense tracking) is built
on, so this sits at Step 3, immediately after Registration.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`).
- Step 2 — Registration (`create_user()` and a way to create accounts to sign in with).

## Routes
- `GET /login` — render the sign-in form — public (already exists, keep as-is).
- `POST /login` — validate credentials, set the session, redirect to `/` (the main
  page) on success — public (new handling; extend the existing route to accept POST).
- `GET /logout` — clear the session and redirect to `/login` — logged-in
  (replace the existing placeholder that returns `"Logout — coming in Step 3"`).

No other new routes.

## Database changes
No schema changes. The `users` table from Step 1 already has `email` (UNIQUE) and
`password_hash`, which is everything login needs. Verified against `database/db.py`.

A new read-only DB helper must be added to `database/db.py`:
- `get_user_by_email(email)` — runs a parameterised `SELECT` against `users` for the
  given email, returns the matching `sqlite3.Row` (including `id`, `name`,
  `password_hash`) or `None` if no user exists. Must close the connection in every path.

## Templates
- Create: none.
- **Modify**: `templates/base.html`
  - Make the `.nav-links` block session-aware using the `session` object (available
    in Jinja by default):
    - When `session.user_id` is set: show a link to `/logout` ("Sign out"), and
      optionally a greeting / link to `/profile`.
    - Otherwise: keep the existing "Sign in" and "Get started" links unchanged.
  - Keep all existing markup, classes, and visual design.
- **Modify (only if needed)**: `templates/login.html`
  - The form already `POST`s to `/login` with `name="email"` and `name="password"`
    and already renders an `{{ error }}` block — no change is expected. Leave the
    existing visual design intact.

## Files to change
- `app.py` — extend the `/login` route to accept `["GET", "POST"]`; on POST look up
  the user via `get_user_by_email`, verify with `check_password_hash`, set
  `session["user_id"]` (and `session["user_name"]`) on success and redirect to
  `/` (the main page), or re-render `login.html` with an `error` on failure. Replace the
  `/logout` placeholder with `session.clear()` + redirect to `/login`. Add imports:
  `session` from `flask`, `check_password_hash` from `werkzeug.security`, and
  `get_user_by_email` from `database.db`.
- `database/db.py` — add the `get_user_by_email()` helper.
- `templates/base.html` — session-aware navigation links.

## File to create
- None.

## New dependencies
No new dependencies. Flask sessions are built in (`flask.session`, backed by the
existing `app.secret_key`) and `werkzeug.security.check_password_hash` is already
available.

## Rules for implementation
- No SQLAlchemy or ORMs — use `sqlite3` via `get_db()` only.
- Parameterised queries only — never use string formatting / f-strings in SQL.
- Password hashed with werkzeug — verify with `check_password_hash`; never compare
  plaintext and never store or log the raw password.
- Use CSS variables — never hardcode hex values (reuse existing nav classes; no new
  colours expected).
- All templates extend `base.html`.
- Normalise the submitted email the same way registration does: `strip()` and
  lowercase before lookup, so sign-in matches the stored value.
- Use a single generic error message ("Invalid email or password") for both an
  unknown email and a wrong password — do not reveal which was wrong.
- Store only the user id (and name) in the session — never the password or hash.
- `/logout` must clear the session and must not error if no one is logged in.
- Close the DB connection in every path.
- Do not add `@login_required` protection to `/profile` or expense routes here —
  route protection arrives with the Profile step; this step only establishes the
  session.

## Definition of done
- [ ] Visiting `/login` shows the sign-in form (GET still works).
- [ ] Signing in with the seeded demo account (`demo@spendly.com` / `demo123`) or a
      newly registered account succeeds and redirects to `/` (the main page).
- [ ] After a successful login the navbar shows a "Sign out" link (session-aware nav).
- [ ] Submitting a wrong password re-renders `login.html` with a visible
      "Invalid email or password" error and does **not** create a session.
- [ ] Submitting an email that is not registered shows the same generic error.
- [ ] Visiting `/logout` clears the session, redirects to `/login`, and the navbar
      reverts to "Sign in / Get started".
- [ ] Visiting `/logout` while not logged in does not raise a 500.
- [ ] The session cookie stores only the user id/name — never the password or hash.
- [ ] All SQL in the new code uses parameterised queries.
