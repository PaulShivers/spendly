# Spec: Registration

## Overview
Enable new users to create a Spendly account. The `/register` route and its
template already exist for display only — this step makes the form actually work:
accepting a POST submission, validating the input, hashing the password with
werkzeug, and inserting a new row into the `users` table. On success the user is 
shown with a success message and then redirected to the login page.  Registration is the
gateway to every authenticated feature (login, profile, expense tracking), so it
sits at Step 2 of the roadmap, immediately after the database foundation.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`) must be complete.

## Routes
- `GET /register` — render the registration form — public (already exists, keep as-is).
- `POST /register` — process the submitted form, create the user, redirect to
  `/login` on success — public (new handling; extend the existing route to accept POST).

No other new routes.

## Database changes
No database changes. The `users` table from Step 1 already has every required
column (`name`, `email`, `password_hash`, `created_at`) and the `UNIQUE` constraint
on `email`. Verified against `database/db.py`.

A new DB helper must be added to 'database/db.py':
- 'create_user(name, email, password)' - hashes the password with 'werkzeug', 
inserts a row into 'users', 
returns the new user's 'id'.  
Raises 'sqlite3.IntegrityError' if the email is already taken (UNIQUE constraint).

## Templates
- Create: none.
-	**Modify**: ‘templates/register.html’
-	Change the form ‘action’ to ‘url_for(‘register’)’ with ‘method=”post”’
-	Add ‘name’ attributes to all inputs: ‘name’, ‘email’, ‘password’, ‘confirm_password’
-	Add a block to display a flash error message (e.g. “Email already registered”, “Passwords do not match”)
-	Keep all existing visual design

## Files to change
- `app.py` — change the `/register` route to accept `["GET", "POST"]`, add
  validation + user-creation logic on POST, import `get_db` and the redirect/request
  helpers.
- 'database/db.py' - add 'create_user()' helper
- 'templates/register.html' - wire up form action/method and flash message display

## File to create
- None.

## New dependencies
No new dependencies. Uses Flask (`request`, `redirect`, `url_for`) and
`werkzeug.security.generate_password_hash`, both already available.

## Rules for implementation
- No SQLAlchemy or ORMs — use `sqlite3` via `get_db()` only.
- Parameterised queries only — never use string formatting / f-strings in SQL.
- Password hashed with werkzeug (`generate_password_hash`) — never store plaintext.
- Use CSS variables — never hardcode hex values (no template styling changes expected).
- All templates extend `base.html`.
- Trim/normalise inputs: strip whitespace on `name` and `email`; store email lowercased.
- Validate on the server: `name`, `email`, `password` all required; email must
  contain `@`; password minimum 8 characters.
- Reject duplicate emails gracefully — check first and/or catch the `UNIQUE`
  constraint error, then re-render `register.html` with a friendly `error` message
  (do not let a 500 leak).
- On success, redirect to `/login` (do not auto-login — sessions arrive in Step 3).
- Close the DB connection in every path.

## Definition of done
- [ ] Visiting `/register` shows the form (GET still works).
- [ ] Submitting valid details creates exactly one new row in `users` and redirects to `/login`.
- [ ] The stored `password_hash` is a werkzeug hash, not the plaintext password.
- [ ] Submitting an email that already exists re-renders the form with a visible error and creates no new row.
- [ ] Submitting with any field blank re-renders the form with a visible error and creates no new row.
- [ ] Submitting a password shorter than 8 characters is rejected with a visible error.
- [ ] App starts and handles submissions without a 500 error.
- [ ] All SQL in the new code uses parameterised queries.
