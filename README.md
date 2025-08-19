# Expense & Income Management App (Flask + MySQL) + Power BI

A lightweight web app to **log expenses and incomes** with a **Power BI** report for daily net balance and category insights.

- **Database:** MySQL / MariaDB (e.g., XAMPP)
- **Backend:** Python (Flask, SQLAlchemy)
- **Dashboard:** Power BI (`powerbi/dashboard.pbix`)

---

## Features
- Add / edit / delete **expenses** and **incomes**
- **Daily Net Balance** (Income − Expense)
- Category-wise analytics page
- Simple HTML UI (Jinja templates)
- DB connection health check (`/health`)
- Power BI dashboard for trends & breakdowns

---

## Folder Structure
- `powerbi/`
  - `dashboard.pbix`
- `static/`
  - `logo.svg`
  - `style.css`
- `templates/`
  - `add_expense.html`
  - `add_income.html`
  - `analytics.html`
  - `base.html`
  - `edit_expense.html`
  - `edit_income.html`
  - `home.html`
  - `list_expenses.html`
  - `list_income.html`
- `app.py`
- `db_test.py`
- `requirements.txt`
- `start_mywallet_xampp.bat` *(optional helper)*
- `.gitignore`
- `README.md`

---

## Prerequisites
- **Python** 3.10+
- **MySQL/MariaDB** running locally (XAMPP → start *MySQL*)
- (Optional) **Power BI Desktop** to open `dashboard.pbix`

---

## Setup & Run (Windows / VS Code)

```powershell
# 1) Create & activate venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Install dependencies
pip install -r requirements.txt

# 3) Configure environment
# Create .env in the project root with your DB URL:
# For mysql-connector-python:
# DATABASE_URL=mysql+mysqlconnector://expense_user:2222@127.0.0.1:3306/expense_db
# (Or, for PyMySQL)
# DATABASE_URL=mysql+pymysql://expense_user:2222@127.0.0.1:3306/expense_db
