"""AI-Based Digital Banking Solutions - Flask application."""
import random
import secrets
from functools import wraps

from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import ai_engine
from database import get_db, init_db

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # replace with a fixed secret in production

init_db()


# ------------------------------------------------------------------ helpers
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def current_account(db):
    return db.execute("SELECT * FROM accounts WHERE user_id = ?", (session["user_id"],)).fetchone()


def user_transactions(db, account_id, limit=None):
    sql = "SELECT * FROM transactions WHERE account_id = ? ORDER BY id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return db.execute(sql, (account_id,)).fetchall()


def new_account_no(db):
    while True:
        no = "AIB" + "".join(random.choices("0123456789", k=9))
        if not db.execute("SELECT 1 FROM accounts WHERE account_no = ?", (no,)).fetchone():
            return no


def record(db, account_id, ttype, amount, description="", counterparty="",
           status="completed", score=0, reasons=""):
    db.execute(
        """INSERT INTO transactions
           (account_id, type, amount, description, category, counterparty, status, fraud_score, fraud_reasons)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (account_id, ttype, amount, description, ai_engine.categorize(description),
         counterparty, status, score, reasons))


def parse_amount(value):
    try:
        amount = round(float(value), 2)
    except (TypeError, ValueError):
        return None
    return amount if amount > 0 else None


# ------------------------------------------------------------------- auth
@app.route("/")
def index():
    return redirect(url_for("dashboard" if "user_id" in session else "login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 6:
            flash("Fill all fields; password must be at least 6 characters.", "error")
            return render_template("register.html")
        db = get_db()
        try:
            cur = db.execute("INSERT INTO users (name, email, password_hash) VALUES (?,?,?)",
                             (name, email, generate_password_hash(password)))
            db.execute("INSERT INTO accounts (user_id, account_no, balance) VALUES (?,?,?)",
                       (cur.lastrowid, new_account_no(db), 0))
            db.commit()
        except Exception:
            db.rollback()
            flash("That email is already registered.", "error")
            return render_template("register.html")
        finally:
            db.close()
        flash("Account created! Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        db.close()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"], session["name"] = user["id"], user["name"]
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -------------------------------------------------------------- dashboard
@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    acc = current_account(db)
    txns = user_transactions(db, acc["id"])
    insights = ai_engine.spending_insights(txns)
    db.close()
    return render_template("dashboard.html", acc=acc, txns=txns[:10], insights=insights)


@app.route("/money", methods=["POST"])
@login_required
def money():
    """Deposit or withdraw."""
    action = request.form.get("action")
    amount = parse_amount(request.form.get("amount"))
    description = request.form.get("description", "").strip()
    if action not in ("deposit", "withdraw") or amount is None:
        flash("Enter a valid amount.", "error")
        return redirect(url_for("dashboard"))
    db = get_db()
    acc = current_account(db)
    if action == "withdraw":
        if amount > acc["balance"]:
            flash("Insufficient balance.", "error")
            db.close()
            return redirect(url_for("dashboard"))
        db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, acc["id"]))
    else:
        db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, acc["id"]))
    record(db, acc["id"], action, amount, description)
    db.commit()
    db.close()
    flash(f"{action.title()} of Rs. {amount:,.2f} successful.", "success")
    return redirect(url_for("dashboard"))


# --------------------------------------------------------------- transfer
@app.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():
    result = None
    if request.method == "POST":
        to_no = request.form.get("to_account", "").strip().upper()
        amount = parse_amount(request.form.get("amount"))
        description = request.form.get("description", "").strip()
        db = get_db()
        acc = current_account(db)
        dest = db.execute("SELECT * FROM accounts WHERE account_no = ?", (to_no,)).fetchone()

        if amount is None:
            flash("Enter a valid amount.", "error")
        elif not dest:
            flash("Recipient account not found.", "error")
        elif dest["id"] == acc["id"]:
            flash("You cannot transfer to your own account.", "error")
        elif amount > acc["balance"]:
            flash("Insufficient balance.", "error")
        else:
            past = [r["amount"] for r in db.execute(
                "SELECT amount FROM transactions WHERE account_id=? AND type IN ('withdraw','transfer_out') AND status='completed'",
                (acc["id"],))]
            recent = db.execute(
                "SELECT COUNT(*) c FROM transactions WHERE account_id=? AND created_at >= datetime('now','-10 minutes')",
                (acc["id"],)).fetchone()["c"]
            score, reasons = ai_engine.fraud_check(amount, acc["balance"], past, recent)
            reason_text = "; ".join(reasons)

            if score >= 70:
                record(db, acc["id"], "transfer_out", amount, description, to_no,
                       status="blocked", score=score, reasons=reason_text)
                result = {"level": "blocked", "score": score, "reasons": reasons}
            else:
                db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, acc["id"]))
                db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, dest["id"]))
                record(db, acc["id"], "transfer_out", amount, description, to_no, score=score, reasons=reason_text)
                record(db, dest["id"], "transfer_in", amount, description, acc["account_no"])
                result = {"level": "flagged" if score >= 40 else "ok", "score": score, "reasons": reasons}
            db.commit()
        db.close()
    return render_template("transfer.html", result=result)


# ---------------------------------------------------------------- history
@app.route("/history")
@login_required
def history():
    db = get_db()
    acc = current_account(db)
    txns = user_transactions(db, acc["id"])
    db.close()
    return render_template("history.html", acc=acc, txns=txns)


# ---------------------------------------------------------------- chatbot
@app.route("/chatbot")
@login_required
def chatbot():
    return render_template("chatbot.html")


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    message = (request.get_json(silent=True) or {}).get("message", "")
    db = get_db()
    acc = current_account(db)
    txns = user_transactions(db, acc["id"])
    reply = ai_engine.chatbot_reply(message, acc["balance"], txns[:5], ai_engine.spending_insights(txns))
    db.close()
    return jsonify({"reply": reply})


# ------------------------------------------------------------------- loan
@app.route("/loan", methods=["GET", "POST"])
@login_required
def loan():
    result = None
    if request.method == "POST":
        try:
            income = float(request.form["income"])
            emi = float(request.form.get("existing_emi") or 0)
            amount = float(request.form["amount"])
            tenure = int(request.form["tenure"])
        except (KeyError, ValueError):
            flash("Please enter valid numbers.", "error")
            return render_template("loan.html", result=None)
        db = get_db()
        acc = current_account(db)
        count = db.execute("SELECT COUNT(*) c FROM transactions WHERE account_id=?", (acc["id"],)).fetchone()["c"]
        db.close()
        result = ai_engine.loan_assessment(income, emi, amount, tenure, acc["balance"], count)
    return render_template("loan.html", result=result)


if __name__ == "__main__":
    app.run(debug=True)
