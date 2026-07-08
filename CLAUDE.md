# Spendly — Project Guide

Spendly is a personal expense tracker built as a step-by-step teaching project.
Each feature is planned as a spec in `.claude/specs/`, implemented on a
`feature/<slug>` branch, and merged via PR. This file is the source of truth for the
roadmap, conventions, and schema — read it before planning or implementing anything.

## Stack

- **Backend:** Flask 3.1 (`app.py`) — plain functions + `render_template`, no blueprints.
- **Database:** SQLite via the `sqlite3` standard library only. **No ORM (no SQLAlchemy).**
  All DB access goes through helpers in `database/db.py`.
- **Auth:** `werkzeug.security` password hashing + Flask server-side sessions
  (`app.secret_key` from the `SECRET_KEY` env var, dev fallback in `app.py`).
- **Frontend:** Jinja2 templates in `templates/` (all extend `base.html`) + vanilla
  CSS in `static/css/` and JS in `static/js/`.
- **Tests:** `pytest` / `pytest-flask` (installed; suite not yet written).
- **Run:** `python app.py` → http://127.0.0.1:5001 (debug on). `init_db()` + `seed_db()`
  run on startup.

## Database

Single file `expense_tracker.db` in the project root (created on first run). The path
is derived in `database/db.py` — do not hardcode it elsewhere.

### `users`
| Column | Type | Constraints |
| --- | --- | --- |
| id | INTEGER | PK, autoincrement |
| name | TEXT | NOT NULL |
| email | TEXT | UNIQUE, NOT NULL (stored lowercased) |
| password_hash | TEXT | NOT NULL (werkzeug hash) |
| created_at | TEXT | DEFAULT `datetime('now')` |

### `expenses`
| Column | Type | Constraints |
| --- | --- | --- |
| id | INTEGER | PK, autoincrement |
| user_id | INTEGER | FK → `users.id`, NOT NULL |
| amount | REAL | NOT NULL |
| category | TEXT | NOT NULL (one of the fixed categories below) |
| date | TEXT | NOT NULL, `YYYY-MM-DD` |
| description | TEXT | Nullable |
| created_at | TEXT | DEFAULT `datetime('now')` |

### Fixed categories
`Food`, `Transport`, `Bills`, `Health`, `Entertainment`, `Shopping`, `Other`
(defined as `CATEGORIES` in `database/db.py` — use that list, never inline strings).

### DB helper pattern
Every helper opens its own connection with `get_db()` (which sets
`row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`), runs a **parameterised**
query, and closes the connection in every path via `try/finally`. Follow the existing
helpers exactly. Current helpers: `create_user`, `get_user_by_email`, `get_user_by_id`,
`get_expense_summary`, `get_expenses`, `get_summary`, `get_category_breakdown`,
`init_db`, `seed_db`.

## Conventions (non-negotiable)

- **No ORM** — `sqlite3` via `get_db()` only.
- **Parameterised queries only** — never use string formatting / f-strings in SQL
  (including `LIMIT` values and date filters).
- **Passwords** — hash with `werkzeug.security.generate_password_hash`; verify with
  `check_password_hash`. Never store, log, or render plaintext or the hash.
- **Scope every expense query by `user_id = ?`** — a user must only ever see their own data.
- **CSS variables only** — never hardcode hex values; reuse the tokens/classes defined
  in `static/css/style.css` (and page CSS like `profile.css`). Per-page CSS is linked
  through the template's `{% block head %}`.
- **All templates extend `base.html`.**
- **Login-protect authed routes** — `if not session.get("user_id"): return redirect(url_for("login"))`.
  Store only `user_id` (and `user_name`) in the session.
- **Money/date formatting is display-only** — format in the template
  (`${{ "{:,.2f}".format(x) }}`); don't change how values are stored (amount stays REAL,
  dates stay `YYYY-MM-DD`).
- **Empty/defensive cases** — use `COALESCE` so a user with no expenses sees `0` / `$0.00`,
  never `None`.

## Routes (current)

Public: `GET /` (landing), `GET|POST /register`, `GET|POST /login`, `GET /terms`,
`GET /privacy`.
Authed: `GET /logout`, `GET /profile`, `GET /transactions`, `GET /categories`.
Placeholders (return a string, implemented in later steps): `GET /expenses/add`,
`GET /expenses/<id>/edit`, `GET /expenses/<id>/delete`.

## Roadmap

| Step | Feature | Status |
| --- | --- | --- |
| 1 | Database setup (schema, `get_db`, `init_db`, `seed_db`) | ✅ Done |
| 2 | Registration | ✅ Done |
| 3 | Login & Logout (sessions, session-aware navbar) | ✅ Done |
| 4 | Profile page (login-protected, read-only summary) | ✅ Done |
| 5 | Profile & reporting routes (transactions, enriched summary, category breakdown) | ✅ Done |
| 6 | _Unassigned_ | ⏳ Not planned |
| 7 | Add expense (`/expenses/add`) | ⏳ Placeholder |
| 8 | Edit expense (`/expenses/<id>/edit`) | ⏳ Placeholder |
| 9 | Delete expense (`/expenses/<id>/delete`) | ⏳ Placeholder |

Specs for completed steps live in `.claude/specs/`. Use the `/create-spec` command to
plan the next step (it branches from `master` and writes a new spec). Mark a step done
here once its PR merges.

## Demo data

`seed_db()` inserts a demo account only when the `users` table is empty:
`demo@spendly.com` / `demo123`, plus sample expenses across categories. The
`/seed-user` and `/seed-expense` commands can add more dummy data.
