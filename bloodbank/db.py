import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

_candidates = [BASE_DIR / ".env", BASE_DIR.parent / "pg-docker" / ".env"]
if os.getenv("BLOODBANK_ENV_FILE"):
    _candidates.insert(0, Path(os.environ["BLOODBANK_ENV_FILE"]))

ENV_FILE = next((p for p in _candidates if p.is_file()), None)
if ENV_FILE:
    load_dotenv(ENV_FILE)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "bloodbank")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")

APP_NAME = "bloodbank_app"

_conn = None

def connect(dbname=DB_NAME, autocommit=False):
    if not DB_PASSWORD:
        raise RuntimeError("POSTGRES_PASSWORD not found - check the .env file "
                           f"(looked in: {', '.join(str(p) for p in _candidates)})")
    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=dbname,
                            user=DB_USER, password=DB_PASSWORD,
                            connect_timeout=3, application_name=APP_NAME)
    conn.autocommit = autocommit
    return conn

def get_connection():
    global _conn
    if _conn is None or _conn.closed:
        _conn = connect()
    return _conn

def _reset():
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except psycopg2.Error:
            pass
    _conn = None

def query(sql, params=None):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if cur.description is None:
                    return [], []
                return [c.name for c in cur.description], cur.fetchall()
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        _reset()
        raise

def connection_status():
    try:
        _, rows = query("SELECT current_database(), current_user, "
                        "current_setting('server_version')")
        dbname, user, version = rows[0]
        return True, f"Connected to {dbname} @ {DB_HOST}:{DB_PORT} as {user} (PostgreSQL {version})"
    except Exception as exc:
        return False, f"NOT CONNECTED to {DB_NAME} @ {DB_HOST}:{DB_PORT} - {error_message(exc)}"

def error_message(exc):
    if isinstance(exc, psycopg2.Error):
        diag = getattr(exc, "diag", None)
        if diag is not None and diag.message_primary:
            msg = diag.message_primary
            if diag.message_detail:
                msg += "\n" + diag.message_detail
            return msg
        return (exc.pgerror or str(exc)).strip()
    return str(exc)
