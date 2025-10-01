# db_helpers.py
import sqlite3
from datetime import datetime

DB_FILE = 'flage.db'

def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def create_user(user_id, username=None, first_name=None, referrer=None):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    exists = c.fetchone() is not None
    if exists:
        c.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?", (username, first_name, user_id))
        conn.commit()
        conn.close()
        return False
    else:
        c.execute("""INSERT INTO users (user_id, username, first_name, referrer, balance, total_earned,
                     checkin_day, last_checkin, milestones_awarded, wallet, created_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (user_id, username, first_name, referrer, 0, 0, 1, '', 0, '', now))
        conn.commit()
        conn.close()
        return True

def get_user(user_id):
    c = get_conn().cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    return dict(row) if row else None

def update_balance(user_id, amount, note=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id=?", (amount, amount, user_id))
    now = datetime.utcnow().isoformat()
    c.execute("INSERT INTO tasks (user_id, task_type, amount, details, created_at) VALUES (?,?,?,?,?)",
              (user_id, note or 'award', amount, '', now))
    conn.commit()
    conn.close()

def connect_wallet(user_id, wallet_address):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET wallet=? WHERE user_id=?", (wallet_address, user_id))
    now = datetime.utcnow().isoformat()
    c.execute("INSERT INTO tasks (user_id, task_type, amount, details, created_at) VALUES (?,?,?,?,?)",
              (user_id, 'connect_wallet', 0, wallet_address, now))
    conn.commit()
    conn.close()

def get_leaderboard(limit=500):
    c = get_conn().cursor()
    c.execute("SELECT user_id, username, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    return [dict(r) for r in rows]

def mark_task(user_id, task_type, amount):
    update_balance(user_id, amount, note=f"task:{task_type}")

def check_and_award_milestones(friend_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT referrer, total_earned, milestones_awarded FROM users WHERE user_id=?", (friend_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return
    referrer = row['referrer']
    total = row['total_earned'] or 0
    awarded = row['milestones_awarded'] or 0
    new_milestones = total // 1000
    if referrer and new_milestones > awarded:
        to_award = (new_milestones - awarded) * 100
        c.execute("UPDATE users SET milestones_awarded = ? WHERE user_id=?", (new_milestones, friend_id))
        c.execute("UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id=?", (to_award, to_award, referrer))
        now = datetime.utcnow().isoformat()
        c.execute("INSERT INTO tasks (user_id, task_type, amount, details, created_at) VALUES (?,?,?,?,?)",
                  (referrer, f'milestone_from_{friend_id}', to_award, '', now))
        conn.commit()
    conn.close()
