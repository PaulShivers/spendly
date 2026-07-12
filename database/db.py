import os
import sqlite3

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "expense_tracker.db")

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()


def create_user(name, email, password):
    conn = get_db()
    try:
        password_hash = generate_password_hash(password)
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def create_expense(user_id, amount, category, date, description=None):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_expense_by_id(expense_id, user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        ).fetchone()
    finally:
        conn.close()


def update_expense(expense_id, user_id, amount, category, date, description=None):
    conn = get_db()
    try:
        cursor = conn.execute(
            "UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? "
            "WHERE id = ? AND user_id = ?",
            (amount, category, date, description, expense_id, user_id),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def delete_expense_by_id(expense_id, user_id):
    conn = get_db()
    try:
        cursor = conn.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def get_expense_summary(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def get_expenses(user_id, limit=None, start_date=None, end_date=None):
    conn = get_db()
    try:
        query = "SELECT * FROM expenses WHERE user_id = ?"
        params = [user_id]
        if start_date is not None:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date is not None:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date DESC, id DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def get_summary(user_id, start_date=None, end_date=None):
    conn = get_db()
    try:
        date_clause = ""
        date_params = []
        if start_date is not None:
            date_clause += " AND date >= ?"
            date_params.append(start_date)
        if end_date is not None:
            date_clause += " AND date <= ?"
            date_params.append(end_date)

        row = conn.execute(
            "SELECT COUNT(*) AS count, "
            "COALESCE(SUM(amount), 0) AS total, "
            "COALESCE(SUM(CASE WHEN strftime('%Y-%m', date) = strftime('%Y-%m', 'now') "
            "THEN amount ELSE 0 END), 0) AS month_total, "
            "COALESCE(AVG(amount), 0) AS average "
            "FROM expenses WHERE user_id = ?" + date_clause,
            [user_id] + date_params,
        ).fetchone()

        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ?" + date_clause +
            " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            [user_id] + date_params,
        ).fetchone()

        return {
            "count": row["count"],
            "total": row["total"],
            "month_total": row["month_total"],
            "average": row["average"],
            "top_category": top["category"] if top is not None else None,
        }
    finally:
        conn.close()


def get_category_breakdown(user_id, start_date=None, end_date=None):
    conn = get_db()
    try:
        query = (
            "SELECT category, COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count "
            "FROM expenses WHERE user_id = ?"
        )
        params = [user_id]
        if start_date is not None:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date is not None:
            query += " AND date <= ?"
            params.append(end_date)
        query += " GROUP BY category ORDER BY total DESC"
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def seed_db():
    conn = get_db()
    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        conn.close()
        return

    password_hash = generate_password_hash("demo123")
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", password_hash),
    )
    user_id = cursor.lastrowid

    sample_expenses = [
        (user_id, 42.50, "Food", "2026-07-01", "Groceries"),
        (user_id, 15.00, "Transport", "2026-07-02", "Bus pass"),
        (user_id, 120.00, "Bills", "2026-07-03", "Electricity"),
        (user_id, 60.00, "Health", "2026-07-05", "Pharmacy"),
        (user_id, 25.00, "Entertainment", "2026-07-08", "Movie tickets"),
        (user_id, 80.00, "Shopping", "2026-07-10", "Clothes"),
        (user_id, 10.00, "Other", "2026-07-12", "Misc"),
        (user_id, 33.75, "Food", "2026-07-15", "Restaurant"),
    ]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        sample_expenses,
    )
    conn.commit()
    conn.close()
