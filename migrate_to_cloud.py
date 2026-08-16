import os
import sqlite3
import sys
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "certificates.db")
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def migrate():
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL environment variable is missing from .env file!")
        print("Please add your Cloud PostgreSQL connection string to your .env file:")
        print("DATABASE_URL=postgresql://user:password@host:5432/dbname")
        return False

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Local SQLite database file not found at {DB_PATH}")
        return False

    print(f"Connecting to local SQLite DB: {DB_PATH}...")
    sqlite_conn = sqlite3.connect(DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    sqlite_cursor.execute("SELECT certificate_number, student_name, pdf_path, cloudinary_url, created_at FROM certificates ORDER BY id ASC")
    rows = sqlite_cursor.fetchall()
    sqlite_conn.close()

    print(f"Found {len(rows)} local records to migrate.")

    try:
        import psycopg2
        print(f"Connecting to Cloud PostgreSQL database...")
        pg_conn = psycopg2.connect(DATABASE_URL)
        pg_cursor = pg_conn.cursor()

        # Create table if not exists
        pg_cursor.execute("""
            CREATE TABLE IF NOT EXISTS certificates (
                id SERIAL PRIMARY KEY,
                certificate_number TEXT,
                student_name TEXT,
                pdf_path TEXT,
                cloudinary_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        pg_conn.commit()

        # Check existing count in Cloud PG
        pg_cursor.execute("SELECT COUNT(*) FROM certificates")
        existing_pg_count = pg_cursor.fetchone()[0]
        print(f"Cloud PostgreSQL currently has {existing_pg_count} records.")

        migrated_count = 0
        for r in rows:
            # Avoid duplicate inserts
            pg_cursor.execute("SELECT id FROM certificates WHERE certificate_number = %s", (r["certificate_number"],))
            if not pg_cursor.fetchone():
                pg_cursor.execute(
                    """
                    INSERT INTO certificates (certificate_number, student_name, pdf_path, cloudinary_url, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (r["certificate_number"], r["student_name"], r["pdf_path"], r["cloudinary_url"], r["created_at"])
                )
                migrated_count += 1

        pg_conn.commit()
        pg_cursor.close()
        pg_conn.close()

        print(f"SUCCESS: Migrated {migrated_count} records to Cloud PostgreSQL database!")
        return True

    except Exception as e:
        print(f"ERROR migrating to PostgreSQL: {e}")
        return False


if __name__ == "__main__":
    migrate()
