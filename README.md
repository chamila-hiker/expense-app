# Expense & Income Management App (Flask + MySQL) + Power BI

A lightweight web app to **log expenses/incomes** and a **Power BI** report to analyze daily net balance and category trends.

   **Database:** MySQL (e.g., XAMPP MySQL)  
   **Backend:** Python (Flask, SQLAlchemy)  
   **Dashboard:** Power BI (`powerbi/dashboard.pbix`)

---

## Features
- Add / edit / delete **expenses** and **incomes**
- **Daily Net Balance** (Income − Expense)
- Category-wise analytics page
- Simple HTML UI (Jinja templates)
- Health / DB test script
- Power BI dashboard for trends & breakdowns

---

## Folder Structure
- powerbi/
  - dashboard.pbix
- static/
  - logo.svg
  - style.css
- templates/
  - add_expense.html
  - add_income.html
  - analytics.html
  - base.html
  - edit_expense.html
  - edit_income.html
  - home.html
  - list_expenses.html
  - list_income.html
- app.py
- db_test.py
- requirements.txt
- start_mywallet_xampp.bat (optional)
- .gitignore
- README.md

