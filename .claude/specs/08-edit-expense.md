# Spec: Edit Expense

## Overview
Now that a signed-in user can create expenses (Step 7), they need a way to fix mistakes —
a wrong amount, category, date, or description. This step turns the
`GET /expenses/<id>/edit` placeholder into a real **edit-expense** feature: a
login-protected page that loads one of the current user's existing expenses into a
pre-filled form, and on `POST` validates the input, updates that single row (scoped to the
owning user), and redirects back with a confirmation flash. It is the second of the
add/edit/delete trio (Steps 7–9) and reuses the exact validation, template, and DB
conventions established by Add Expense, so it slots in directly after Step 7.

## Depends on
- Step 1 — Database setup (`expenses` table, `CATEGORIES`, `get_db()`, the
  parameterised-query + `try/finally` helper pattern).
- Step 3 — Login and Logout (`session["user_id"]` identifies the current user; the
  login-protect redirect pattern).
- Step 5 — Profile & reporting routes (the `/profile` / `/transactions` views the edit
  link is surfaced from and returned to).
- Step 7 — Add Expense (the `add_expense.html` form, the `_valid_date` helper, and the
  server-side validation rules this step mirrors).

## Routes
- `GET /expenses/<int:id>/edit` — **modify existing placeholder** — logged-in — look up
  the expense by `id` **scoped to `session["user_id"]`**. If it does not exist or belongs
  to another user, flash a not-found message and `redirect` to `/transactions` (never
  render another user's data). Otherwise render `edit_expense.html` pre-filled with the
  expense's current values and the `CATEGORIES` list. Redirect to `/login` if
  `session["user_id"]` is missing.
- `POST /expenses/<int:id>/edit` — **new method on the same route** — logged-in —
  re-verify the expense belongs to the current user, validate the submitted fields, and on
  success update that one row, flash a confirmation, and `redirect` to `/transactions`. On
  validation failure, re-render `edit_expense.html` with a `flash` message and the user's
  submitted values preserved. Redirect to `/login` if signed out.

The route must declare `methods=["GET", "POST"]`. No other routes change; the Step 9
placeholder (`/expenses/<id>/delete`) is untouched.

## Database changes
No schema changes — editing only updates existing columns on the `expenses` table
(`amount`, `category`, `date`, `description`). Verified against `database/db.py`.

Add two new helpers to `database/db.py`, each following the existing pattern exactly (opens
its own `get_db()` connection, runs a **parameterised** query, closes in a `try/finally`):

```
def get_expense_by_id(expense_id, user_id):
    ...
    "SELECT * FROM expenses WHERE id = ? AND user_id = ?"
    # returns the sqlite3.Row or None (scoped so a user can't read another's expense)


def update_expense(expense_id, user_id, amount, category, date, description=None):
    ...
    "UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? "
    "WHERE id = ? AND user_id = ?"
    # commit(); return cursor.rowcount (0 = not found / not owned)
```

Both are scoped by `user_id = ?` so ownership is enforced in the query itself, not just in
Python. `description` is stored as `NULL` when blank. `created_at` is never modified.

## Templates
- **Create:** `templates/edit_expense.html` — extends `base.html`. Structurally a near-copy
  of `add_expense.html` (reusing `.auth-section` / `.auth-card` / `.form-group` /
  `.form-input` / `.btn-submit` classes), with these differences:
  - Heading/subtitle reflect editing (e.g. "Edit expense" / "Update this transaction").
  - `<form method="POST" action="{{ url_for('edit_expense', id=expense['id']) }}">`.
  - Every field pre-populated from the `form` context dict (which the route seeds from the
    existing expense on GET and from the submitted values on a validation bounce): amount
    `value`, the matching category `<option ... selected>`, date `value`, description
    `value`.
  - Submit button label "Save changes"; a Cancel link back to `{{ url_for('transactions') }}`.
- **Modify:** `templates/transactions.html` — add an "Edit" link per expense row pointing
  to `{{ url_for('edit_expense', id=expense['id']) }}`, using an existing/link button style
  (no new hex). Optionally surface the same link on the profile's recent list; keep it
  minimal.

## Files to change
- `app.py` — replace the `edit_expense` placeholder with a `GET`/`POST` handler
  (login-protect; load the owned expense or redirect; parse + validate the form reusing the
  same rules as `add_expense`; call `update_expense`; flash + redirect to `/transactions`
  on success; re-render with flash on failure). Import `get_expense_by_id` and
  `update_expense`.
- `database/db.py` — add the `get_expense_by_id` and `update_expense` helpers.
- `templates/transactions.html` — add the per-row "Edit" link (the minimal entry point).

## File to create
- `templates/edit_expense.html` — the pre-filled edit-expense form page.
- No new CSS file — reuse the existing form/auth classes in `style.css` (and
  `transactions.css` for the row link). Create a CSS file only if the edit link genuinely
  needs a style not already available; if so, link it via the template's `{% block head %}`.

## New dependencies
No new dependencies. Uses `sqlite3` via `get_db()` for the read/update, the standard-library
`datetime`/`date` (already imported in `app.py`), and Flask's `request.form`, `flash`,
`redirect`, `url_for` (already imported).

## Rules for implementation
- No SQLAlchemy or ORMs — `sqlite3` via `get_db()` only.
- Parameterised queries only — the `SELECT` and `UPDATE` values (including `id` and
  `user_id`) are bound parameters, never string-formatted / f-strings.
- Every read and write is scoped to the current user — both helpers include
  `AND user_id = ?`; never trust a `user_id` from the form and never look an expense up by
  `id` alone. A user must never view or edit another user's expense.
- Passwords hashed with werkzeug — untouched here; never expose/log `password_hash`.
- Use CSS variables — never hardcode hex; reuse tokens/classes from `style.css` /
  `transactions.css`.
- All templates extend `base.html`; `edit_expense.html` does so.
- Login-protect the route — a missing `session["user_id"]` redirects to `/login` before any
  query runs, on both `GET` and `POST`.
- Display-only formatting — `amount` stays REAL, `date` stays `YYYY-MM-DD`; do not reformat
  stored values when pre-filling or saving.
- Validate server-side (never rely on HTML5 attributes alone), identical to Add Expense:
  - `amount` — required, parses to a `float` greater than `0`; reject empty/non-numeric/≤ 0.
  - `category` — required and must be a member of `CATEGORIES`.
  - `date` — required and a valid `YYYY-MM-DD` string (reuse the existing `_valid_date`
    helper in `app.py`).
  - `description` — optional; strip whitespace and store `None`/`NULL` when blank.
  - On any failure, re-render the form with a flash and the submitted values preserved — the
    row is never partially updated.
- Non-existent or non-owned `id` — resolve safely (flash + redirect to `/transactions`),
  never a 500 and never another user's data.

## Definition of done
- [ ] Signed in as the demo account (`demo@spendly.com` / `demo123`), each expense row in
      `/transactions` shows an "Edit" link to `/expenses/<id>/edit`.
- [ ] Visiting `/expenses/<id>/edit` for one of your own expenses shows the form pre-filled
      with that expense's current amount, category (correct option selected), date, and
      description.
- [ ] Submitting valid changes updates exactly that one row (no new row is created) and
      redirects to `/transactions` with a confirmation flash; the change is immediately
      reflected in the transactions list, the profile totals, and the category breakdown.
- [ ] Clearing the description and saving stores `NULL` for that row.
- [ ] Invalid submissions — missing/≤ 0/non-numeric amount, a category not in `CATEGORIES`,
      or a missing/malformed date — do **not** modify the row; the form re-renders with a
      flash and keeps the user's entered values.
- [ ] Requesting `/expenses/<id>/edit` (GET or POST) for an `id` that does not exist or
      belongs to another user does not reveal or modify that expense — it flashes a
      not-found message and redirects to `/transactions` (no 500).
- [ ] Visiting or posting to `/expenses/<id>/edit` while signed out redirects to `/login`.
- [ ] The `SELECT` and `UPDATE` are parameterised and scoped by `user_id`;
      `get_expense_by_id` and `update_expense` follow the `get_db()` + `try/finally` pattern.
- [ ] No hardcoded hex values in any new markup/CSS; `edit_expense.html` extends
      `base.html`.
- [ ] The app starts and serves `/expenses/<id>/edit` (GET and POST) without a 500.
