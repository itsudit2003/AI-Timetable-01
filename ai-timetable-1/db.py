import mysql.connector
from contextlib import contextmanager
from config import DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME

def get_db():
    return mysql.connector.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database=DB_NAME, autocommit=False
    )

@contextmanager
def db_cursor(commit=False):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    try:
        yield cur
        if commit:
            conn.commit()
    finally:
        cur.close()
        conn.close()
