import sqlite3
import os

DB_PATH = "c:\\Harishma\\Maitexa\\Acadeno\\Flask_Certificate\\Aca\\certificates.db"

if not os.path.exists(DB_PATH):
    print(f"Database file not found at {DB_PATH}")
else:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM certificates ORDER BY id DESC LIMIT 5")
    rows = c.fetchall()
    print(f"Last 5 records: {rows}")
    
    c.execute("SELECT count(*) FROM certificates")
    count = c.fetchone()[0]
    print(f"Total records: {count}")
    
    conn.close()
