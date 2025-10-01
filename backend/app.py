# app.py
import os
import threading
from datetime import date, datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import telebot

from db_helpers import create_user, get_user, update_balance, connect_wallet, get_leaderboard, mark_task, check_and_award_milestones, get_conn

# CONFIG: set these as environment variables in Replit or local shell
BOT_TOKEN = os.environ.get('BOT_TOKEN') or 'PUT_YOUR_BOT_TOKEN_HERE'
FRONTEND_URL = os.environ.get('FRONTEND_URL') or ''  # example: https://flage-app.vercel.app
BACKEND_URL = os.environ.get('BACKEND_URL') or ''    # example: https://your-backend.repl.co
CHECKIN_REWARDS = [50,70,90,110,130,150,170]

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

# ---------- FLASK API ----------
@app.route('/api/balance')
def api_balance():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({'ok':False,'error':'user_id missing'}), 400
    u = get_user(user_id) or {'balance':0}
    return jsonify({'ok':True,'balance': u['balance']})

@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    data = request.json or {}
    user_id = int(data.get('user_id') or 0)
    if not user_id:
        return jsonify({'ok':False,'error':'user_id missing'}),400
    create_user(user_id)
    conn = get_conn()
    c = conn.cursor()
    u = get_user(user_id)
    today = date.today().isoformat()
    if u['last_checkin'] == today:
        next_day = u['checkin_day']
        next_reward = CHECKIN_REWARDS[(next_day-1) % len(CHECKIN_REWARDS)]
        return jsonify({'ok':False,'error':'Already checked in today','next_day':next_day,'next_reward':next_reward}),400
    day = u['checkin_day'] or 1
    reward = CHECKIN_REWARDS[(day-1) % len(CHECKIN_REWARDS)]
    new_day = 1 if day >= 7 else day + 1
    now = datetime.utcnow().isoformat()
    c.execute("UPDATE users SET balance = balance + ?, total_earned = total_earned + ?, last_checkin = ?, checkin_day = ? WHERE user_id=?", (reward, reward, today, new_day, user_id))
    c.execute("INSERT INTO tasks (user_id, task_type, amount, details, created_at) VALUES (?,?,?,?,?)", (user_id, 'daily_checkin', reward, '', now))
    conn.commit()
    conn.close()
    check_and_award_milestones(user_id)
    new_bal = get_user(user_id)['balance']
    next_info = get_user(user_id)
    next_day = next_info['checkin_day']
    next_reward = CHECKIN_REWARDS[(next_day-1) % len(CHECKIN_REWARDS)]
    return jsonify({'ok':True,'new_balance': new_bal,'next_day': next_day,'next_reward': next_reward})

@app.route('/api/checkin_info')
def api_checkin_info():
    user_id = int(request.args.get('user_id') or 0)
    if not user_id:
        return jsonify({'ok':False,'error':'user_id missing'}),400
    u = get_user(user_id) or {}
    day = u.get('checkin_day',1)
    reward = CHECKIN_REWARDS[(day-1) % len(CHECKIN_REWARDS)]
    return jsonify({'ok':True,'day':day,'reward':reward})

@app.route('/api/complete_task', methods=['POST'])
def api_complete_task():
    data = request.json or {}
    user_id = int(data.get('user_id') or 0)
    task = data.get('task') or 'task'
    amount = int(data.get('amount') or 0)
    if not user_id:
        return jsonify({'ok':False,'error':'user_id missing'}),400
    create_user(user_id)
    if amount <= 0:
        return jsonify({'ok':False,'error':'amount must be > 0'}),400
    mark_task(user_id, task, amount)
    check_and_award_milestones(user_id)
    new_bal = get_user(user_id)['balance']
    return jsonify({'ok':True,'new_balance': new_bal})

@app.route('/api/connect_wallet', methods=['POST'])
def api_connect_wallet():
    data = request.json or {}
    user_id = int(data.get('user_id') or 0)
    wallet = data.get('wallet') or ''
    if not user_id:
        return jsonify({'ok':False,'error':'user_id missing'}),400
    create_user(user_id)
    connect_wallet(user_id, wallet)
    return jsonify({'ok':True,'wallet': wallet})

@app.route('/api/leaderboard')
def api_leaderboard():
    limit = int(request.args.get('limit') or 50)
    leaders = get_leaderboard(limit=limit)
    return jsonify({'ok':True,'leaders':leaders})

# ---------- TELEGRAM BOT ----------
@bot.message_handler(commands=['start'])
def handle_start(msg):
    chat_id = msg.from_user.id
    parts = (msg.text or '').split()
    ref = None
    if len(parts) > 1:
        try:
            ref = int(parts[1])
        except:
            ref = None
    username = msg.from_user.username
    first_name = msg.from_user.first_name
    created = create_user(chat_id, username=username, first_name=first_name, referrer=ref)
    if created and ref and ref != chat_id:
        ref_user = get_user(ref)
        if ref_user:
            update_balance(ref, 30, note=f'invite_bonus_for_{chat_id}')
    try:
        me = bot.get_me()
        bot_username = me.username
    except:
        bot_username = 'YOUR_BOT'
    webapp_url = FRONTEND_URL
    if webapp_url:
        sep = '&' if '?' in webapp_url else '?'
        webapp_url = f"{webapp_url}{sep}user_id={chat_id}&backend={BACKEND_URL}&bot={bot_username}"
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        webapp = telebot.types.WebAppInfo(webapp_url)
        btn = telebot.types.KeyboardButton(text="🚀 Open Mining", web_app=webapp)
        markup.add(btn)
        bot.send_message(chat_id, "Welcome! Click button to open FLAGE mini app.", reply_markup=markup)
    else:
        link = f"https://t.me/{bot_username}?start={chat_id}"
        bot.send_message(chat_id, f"Welcome! Your referral link:\n{link}")

@bot.message_handler(commands=['balance'])
def handle_balance(msg):
    uid = msg.from_user.id
    u = get_user(uid) or {}
    bot.send_message(uid, f"💰 Your balance: {u.get('balance',0)} FLAG")

@bot.message_handler(commands=['referral'])
def handle_referral(msg):
    uid = msg.from_user.id
    try:
        me = bot.get_me()
        bot_username = me.username
    except:
        bot_username = 'YOUR_BOT'
    link = f"https://t.me/{bot_username}?start={uid}"
    text = ("Share this link to invite friends:\n" + link +
            "\n\nYou get 30 FLAG for each friend who joins. Plus 100 FLAG whenever your friend reaches each 1000 FLAG milestone.")
    bot.send_message(uid, text)

@bot.message_handler(commands=['leaderboard'])
def handle_leaderboard(msg):
    rows = get_leaderboard(limit=10)
    text = "🏆 Top users:\n"
    for i,r in enumerate(rows, start=1):
        uname = r['username'] or str(r['user_id'])
        text += f"{i}. {uname} — {r['balance']} FLAG\n"
    bot.send_message(msg.chat.id, text)

def run_bot():
    print("Bot polling started...")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)

if __name__ == '__main__':
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
