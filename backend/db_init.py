# db_init.py
import sqlite3

DB_FILE = 'flage.db'

conn = sqlite3.connect(DB_FILE)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    referrer INTEGER,
    balance INTEGER DEFAULT 0,
    total_earned INTEGER DEFAULT 0,
    checkin_day INTEGER DEFAULT 1,
    last_checkin TEXT DEFAULT '',
    milestones_awarded INTEGER DEFAULT 0,
    wallet TEXT DEFAULT '',
    created_at TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    task_type TEXT,
    amount INTEGER,
    details TEXT,
    created_at TEXT
)
""")

conn.commit()
conn.close()
print("Database initialized:", DB_FILE)
