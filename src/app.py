# src/app.py
from datetime import date, datetime, timedelta
import csv, io
import pymysql
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, Response
)

app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/static")
app.secret_key = "dev-change-this"

# ----- DB CONFIG (XAMPP MySQL on 3306) -----
CFG = {
    "host": "127.0.0.1",
    "port": 3306,                         # XAMPP default
    "user": "expense_user",
    "password": "StrongPassword123!",     # <-- put your real password
    "database": "expense_db",
    "cursorclass": pymysql.cursors.DictCursor,
    "charset": "utf8mb4",
    "autocommit": True,
}
def get_conn():
    return pymysql.connect(**CFG)

# ---------- Helpers ----------
def parse_ymd(s: str):
    """Parse 'YYYY-MM-DD' -> date or None"""
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None

def month_start_end(d: date):
    return d.replace(day=1), d

def default_range():
    """Current month: 1st .. today (inclusive)"""
    return month_start_end(date.today())

def get_categories():
    with get_conn().cursor() as cur:
        cur.execute("SELECT id, name FROM categories ORDER BY name;")
        return cur.fetchall()

def get_income_categories():
    with get_conn().cursor() as cur:
        cur.execute("SELECT id, name FROM income_categories ORDER BY name;")
        return cur.fetchall()

def ensure_income_category(label: str):
    """Create an income category if it does not exist (case-insensitive)."""
    with get_conn().cursor() as cur:
        cur.execute("SELECT id FROM income_categories WHERE LOWER(name)=LOWER(%s) LIMIT 1", (label,))
        if not cur.fetchone():
            cur.execute("INSERT INTO income_categories(name) VALUES (%s)", (label,))

# ---- Flask 3.x safe seeding (no before_first_request) ----
_SEEDED = False
def try_seed():
    global _SEEDED
    if _SEEDED:
        return
    try:
        ensure_income_category("Tuition fee")
        _SEEDED = True
    except Exception as e:
        print("Seed warning:", e)

def totals_between(d_from: date, d_to: date):
    """Inclusive range totals + label dict for UI."""
    if d_from is None or d_to is None or d_from > d_to:
        d_from, d_to = default_range()

    with get_conn().cursor() as cur:
        cur.execute("""
            SELECT COALESCE(SUM(amount),0) AS total_exp
            FROM expenses
            WHERE tx_date >= %s AND tx_date <= %s;
        """, (d_from, d_to))
        total_exp = float(cur.fetchone()["total_exp"] or 0)

        cur.execute("""
            SELECT COALESCE(SUM(amount),0) AS total_inc
            FROM incomes
            WHERE tx_date >= %s AND tx_date <= %s;
        """, (d_from, d_to))
        total_inc = float(cur.fetchone()["total_inc"] or 0)

    return {
        "range_from": d_from.isoformat(),
        "range_to": d_to.isoformat(),
        "range_label": f"{d_from.isoformat()} → {d_to.isoformat()}",
        "expense": total_exp,
        "income": total_inc,
        "net": total_inc - total_exp,
    }

# ---------- PAGES ----------
@app.route("/")
def dashboard():
    try_seed()
    d_from = parse_ymd(request.args.get("from", "")) or None
    d_to   = parse_ymd(request.args.get("to", "")) or None
    if not d_from or not d_to or d_from > d_to:
        d_from, d_to = default_range()

    with get_conn().cursor() as cur:
        cur.execute("""
            SELECT e.id, e.tx_date, c.name AS category, e.amount, e.payment_method, e.merchant, e.note
            FROM expenses e
            JOIN categories c ON c.id = e.category_id
            WHERE e.tx_date >= %s AND e.tx_date <= %s
            ORDER BY e.tx_date DESC, e.id DESC
            LIMIT 10;
        """, (d_from, d_to))
        recent_exp = cur.fetchall()

        cur.execute("""
            SELECT i.id, i.tx_date, ic.name AS category, i.amount, i.source, i.note
            FROM incomes i
            JOIN income_categories ic ON ic.id = i.category_id
            WHERE i.tx_date >= %s AND i.tx_date <= %s
            ORDER BY i.tx_date DESC, i.id DESC
            LIMIT 10;
        """, (d_from, d_to))
        recent_inc = cur.fetchall()

    return render_template("home.html",
                           summary=totals_between(d_from, d_to),
                           recent_expenses=recent_exp,
                           recent_incomes=recent_inc)

@app.route("/analytics")
def analytics():
    try_seed()
    return render_template("analytics.html",
                           default_month=date.today().strftime("%Y-%m"),
                           summary=totals_between(*default_range()))

# ---------- EXPENSES ----------
@app.route("/expenses")
def list_expenses():
    d_from = parse_ymd(request.args.get("from", "")) or None
    d_to   = parse_ymd(request.args.get("to", "")) or None
    cat_id = request.args.get("category_id")

    where, params = [], []
    if d_from: where.append("e.tx_date >= %s"); params.append(d_from)
    if d_to:   where.append("e.tx_date <= %s"); params.append(d_to)
    if cat_id and cat_id.isdigit():
        where.append("e.category_id = %s"); params.append(int(cat_id))

    sql = """
        SELECT e.id, e.tx_date, c.name AS category, e.amount, e.payment_method, e.merchant, e.note
        FROM expenses e
        JOIN categories c ON c.id = e.category_id
    """
    if where: sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY e.tx_date DESC, e.id DESC LIMIT 200;"

    with get_conn().cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return render_template("list_expenses.html",
                           expenses=rows,
                           categories=get_categories(),
                           selected_from=d_from.isoformat() if d_from else "",
                           selected_to=d_to.isoformat() if d_to else "",
                           selected_cat=int(cat_id) if cat_id and cat_id.isdigit() else None)

@app.route("/add", methods=["GET", "POST"])
def add_expense():
    if request.method == "GET":
        return render_template("add_expense.html",
                               categories=get_categories(),
                               default_date=date.today().isoformat(),
                               payment_methods=["Cash", "Card", "Bank", "Mobile", "Other"])

    tx_date = request.form.get("tx_date","").strip()
    category_id = request.form.get("category_id","").strip()
    amount = request.form.get("amount","").strip()
    payment_method = request.form.get("payment_method","").strip() or None
    merchant = request.form.get("merchant","").strip() or None
    note = request.form.get("note","").strip() or None

    errors = []
    if not tx_date: errors.append("Date is required.")
    if not category_id.isdigit(): errors.append("Category is required.")
    try:
        amount_val = float(amount)
        if amount_val <= 0: errors.append("Amount must be > 0.")
    except Exception:
        errors.append("Amount must be a number.")
    if errors:
        for e in errors: flash(e, "error")
        return redirect(url_for("add_expense"))

    with get_conn().cursor() as cur:
        cur.execute("""
            INSERT INTO expenses (tx_date, category_id, amount, payment_method, merchant, note)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (tx_date, int(category_id), amount_val, payment_method, merchant, note))
    flash("Expense saved.", "ok")
    return redirect(url_for("dashboard"))

@app.route("/expense/<int:id>/edit", methods=["GET","POST"])
def edit_expense(id):
    with get_conn().cursor() as cur:
        cur.execute("SELECT * FROM expenses WHERE id=%s", (id,))
        row = cur.fetchone()
    if not row:
        flash(f"Expense #{id} not found.", "error")
        return redirect(url_for("list_expenses"))

    if request.method == "GET":
        return render_template("edit_expense.html",
                               expense=row,
                               categories=get_categories(),
                               payment_methods=["Cash", "Card", "Bank", "Mobile", "Other"])

    tx_date = request.form.get("tx_date","").strip()
    category_id = request.form.get("category_id","").strip()
    amount = request.form.get("amount","").strip()
    payment_method = request.form.get("payment_method","").strip() or None
    merchant = request.form.get("merchant","").strip() or None
    note = request.form.get("note","").strip() or None

    errors = []
    if not tx_date: errors.append("Date is required.")
    if not category_id.isdigit(): errors.append("Category is required.")
    try:
        amount_val = float(amount)
        if amount_val <= 0: errors.append("Amount must be > 0.")
    except Exception:
        errors.append("Amount must be a number.")
    if errors:
        for e in errors: flash(e, "error")
        return redirect(url_for("edit_expense", id=id))

    with get_conn().cursor() as cur:
        cur.execute("""
            UPDATE expenses
               SET tx_date=%s, category_id=%s, amount=%s, payment_method=%s, merchant=%s, note=%s
             WHERE id=%s
        """, (tx_date, int(category_id), amount_val, payment_method, merchant, note, id))
    flash(f"Expense #{id} updated.", "ok")
    return redirect(url_for("list_expenses"))

@app.route("/delete/<int:id>", methods=["POST"])
def delete_expense(id):
    with get_conn().cursor() as cur:
        cur.execute("DELETE FROM expenses WHERE id=%s", (id,))
        affected = cur.rowcount
    flash(f"{'Deleted' if affected else 'Not found'} expense #{id}.", "ok" if affected else "error")
    return redirect(url_for("list_expenses"))

# ---------- INCOME ----------
@app.route("/income")
def list_income():
    d_from = parse_ymd(request.args.get("from", "")) or None
    d_to   = parse_ymd(request.args.get("to", "")) or None
    cat_id = request.args.get("category_id")

    where, params = [], []
    if d_from: where.append("i.tx_date >= %s"); params.append(d_from)
    if d_to:   where.append("i.tx_date <= %s"); params.append(d_to)
    if cat_id and cat_id.isdigit():
        where.append("i.category_id = %s"); params.append(int(cat_id))

    sql = """
        SELECT i.id, i.tx_date, ic.name AS category, i.amount, i.source, i.note
        FROM incomes i
        JOIN income_categories ic ON ic.id = i.category_id
    """
    if where: sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY i.tx_date DESC, i.id DESC LIMIT 200;"

    with get_conn().cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return render_template("list_income.html",
                           incomes=rows,
                           categories=get_income_categories(),
                           selected_from=d_from.isoformat() if d_from else "",
                           selected_to=d_to.isoformat() if d_to else "",
                           selected_cat=int(cat_id) if cat_id and cat_id.isdigit() else None)

@app.route("/income/add", methods=["GET", "POST"])
def add_income():
    try_seed()
    if request.method == "GET":
        return render_template("add_income.html",
                               categories=get_income_categories(),
                               default_date=date.today().isoformat())

    tx_date = request.form.get("tx_date","").strip()
    category_id = request.form.get("category_id","").strip()
    amount = request.form.get("amount","").strip()
    source = request.form.get("source","").strip() or None
    note = request.form.get("note","").strip() or None

    errors = []
    if not tx_date: errors.append("Date is required.")
    if not category_id.isdigit(): errors.append("Category is required.")
    try:
        amount_val = float(amount)
        if amount_val <= 0: errors.append("Amount must be > 0.")
    except Exception:
        errors.append("Amount must be a number.")
    if errors:
        for e in errors: flash(e, "error")
        return redirect(url_for("add_income"))

    with get_conn().cursor() as cur:
        cur.execute("""
            INSERT INTO incomes (tx_date, category_id, amount, source, note)
            VALUES (%s,%s,%s,%s,%s)
        """, (tx_date, int(category_id), amount_val, source, note))
    flash("Income saved.", "ok")
    return redirect(url_for("dashboard"))

@app.route("/income/<int:id>/edit", methods=["GET","POST"])
def edit_income(id):
    with get_conn().cursor() as cur:
        cur.execute("SELECT * FROM incomes WHERE id=%s", (id,))
        row = cur.fetchone()
    if not row:
        flash(f"Income #{id} not found.", "error")
        return redirect(url_for("list_income"))

    if request.method == "GET":
        return render_template("edit_income.html",
                               income=row,
                               categories=get_income_categories())

    tx_date = request.form.get("tx_date","").strip()
    category_id = request.form.get("category_id","").strip()
    amount = request.form.get("amount","").strip()
    source = request.form.get("source","").strip() or None
    note = request.form.get("note","").strip() or None

    errors = []
    if not tx_date: errors.append("Date is required.")
    if not category_id.isdigit(): errors.append("Category is required.")
    try:
        amount_val = float(amount)
        if amount_val <= 0: errors.append("Amount must be > 0.")
    except Exception:
        errors.append("Amount must be a number.")
    if errors:
        for e in errors: flash(e, "error")
        return redirect(url_for("edit_income", id=id))

    with get_conn().cursor() as cur:
        cur.execute("""
            UPDATE incomes
               SET tx_date=%s, category_id=%s, amount=%s, source=%s, note=%s
             WHERE id=%s
        """, (tx_date, int(category_id), amount_val, source, note, id))
    flash(f"Income #{id} updated.", "ok")
    return redirect(url_for("list_income"))

@app.route("/income/delete/<int:id>", methods=["POST"])
def delete_income(id):
    with get_conn().cursor() as cur:
        cur.execute("DELETE FROM incomes WHERE id=%s", (id,))
        affected = cur.rowcount
    flash(f"{'Deleted' if affected else 'Not found'} income #{id}.", "ok" if affected else "error")
    return redirect(url_for("list_income"))

# ---------- Analytics JSON ----------
@app.route("/api/summary")
def api_summary():
    d_from, d_to = default_range()
    return jsonify(totals_between(d_from, d_to))

@app.route("/api/expense_by_category")
def api_expense_by_category():
    month = request.args.get("month")
    with get_conn().cursor() as cur:
        if month and len(month) == 7:
            cur.execute("""
                SELECT c.name AS label, COALESCE(SUM(e.amount),0) AS value
                FROM expenses e
                JOIN categories c ON c.id = e.category_id
                WHERE e.tx_date >= CONCAT(%s, '-01')
                  AND e.tx_date <  DATE_FORMAT(DATE_ADD(CONCAT(%s,'-01'), INTERVAL 1 MONTH), '%%Y-%%m-%%d')
                GROUP BY c.name ORDER BY value DESC;
            """, (month, month))
        else:
            cur.execute("""
                SELECT c.name AS label, COALESCE(SUM(e.amount),0) AS value
                FROM expenses e
                JOIN categories c ON c.id = e.category_id
                WHERE e.tx_date >= DATE_FORMAT(CURDATE(), '%%Y-%%m-01')
                  AND e.tx_date <  DATE_FORMAT(DATE_ADD(CURDATE(), INTERVAL 1 MONTH), '%%Y-%%m-01')
                GROUP BY c.name ORDER BY value DESC;
            """)
        rows = cur.fetchall()
    return jsonify(rows)

@app.route("/api/income_by_category")
def api_income_by_category():
    month = request.args.get("month")
    with get_conn().cursor() as cur:
        if month and len(month) == 7:
            # e.g. 2025-08
            cur.execute("""
                SELECT ic.name AS label, COALESCE(SUM(i.amount),0) AS value
                FROM incomes i
                JOIN income_categories ic ON ic.id = i.category_id
                WHERE i.tx_date >= CONCAT(%s, '-01')
                  AND i.tx_date <  DATE_FORMAT(DATE_ADD(CONCAT(%s,'-01'), INTERVAL 1 MONTH), '%%Y-%%m-%%d')
                GROUP BY ic.name
                ORDER BY value DESC;
            """, (month, month))
        else:
            # current month
            cur.execute("""
                SELECT ic.name AS label, COALESCE(SUM(i.amount),0) AS value
                FROM incomes i
                JOIN income_categories ic ON ic.id = i.category_id
                WHERE i.tx_date >= DATE_FORMAT(CURDATE(), '%%Y-%%m-01')
                  AND i.tx_date <  DATE_FORMAT(DATE_ADD(CURDATE(), INTERVAL 1 MONTH), '%%Y-%%m-01')
                GROUP BY ic.name
                ORDER BY value DESC;
            """)
        rows = cur.fetchall()
    return jsonify(rows)

@app.route("/api/cashflow_daily")
def api_cashflow_daily():
    try:
        days = max(1, min(90, int(request.args.get("days", "30"))))
    except Exception:
        days = 30
    start = date.today() - timedelta(days=days-1)
    with get_conn().cursor() as cur:
        cur.execute("SELECT tx_date, SUM(amount) AS total FROM expenses WHERE tx_date >= %s GROUP BY tx_date", (start,))
        exp_map = {str(r["tx_date"]): float(r["total"]) for r in cur.fetchall()}
        cur.execute("SELECT tx_date, SUM(amount) AS total FROM incomes WHERE tx_date >= %s GROUP BY tx_date", (start,))
        inc_map = {str(r["tx_date"]): float(r["total"]) for r in cur.fetchall()}
    labels, inc, exp = [], [], []
    for i in range(days):
        d = str(start + timedelta(days=i))
        labels.append(d)
        inc.append(round(inc_map.get(d, 0.0), 2))
        exp.append(round(exp_map.get(d, 0.0), 2))
    return jsonify({"labels": labels, "income": inc, "expense": exp})

@app.route("/api/monthly_totals")
def api_monthly_totals():
    try:
        m = max(3, min(24, int(request.args.get("months", "12"))))
    except Exception:
        m = 12
    with get_conn().cursor() as cur:
        cur.execute("SELECT DATE_FORMAT(tx_date, '%%Y-%%m') AS ym, SUM(amount) AS total FROM expenses GROUP BY ym ORDER BY ym DESC LIMIT %s", (m,))
        exp = {r["ym"]: float(r["total"]) for r in cur.fetchall()}
        cur.execute("SELECT DATE_FORMAT(tx_date, '%%Y-%%m') AS ym, SUM(amount) AS total FROM incomes GROUP BY ym ORDER BY ym DESC LIMIT %s", (m,))
        inc = {r["ym"]: float(r["total"]) for r in cur.fetchall()}
    months = sorted(set(exp.keys()) | set(inc.keys()))
    months = months[-m:]
    labels, income, expense, net = [], [], [], []
    for ym in months:
        i = round(inc.get(ym, 0.0), 2)
        e = round(exp.get(ym, 0.0), 2)
        labels.append(ym)
        income.append(i)
        expense.append(e)
        net.append(round(i - e, 2))
    return jsonify({"labels": labels, "income": income, "expense": expense, "net": net})

# ---------- CSV EXPORT ----------
def _csv_response(filename: str, headers: list[str], rows: list[dict]):
    buff = io.StringIO()
    w = csv.writer(buff)
    w.writerow(headers)
    for r in rows:
        w.writerow([r.get(k) for k in headers])
    data = buff.getvalue().encode("utf-8-sig")  # BOM for Excel
    return Response(
        data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.route("/export/expenses.csv")
def export_expenses_csv():
    d_from = parse_ymd(request.args.get("from", "")) or None
    d_to   = parse_ymd(request.args.get("to", "")) or None
    cat_id = request.args.get("category_id")

    where, params = [], []
    if d_from: where.append("e.tx_date >= %s"); params.append(d_from)
    if d_to:   where.append("e.tx_date <= %s"); params.append(d_to)
    if cat_id and cat_id.isdigit():
        where.append("e.category_id = %s"); params.append(int(cat_id))

    sql = """
        SELECT e.id AS id, e.tx_date AS date, c.name AS category, e.amount AS amount,
               e.payment_method AS method, e.merchant AS merchant, e.note AS note
        FROM expenses e JOIN categories c ON c.id = e.category_id
    """
    if where: sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY e.tx_date, e.id;"

    with get_conn().cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    fname = f'expenses_{(d_from or "")}_{(d_to or "")}.csv'.replace(":", "-")
    return _csv_response(fname, ["id","date","category","amount","method","merchant","note"], rows)

@app.route("/export/income.csv")
def export_income_csv():
    d_from = parse_ymd(request.args.get("from", "")) or None
    d_to   = parse_ymd(request.args.get("to", "")) or None
    cat_id = request.args.get("category_id")

    where, params = [], []
    if d_from: where.append("i.tx_date >= %s"); params.append(d_from)
    if d_to:   where.append("i.tx_date <= %s"); params.append(d_to)
    if cat_id and cat_id.isdigit():
        where.append("i.category_id = %s"); params.append(int(cat_id))

    sql = """
        SELECT i.id AS id, i.tx_date AS date, ic.name AS category, i.amount AS amount,
               i.source AS source, i.note AS note
        FROM incomes i JOIN income_categories ic ON ic.id = i.category_id
    """
    if where: sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY i.tx_date, i.id;"

    with get_conn().cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    fname = f'income_{(d_from or "")}_{(d_to or "")}.csv'.replace(":", "-")
    return _csv_response(fname, ["id","date","category","amount","source","note"], rows)

# ---------- misc ----------
@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import os
    DEBUG = os.getenv("MYWALLET_DEBUG", "1") == "1"  # your BAT can set this to 0/1
    if DEBUG:
        app.config.update(TEMPLATES_AUTO_RELOAD=True, SEND_FILE_MAX_AGE_DEFAULT=0)
    app.run(host="127.0.0.1", port=5000, debug=DEBUG)
