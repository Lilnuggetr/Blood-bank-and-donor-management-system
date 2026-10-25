import sys

from psycopg2 import sql

import db

SQL_FILES = ["01_schema.sql", "02_logic.sql", "03_seed.sql"]

def create_database():
    conn = db.connect("postgres", autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db.DB_NAME,))
            if cur.fetchone():
                print(f"Database '{db.DB_NAME}' already exists")
            else:
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db.DB_NAME)))
                print(f"Database '{db.DB_NAME}' created")
    finally:
        conn.close()

def run_sql_files():
    conn = db.connect()
    try:
        for name in SQL_FILES:
            path = db.BASE_DIR / "sql" / name
            with conn:
                with conn.cursor() as cur:
                    cur.execute(path.read_text(encoding="utf-8"))
            for notice in conn.notices:
                print("   ", notice.strip())
            conn.notices.clear()
            print(f"Ran sql/{name}")
    finally:
        conn.close()

def verify():
    conn = db.connect()
    checks = {
        "Tables": "SELECT table_name FROM information_schema.tables "
                  "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY 1",
        "Views": "SELECT table_name FROM information_schema.views "
                 "WHERE table_schema = 'public' ORDER BY 1",
        "Triggers": "SELECT DISTINCT trigger_name || ' ON ' || event_object_table "
                    "FROM information_schema.triggers WHERE trigger_schema = 'public' ORDER BY 1",
        "Functions": "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                     "WHERE n.nspname = 'public' ORDER BY 1",
    }
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user, inet_server_port(), "
                        "current_setting('server_version')")
            dbname, user, port, version = cur.fetchone()
            print(f"\nConnected to {dbname} @ {db.DB_HOST}:{db.DB_PORT} as {user} "
                  f"(PostgreSQL {version})")
            for title, q in checks.items():
                cur.execute(q)
                names = [r[0] for r in cur.fetchall()]
                print(f"{title} ({len(names)}): {', '.join(names)}")
            print("Row counts:")
            for table in ["donors", "donations", "blood_units", "hospitals",
                          "blood_requests", "blood_issues", "blood_compatibility"]:
                cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
                print(f"   {table:20} {cur.fetchone()[0]}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        create_database()
        run_sql_files()
        verify()
    except Exception as exc:
        print("ERROR:", db.error_message(exc))
        sys.exit(1)
    print("\nDone.")
