from contextlib import contextmanager
import pymysql

from config import get_settings


@contextmanager
def get_connection():
    settings = get_settings()
    conn = pymysql.connect(
        host=settings.db_host,
        user=settings.db_user,
        password=settings.db_pass,
        database=settings.db_name,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )
    try:
        yield conn
    finally:
        conn.close()
