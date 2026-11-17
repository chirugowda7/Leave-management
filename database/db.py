import sqlite3
import os
from config import Config

def get_db_connection():
    db_path = Config.DATABASE_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db_connection()
    schema_file = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_file, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    conn.commit()

    # Migration: Ensure profile_pic, verification_doc, blood_group, address exist on users table
    cur = conn.cursor()
    columns = [row[1] for row in cur.execute("PRAGMA table_info(users)").fetchall()]
    if 'profile_pic' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN profile_pic TEXT;")
        conn.commit()
    if 'verification_doc' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN verification_doc TEXT;")
        conn.commit()
    if 'blood_group' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN blood_group TEXT;")
        conn.commit()
    if 'address' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN address TEXT;")
        conn.commit()

    verif_cols = [row[1] for row in cur.execute("PRAGMA table_info(employee_verification)").fetchall()]
    if 'verification_doc' not in verif_cols:
        cur.execute("ALTER TABLE employee_verification ADD COLUMN verification_doc TEXT;")
        conn.commit()
    if 'blood_group' not in verif_cols:
        cur.execute("ALTER TABLE employee_verification ADD COLUMN blood_group TEXT;")
        conn.commit()
    if 'address' not in verif_cols:
        cur.execute("ALTER TABLE employee_verification ADD COLUMN address TEXT;")
        conn.commit()

    conn.close()

def query_db(query, args=(), one=False):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    if one:
        return rv[0] if rv else None
    return rv

def execute_db(query, args=()):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    lastid = cur.lastrowid
    conn.close()
    return lastid

def execute_many_db(query, args_list):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.executemany(query, args_list)
    conn.commit()
    conn.close()
