# ia/db_mysql.py
import os
import pymysql

_conn = None

def get_connection():
    global _conn
    try:
        if _conn is None or not _conn.open:
            _conn = pymysql.connect(
                host=os.environ.get("MYSQL_HOST", "localhost"),         # "db" en Docker
                user=os.environ.get("MYSQL_USER", "root"),
                password=os.environ.get("MYSQL_PASSWORD", "root"),
                database=os.environ.get("MYSQL_DATABASE", "e_commmerce"),
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
        conn.commit()  # force la lecture des données fraîches
        with conn.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()
    except Exception as e:
        print(f"[DB] Erreur requête : {e}")
        return []