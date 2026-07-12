import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    CATEGORIES,
    create_expense,
    create_user,
    get_category_breakdown,
    get_expense_by_id,
    get_expenses,
    get_summary,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
    update_expense,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _format_day(value):
    """Display a YYYY-MM-DD string as e.g. 'Jul 1, 2026'."""
    dt = datetime.strptime(value, "%Y-%m-%d")
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}"


def _valid_date(value):
    """Return a canonical YYYY-MM-DD string if value is a valid date, else None."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except (ValueError, TypeError):
        return None


def resolve_date_range(preset, start, end):
    """Resolve profile filter params to (start_date, end_date, active_preset, label).

    A valid preset wins; otherwise a custom start/end range is used (malformed
    bounds are ignored); otherwise the default is all time.
    """
    today = date.today()
    presets = {
        "month": (today.replace(day=1).isoformat(), today.isoformat(), "This month"),
        "30d": ((today - timedelta(days=29)).isoformat(), today.isoformat(), "Last 30 days"),
        "year": (today.replace(month=1, day=1).isoformat(), today.isoformat(), "This year"),
        "all": (None, None, "All time"),
    }
    if preset in presets:
        start_date, end_date, label = presets[preset]
        return start_date, end_date, preset, label

    start_date = _valid_date(start)
    end_date = _valid_date(end)
    if start_date or end_date:
        if start_date and end_date:
            label = f"{_format_day(start_date)} – {_format_day(end_date)}"
        elif start_date:
            label = f"From {_format_day(start_date)}"
        else:
            label = f"Up to {_format_day(end_date)}"
        return start_date, end_date, None, label

    return None, None, "all", "All time"


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password or not confirm_password:
            flash("All fields are required.")
            return render_template("register.html")
        if "@" not in email:
            flash("Please enter a valid email address.")
            return render_template("register.html")
        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return render_template("register.html")
        if password != confirm_password:
            flash("Passwords do not match.")
            return render_template("register.html")

        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            flash("Email already registered.")
            return render_template("register.html")

        flash("Account created — please sign in.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Invalid email or password")

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("profile"))

    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = get_user_by_id(session["user_id"])
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    start_date, end_date, active_preset, period_label = resolve_date_range(
        request.args.get("preset"),
        request.args.get("start"),
        request.args.get("end"),
    )

    summary = get_summary(session["user_id"], start_date, end_date)
    recent = get_expenses(
        session["user_id"], limit=5, start_date=start_date, end_date=end_date
    )
    breakdown = get_category_breakdown(session["user_id"], start_date, end_date)
    overall_total = sum(row["total"] for row in breakdown)

    dt = datetime.strptime(user["created_at"], "%Y-%m-%d %H:%M:%S")
    member_since = f"{dt.strftime('%B')} {dt.day}, {dt.year}"

    return render_template(
        "profile.html",
        user=user,
        summary=summary,
        recent=recent,
        breakdown=breakdown,
        overall_total=overall_total,
        member_since=member_since,
        active_preset=active_preset,
        period_label=period_label,
        start_date=start_date,
        end_date=end_date,
    )


@app.route("/transactions")
def transactions():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    expenses = get_expenses(session["user_id"])
    breakdown = get_category_breakdown(session["user_id"])
    overall_total = sum(row["total"] for row in breakdown)

    return render_template(
        "transactions.html",
        expenses=expenses,
        breakdown=breakdown,
        overall_total=overall_total,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "POST":
        raw_amount = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date_value = _valid_date(request.form.get("date", "").strip())
        description = request.form.get("description", "").strip() or None

        try:
            amount = float(raw_amount)
        except ValueError:
            amount = None

        form = {
            "amount": raw_amount,
            "category": category,
            "date": request.form.get("date", "").strip(),
            "description": request.form.get("description", "").strip(),
        }

        if amount is None or amount <= 0:
            flash("Enter an amount greater than 0.")
            return render_template("add_expense.html", categories=CATEGORIES, form=form,
                                   today=date.today().isoformat())
        if category not in CATEGORIES:
            flash("Choose a valid category.")
            return render_template("add_expense.html", categories=CATEGORIES, form=form,
                                   today=date.today().isoformat())
        if date_value is None:
            flash("Enter a valid date.")
            return render_template("add_expense.html", categories=CATEGORIES, form=form,
                                   today=date.today().isoformat())

        create_expense(session["user_id"], amount, category, date_value, description)
        flash("Expense added.")
        return redirect(url_for("profile"))

    return render_template("add_expense.html", categories=CATEGORIES, form={},
                           today=date.today().isoformat())


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    expense = get_expense_by_id(id, session["user_id"])
    if expense is None:
        flash("Expense not found.")
        return redirect(url_for("transactions"))

    if request.method == "POST":
        raw_amount = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date_value = _valid_date(request.form.get("date", "").strip())
        description = request.form.get("description", "").strip() or None

        try:
            amount = float(raw_amount)
        except ValueError:
            amount = None

        form = {
            "amount": raw_amount,
            "category": category,
            "date": request.form.get("date", "").strip(),
            "description": request.form.get("description", "").strip(),
        }

        if amount is None or amount <= 0:
            flash("Enter an amount greater than 0.")
            return render_template("edit_expense.html", categories=CATEGORIES,
                                   form=form, expense=expense)
        if category not in CATEGORIES:
            flash("Choose a valid category.")
            return render_template("edit_expense.html", categories=CATEGORIES,
                                   form=form, expense=expense)
        if date_value is None:
            flash("Enter a valid date.")
            return render_template("edit_expense.html", categories=CATEGORIES,
                                   form=form, expense=expense)

        update_expense(id, session["user_id"], amount, category, date_value, description)
        flash("Expense updated.")
        return redirect(url_for("transactions"))

    form = {
        "amount": expense["amount"],
        "category": expense["category"],
        "date": expense["date"],
        "description": expense["description"] or "",
    }
    return render_template("edit_expense.html", categories=CATEGORIES,
                           form=form, expense=expense)


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
