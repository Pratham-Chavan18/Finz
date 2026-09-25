import os
import sys
from pathlib import Path
import psycopg2


def get_database_url() -> str:
    """Retrieve DATABASE_URL from environment or project-root .env file."""
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")

    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                val = line.split("=", 1)[1].strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                return val

    return "postgresql://app_user:finpassword@localhost:5432/finreview"


def main():
    db_url = get_database_url()
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # Columns
    cur.execute("""
        SELECT column_name, data_type, numeric_precision, numeric_scale 
        FROM information_schema.columns 
        WHERE table_name = 'transactions' AND column_name IN ('amount', 'raw_data')
        ORDER BY column_name;
    """)
    print("TRANSACTION COLUMNS:")
    for row in cur.fetchall():
        print(" ", row)

    # Tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    print("\nTABLES:")
    for row in cur.fetchall():
        print(" ", row[0])

    # RLS Policies
    cur.execute("SELECT tablename, policyname FROM pg_policies ORDER BY tablename;")
    print("\nRLS POLICIES:")
    for row in cur.fetchall():
        print(" ", row)

    # Triggers
    cur.execute("""
        SELECT trigger_name, event_manipulation, event_object_table 
        FROM information_schema.triggers 
        WHERE event_object_table = 'audit_logs';
    """)
    print("\nAUDIT TRIGGERS:")
    for row in cur.fetchall():
        print(" ", row)

    conn.close()


if __name__ == "__main__":
    main()
