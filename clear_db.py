import sqlite3

conn = sqlite3.connect("certificates.db")
cur = conn.cursor()

cur.execute("DELETE FROM certificates")
cur.execute("DELETE FROM sqlite_sequence WHERE name='certificates'")

conn.commit()
conn.close()

print("Certificates table cleared successfully")
