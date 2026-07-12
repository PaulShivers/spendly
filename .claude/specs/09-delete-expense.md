# Spec: Delete Expense

## Overview
This is the final piece of the add/edit/delete trio (Steps 7–9): it lets a signed-in user
permanently remove one of their own expenses. Steps 7 and 8 gave users a way to create and
correct expenses; deletion completes basic CRUD so a user can clear out a mistaken or
obsolete row entirely rather than only editing it. This step turns the
`/expenses/<int:id>/delete` placeholder into a real, login-protected action that — as a
**POST** (never a destructive GET) — removes exactly one expense scoped to its owner via a
new `delete_expense_by_id` DB helper, then redirects back to `/transactions` with a
confirmation flash. Deletion is triggered by a small inline form/button on each transactions
row (beside the existing Edit link), guarded by a JS confirmation to prevent accidental
clicks. After this step the roadmap's CRUD feature set is complete.

## Depends on
- Step 1 — Database setup (`expenses` table, `get_db()`, the parameterised-query +
  `try/finally` helper pattern).
- Step 3 — Login and Logout (`session["user_id"]` identifies the current user; the
  login-protect redirect pattern).
- Step 5 — Profile & reporting routes (the `/transactions` view the delete control lives on
  and returns to; the reporting helpers that immediately reflect the removed row).
- Step 8 — Edit Expense (the `get_expense_by_id` ownership helper this step reuses, and the
  `.txn-edit` per-row control the delete button sits next to).

## Routes
- `POST /expenses/<int:id>/delete` — **modify existing placeholder** — logged-in —
  re-verify the expense belongs to `session["user_id"]`; if it exists, delete that single
  row, flash a confirmation, and `redirect` to `/transactions`. If it does not exist or
  belongs to another user, flash a not-found message and `redirect` to `/transactions`
  (never delete another user's row, never 500). Redirect to `/login` if
  `session["user_id"]` is missing.

**Method change:** the current placeholder is a `GET`. Deletion is state-changing and must
not be reachable by a plain navigation/prefetch, so this route becomes **POST-only**
(`methods=["POST"]`). A stray `GET` to the URL therefore returns Flask's default 405 and
never deletes anything. No other routes change.

## Database changes
No schema changes — deleting only removes a row from the existing `expenses` table.
Verified against `database/db.py` (columns `id`, `user_id`, `amount`, `category`, `date`,
`description`, `created_at`; `get_expense_by_id` and `update_expense` already exist).

Add one new helper to `database/db.py`, following the existing pattern exactly (opens its
own `get_db()` connection, runs a **parameterised** query, closes in a `try/finally`):

```
def delete_expense_by_id(expense_id, user_id):
    ...
    "DELETE FROM expenses WHERE id = ? AND user_id = ?"
    # commit(); return cursor.rowcount (0 = not found / not owned, 1 = deleted)
```

The helper is named `delete_expense_by_id` (not `delete_expense`) to avoid colliding with
the existing `delete_expense` Flask view function when imported into `app.py`; it pairs
naturally with the existing `get_expense_by_id`. It is scoped by `AND user_id = ?` so a user
can never delete another user's expense even if the ownership pre-check were bypassed.

## Templates
- **Create:** none. Deletion has no page of its own — it is a POST action, not a form page.
- **Modify:** `templates/transactions.html` — add a delete control to each expense row
  (`<li class="txn-row">`), directly after the existing `.txn-edit` link:
  ```
  <form class="txn-delete-form" method="POST"
        action="{{ url_for('delete_expense', id=expense['id']) }}">
      <button type="submit" class="txn-delete">Delete</button>
  </form>
  ```
  The button is a real POST submit (works without JavaScript); the JS confirmation is
  progressive enhancement layered on top (see below). Use existing classes/tokens only.

## Files to change
- `app.py` — replace the `delete_expense` placeholder (currently `GET`, returns a string)
  with a `POST`-only handler: login-protect; load the owned expense with the existing
  `get_expense_by_id` (flash "Expense not found." + redirect to `/transactions` when
  `None`); otherwise call `delete_expense_by_id`, flash "Expense deleted.", and redirect to
  `/transactions`. Add `delete_expense_by_id` (and, if not already imported,
  `get_expense_by_id`) to the `database.db` import block. Update the route decorator to
  `@app.route("/expenses/<int:id>/delete", methods=["POST"])`.
- `database/db.py` — add the `delete_expense_by_id` helper.
- `templates/transactions.html` — add the per-row delete form/button described above.
- `static/css/transactions.css` — add a `.txn-delete` (and, if needed, `.txn-delete-form`)
  rule styled with the existing `var(--danger)` / `var(--danger-light)` tokens; no new hex.
- `static/js/main.js` — add an unobtrusive `submit` handler that calls
  `confirm("Delete this expense?")` on `.txn-delete-form` submissions and cancels the delete
  if the user dismisses the dialog. Keep it defensive (no error if the class is absent on a
  page).

## File to create
- No new template and no new CSS/JS file — reuse `transactions.css`, `main.js`, and the
  existing `--danger` tokens in `style.css`. (Create a file only if one genuinely does not
  already exist; both `main.js` and `transactions.css` already do.)

## New dependencies
No new dependencies. Uses `sqlite3` via `get_db()` for the delete and Flask's `flash`,
`redirect`, `url_for`, `session`, `request` (already imported in `app.py`).

## Rules for implementation
- No SQLAlchemy or ORMs — `sqlite3` via `get_db()` only.
- Parameterised queries only — the `DELETE` binds `id` and `user_id` as parameters, never
  string-formatted / f-strings.
- Every delete is scoped to the current user — the helper includes `AND user_id = ?`; never
  trust a `user_id` from the form and never delete by `id` alone. A user must never delete
  another user's expense.
- Passwords hashed with werkzeug — untouched here; never expose/log `password_hash`.
- Use CSS variables — never hardcode hex; style the delete control with the existing
  `var(--danger)` / `var(--danger-light)` tokens (and other existing tokens as needed).
- All templates extend `base.html` — `transactions.html` already does; no new template.
- Login-protect the route — a missing `session["user_id"]` redirects to `/login` before any
  query runs.
- Destructive action is POST-only — no deletion via `GET`; the delete control is a `POST`
  form, not a link. The JS `confirm()` is an enhancement, never the only safeguard.
- Non-existent or non-owned `id` — resolve safely (flash + redirect to `/transactions`),
  never a 500 and never another user's data removed.
- Confirmation flash on success uses Flask `flash`, shown through the existing `base.html`
  flash block; do not reformat stored values (this step displays nothing new).

## Definition of done
- [ ] Signed in as the demo account (`demo@spendly.com` / `demo123`), each expense row in
      `/transactions` shows a "Delete" control (a POST form/button) beside the Edit link.
- [ ] Submitting the delete form for one of your own expenses removes exactly that one row
      and redirects to `/transactions` with a "Expense deleted." flash; the row disappears
      from the transactions list and the totals / category breakdown update accordingly.
- [ ] Only the targeted row is deleted — the user's other expenses (and other users'
      expenses) are untouched; the total expense count drops by exactly one.
- [ ] Attempting to delete an `id` that does not exist or belongs to another user does not
      remove any row — it flashes a not-found message and redirects to `/transactions`
      (no 500, no other user's data affected).
- [ ] A plain `GET` to `/expenses/<id>/delete` does not delete anything (route is POST-only;
      returns 405).
- [ ] Posting to `/expenses/<id>/delete` while signed out redirects to `/login` and deletes
      nothing.
- [ ] The JS confirmation dialog appears on delete; dismissing it cancels the request and
      leaves the row in place, while confirming completes the deletion.
- [ ] The `DELETE` is parameterised and scoped by `user_id`; `delete_expense_by_id` follows
      the `get_db()` + `try/finally` pattern and returns the affected row count.
- [ ] No hardcoded hex values in the new markup/CSS (delete control uses `var(--danger)` /
      `var(--danger-light)`); `transactions.html` still extends `base.html`.
- [ ] The app starts and serves `POST /expenses/<id>/delete` without a 500.
