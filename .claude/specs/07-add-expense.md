# Spec: Add Expense

## Overview
Give the signed-in user their first way to create data. Every feature so far (Steps 1–6)
reads and reports on expenses that only exist because `seed_db()` inserted them; there is
no in-app way to record a new one. This step turns the `GET /expenses/add` placeholder
into a real **add-expense** feature: a login-protected page with a form (amount, category,
date, optional description) that, on `POST`, validates the input, inserts one row into the
`expenses` table scoped to the current user via a new `create_expense` DB helper, and
redirects back to `/profile` with a confirmation flash. It is the first of the
add/edit/delete trio (Steps 7–9) and the foundation the next two steps build on, so it
comes right after the read-only reporting/filter work.

## Depends on
- Step 1 — Database setup (`expenses` table, `CATEGORIES`, `get_db()`, the
  parameterised-query + `try/finally` helper pattern).
- Step 3 — Login and Logout (`session["user_id"]` identifies the current user; the
  login-protect redirect pattern).
- Step 5 — Profile & reporting routes (the `/profile` route the form returns to; the
  reporting helpers that will immediately reflect the new row).

## Routes
- `GET /expenses/add` — **modify existing placeholder** — logged-in — render the
  add-expense form (`add_expense.html`) with the `CATEGORIES` list for the category select
  and today's date as the default. Redirect to `/login` if `session["user_id"]` is missing.
- `POST /expenses/add` — **new method on the same route** — logged-in — validate the
  submitted fields, and on success insert one expense for `session["user_id"]`, flash a
  confirmation, and `redirect` to `/profile`. On validation failure, re-render
  `add_expense.html` with a `flash` message and the user's submitted values preserved.
  Redirect to `/login` if signed out.

The route must declare `methods=["GET", "POST"]`. No other routes change; the Step 8/9
placeholders (`/expenses/<id>/edit`, `/expenses/<id>/delete`) are untouched.

## Database changes
No schema changes — the `expenses` table already has every column needed
(`user_id`, `amount`, `category`, `date`, `description`, plus the auto `id`/`created_at`).
Verified against `database/db.py`.

Add one new helper to `database/db.py`, following the existing pattern exactly (opens its
own `get_db()` connection, parameterised `INSERT`, `commit()`, returns `lastrowid`, closes
in a `try/finally`):

```
def create_expense(user_id, amount, category, date, description=None):
    ...
    "INSERT INTO expenses (user_id, amount, category, date, description) "
    "VALUES (?, ?, ?, ?, ?)"
```

`description` is optional and stored as `NULL` when blank. `created_at` uses its column
default. No other helper changes.

## Templates
- **Create:** `templates/add_expense.html` — extends `base.html`. A form
  `<form method="POST" action="{{ url_for('add_expense') }}">` with:
  - **Amount** — `<input type="number" name="amount" step="0.01" min="0.01" required>`.
  - **Category** — `<select name="category" required>` populated by looping the
    `categories` list passed from the route (never inline the category strings).
  - **Date** — `<input type="date" name="date" required>` defaulting to today.
  - **Description** — optional `<input type="text" name="description">` (or textarea).
  - A submit button reusing the existing button class (e.g. `.btn-submit` / `.btn-primary`
    as used elsewhere) and a cancel link back to `/profile`.
  - Re-populate all fields from a `form` context dict so a validation bounce keeps the
    user's input. Validation feedback shows through the existing `base.html` flash block.
- **Modify:** the profile and/or transactions templates only if needed to surface an
  "Add expense" entry point — a link/button to `{{ url_for('add_expense') }}`. Prefer
  linking an existing call-to-action; keep it minimal and use existing classes.

## Files to change
- `app.py` — replace the `add_expense` placeholder with a `GET`/`POST` handler
  (login-protect, parse + validate form, call `create_expense`, flash + redirect to
  `/profile` on success, re-render with flash on failure). Import `create_expense` and the
  `CATEGORIES` list.
- `database/db.py` — add the `create_expense` helper.
- `templates/base.html` **or** an existing authed template — add the "Add expense" link
  (only the minimal entry-point change described above).

## File to create
- `templates/add_expense.html` — the add-expense form page.
- `static/css/add-expense.css` — **only if** the form needs styling beyond the existing
  form/auth classes already in `style.css`; if the existing `.form-group` / `.form-input`
  classes suffice, reuse them and create no new CSS file. Linked via the template's
  `{% block head %}` if created.

## New dependencies
No new dependencies. Uses the standard-library `datetime`/`date` (already imported in
`app.py`) for the default/validation of the date, `sqlite3` via `get_db()` for the insert,
and Flask's `request.form`, `flash`, `redirect`, `url_for` (already imported).

## Rules for implementation
- No SQLAlchemy or ORMs — `sqlite3` via `get_db()` only.
- Parameterised queries only — the `INSERT` values are bound parameters, never
  string-formatted / f-strings.
- Every write is scoped to the current user — insert with `user_id = session["user_id"]`;
  never trust a user_id from the form.
- Passwords hashed with werkzeug — untouched here; never expose/log `password_hash`.
- Use CSS variables — never hardcode hex; reuse tokens/classes from `style.css`.
- All templates extend `base.html`; `add_expense.html` does so.
- Login-protect the route — a missing `session["user_id"]` redirects to `/login` before
  any query runs, on both `GET` and `POST`.
- Display-only formatting — `amount` is stored as REAL, `date` stays `YYYY-MM-DD`; do not
  reformat stored values.
- Validate server-side (never rely on HTML5 attributes alone):
  - `amount` — required, parses to a `float` greater than `0`; reject empty/non-numeric/
    ≤ 0 with a flash.
  - `category` — required and must be a member of `CATEGORIES` (reject anything else).
  - `date` — required and a valid `YYYY-MM-DD` string (reuse the existing `_valid_date`
    helper in `app.py`).
  - `description` — optional; strip whitespace and store `None`/`NULL` when blank.
  - On any failure, re-render the form with a flash and the submitted values preserved —
    no partial/invalid row is ever inserted.

## Definition of done
- [ ] Signed in as the demo account (`demo@spendly.com` / `demo123`), visiting
      `/expenses/add` shows a form with Amount, Category (the seven fixed categories),
      Date (defaulting to today), and an optional Description.
- [ ] Submitting valid values inserts exactly one row into `expenses` for the current user
      and redirects to `/profile` with a confirmation flash.
- [ ] The new expense immediately appears in the profile's recent list / totals and in
      `/transactions`, and the category breakdown updates accordingly.
- [ ] The inserted row has the correct `user_id`, `amount` (REAL), `category`, `date`
      (`YYYY-MM-DD`), and `description` (`NULL` when left blank).
- [ ] Invalid submissions — missing amount, amount ≤ 0 or non-numeric, a category not in
      `CATEGORIES`, or a missing/malformed date — do **not** insert a row; the form
      re-renders with a flash message and keeps the user's entered values.
- [ ] Visiting or posting to `/expenses/add` while signed out redirects to `/login`; a
      user can only ever create expenses under their own `user_id`.
- [ ] The `INSERT` is parameterised; `create_expense` follows the `get_db()` +
      `try/finally` pattern and returns the new row id.
- [ ] No hardcoded hex values in any new markup/CSS; `add_expense.html` extends
      `base.html`.
- [ ] The app starts and serves `/expenses/add` (GET and POST) without a 500.
