import sqlite3
import os

dbs = ['apps/api/preview.db', 'backend/market_intelligence.db']
for db in dbs:
    if os.path.exists(db):
        print(f"=== {db} ===")
        con = sqlite3.connect(db)
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        for t in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM `{t}`")
                print(f"  {t}: {cur.fetchone()[0]}")
            except Exception as e:
                print(f"  {t}: error {e}")
    else:
        print(f"{db} does not exist")
