# ia/db_mysql.py
import pymysql

_conn = None

def get_connection():
    global _conn
    try:
        if _conn is None or not _conn.open:
            _conn = pymysql.connect(
                host="localhost",
                user="root",
                password="root",
                database="e_commmerce",
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor
            )
        return _conn
    except Exception as e:
        print(f"[DB] Erreur connexion MySQL : {e}")
        return None


def fetch_all(query: str) -> list:
    conn = get_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()
    except Exception as e:
        print(f"[DB] Erreur requête : {e}")
        return []