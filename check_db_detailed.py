import sqlite3
import os

DB_PATH = "c:\\Harishma\\Maitexa\\Acadeno\\Flask_Certificate\\Aca\\certificates.db"

if not os.path.exists(DB_PATH):
    print(f"Database file not found at {DB_PATH}")
else:
    conn = sqlite3.connect(DB_PATH)
    # Print the table columns
    # c.execute("PRAGMA table_info(certificates)")
    # print(c.fetchall())
    
    c = conn.cursor()
    c.execute("SELECT id, certificate_number, student_name FROM certificates ORDER BY id DESC LIMIT 5")
    rows = c.fetchall()
    for row in rows:
        print(row)
    
    c.execute("SELECT count(*) FROM certificates")
    count = c.fetchone()[0]
    print(f"Total records: {count}")
    
    conn.close()
