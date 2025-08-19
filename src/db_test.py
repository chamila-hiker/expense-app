import pymysql

CFG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "expense_user",
    "password": "StrongPassword123!",   # <-- your real password
    "database": "expense_db",
    "cursorclass": pymysql.cursors.DictCursor,
    "charset": "utf8mb4",
    "autocommit": True,
}

def main():
    print("Connecting to MySQL…")
    con = pymysql.connect(**CFG)
    with con.cursor() as cur:
        cur.execute("SELECT VERSION() AS ver")
        print("Server version:", cur.fetchone()["ver"])

        cur.execute("SELECT COUNT(*) AS n FROM categories")
        print("Categories in DB:", cur.fetchone()["n"])

        cur.execute("""
            SELECT e.id, e.tx_date, c.name AS category, e.amount, e.payment_method
            FROM expenses e
            JOIN categories c ON c.id = e.category_id
            ORDER BY e.id DESC LIMIT 5
        """)
        rows = cur.fetchall()
        if rows:
            print("\nRecent expenses:")
            for r in rows:
                print(f"- #{r['id']} {r['tx_date']} | {r['category']} | {r['amount']} | {r['payment_method']}")
        else:
            print("\nNo expenses yet. DB connection works!")

    con.close()
    print("\nOK: Python can talk to MySQL.")

if __name__ == "__main__":
    main()
