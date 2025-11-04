# --------------------------------------------------------------
# AlienX Access Control Bot (Telegram + Firebase)
# Syncs with Flask API via settings/trail_enabled
# --------------------------------------------------------------

import os
import time
import logging
from threading import Thread
from datetime import datetime, timedelta
import telebot
import firebase_admin
from firebase_admin import credentials, db

# ------------------------------------------------------------------
# 1. Config & Logging
# ------------------------------------------------------------------
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set!")

ADMIN_IDS = [5316048641, 5819790024]  # Add your IDs

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN)

# ------------------------------------------------------------------
# 2. Firebase
# ------------------------------------------------------------------
cred_path = os.environ.get('FIREBASE_CRED_PATH', 'firebase-key.json')
cred = credentials.Certificate(cred_path)

firebase_admin.initialize_app(cred, {
    'databaseURL': os.environ.get(
        'FIREBASE_URL',
        'https://alien-51afb-default-rtdb.firebaseio.com/'
    )
})

users_ref = db.reference('users')
settings_ref = db.reference('settings')

# ------------------------------------------------------------------
# 3. Helpers
# ------------------------------------------------------------------
def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_trail_enabled():
    try:
        val = settings_ref.child('trail_enabled').get()
        return bool(val) if val is not None else False
    except:
        return False

def parse_duration(duration_str):
    try:
        value = int(duration_str[:-1])
        unit = duration_str[-1].lower()
        if unit == 'd': return timedelta(days=value)
        if unit == 'h': return timedelta(hours=value)
        if unit == 'm': return timedelta(days=30 * value)
        return None
    except:
        return None

def format_time(expiry_str):
    try:
        expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        if now > expiry:
            return "EXPIRED", "Expired"
        delta = expiry - now
        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        mins, _ = divmod(rem, 60)
        rem_str = f"{days}d {hours}h {mins}m" if days else f"{hours}h {mins}m" if hours else f"{mins}m"
        return "ACTIVE", rem_str
    except:
        return "ERROR", "Invalid"

# ------------------------------------------------------------------
# 4. Bot Commands
# ------------------------------------------------------------------
@bot.message_handler(commands=['start'])
def start(message):
    trail = "ON (Everyone has access)" if is_trail_enabled() else "OFF"
    if is_admin(message.from_user.id):
        text = f"""
*AlienX Admin Panel*

*Trail Status:* `{trail}`
*Commands:*
• `/add <id> <30d>` – Add user
• `/remove <id>` – Remove user
• `/check <id>` – Check access
• `/users` – List users
• `/trailon` – Enable public trail
• `/trailoff` – Disable public trail
• `/stats` – Bot stats

*Owners:* @aurenkai | @aliensexy
        """
    else:
        text = f"""
*AlienX Access Bot*

*Trail Status:* `{trail}`
Use `/check` to see your access.

*Contact:* @aurenkai | @aliensexy
        """
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['trailon'])
def trail_on(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Not authorized.")
        return
    settings_ref.child('trail_enabled').set(True)
    bot.reply_to(message, "PUBLIC TRAIL ENABLED – Everyone has file access!")

@bot.message_handler(commands=['trailoff'])
def trail_off(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Not authorized.")
        return
    settings_ref.child('trail_enabled').set(False)
    bot.reply_to(message, "PUBLIC TRAIL DISABLED – Only registered users.")

@bot.message_handler(commands=['add'])
def add_user(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Not authorized.")
        return
    try:
        parts = message.text.split()
        if len(parts) != 3:
            raise ValueError()
        user_id, duration = parts[1], parts[2]
        delta = parse_duration(duration)
        if not delta:
            raise ValueError()
        expiry = datetime.now() + delta
        users_ref.child(user_id).set({
            'expiry': expiry.strftime("%Y-%m-%d %H:%M:%S"),
            'type': 'premium',
            'created': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        bot.reply_to(message, f"User `{user_id}` added!\nExpires: `{expiry.strftime('%Y-%m-%d %H:%M')}`", parse_mode='Markdown')
    except:
        bot.reply_to(message, "*Usage:* `/add <id> <30d>`\n*Examples:* `30d`, `12h`, `6m`", parse_mode='Markdown')

@bot.message_handler(commands=['remove'])
def remove_user(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Not authorized.")
        return
    try:
        user_id = message.text.split()[1]
        if users_ref.child(user_id).get():
            users_ref.child(user_id).delete()
            bot.reply_to(message, f"User `{user_id}` removed.", parse_mode='Markdown')
        else:
            bot.reply_to(message, "User not found.")
    except:
        bot.reply_to(message, "*Usage:* `/remove <id>`", parse_mode='Markdown')

@bot.message_handler(commands=['check'])
def check_access(message):
    try:
        parts = message.text.split()
        user_id = parts[1] if len(parts) > 1 else str(message.from_user.id)
        if len(parts) > 1 and not is_admin(message.from_user.id):
            bot.reply_to(message, "You can only check your own access.")
            return

        if is_trail_enabled():
            bot.reply_to(message, f"User `{user_id}`\n*Access:* PUBLIC TRAIL ACTIVE", parse_mode='Markdown')
            return

        data = users_ref.child(user_id).get()
        if not data:
            bot.reply_to(message, f"User `{user_id}` not registered.", parse_mode='Markdown')
            return

        status, rem = format_time(data['expiry'])
        bot.reply_to(message, f"""
*User:* `{user_id}`
*Type:* `{data.get('type', 'unknown')}`
*Status:* `{status}`
*Remaining:* `{rem}`
*Expires:* `{data['expiry']}`
        """, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, "Error. Use `/check` or `/check <id>`")

@bot.message_handler(commands=['users'])
def list_users(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Not authorized.")
        return
    users = users_ref.get() or {}
    if not users:
        bot.reply_to(message, "No users.")
        return
    lines = []
    for uid, data in users.items():
        status, rem = format_time(data['expiry'])
        lines.append(f"`{uid}` – {status} {rem}")
    text = "*Registered Users:*\n" + "\n".join(lines[:20])
    if len(users) > 20:
        text += f"\n... and {len(users)-20} more."
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def stats(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "Not authorized.")
        return
    users = users_ref.get() or {}
    active = sum(1 for d in users.values() if format_time(d['expiry'])[0] == "ACTIVE")
    trail = "ON" if is_trail_enabled() else "OFF"
    bot.reply_to(message, f"""
*Stats*
• Total Users: `{len(users)}`
• Active: `{active}`
• Public Trail: `{trail}`
    """, parse_mode='Markdown')

@bot.message_handler(func=lambda m: True)
def unknown(message):
    bot.reply_to(message, "Unknown command. Use /start")

# ------------------------------------------------------------------
# 5. Flask Keeper (Render.com) – Optional but recommended
# ------------------------------------------------------------------
from flask import Flask
keep_alive = Flask(__name__)

@keep_alive.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    keep_alive.run(host='0.0.0.0', port=port, threaded=True)

# ------------------------------------------------------------------
# 6. Polling with Auto-Restart
# ------------------------------------------------------------------
def start_polling():
    while True:
        try:
            logger.info("Starting bot polling...")
            bot.remove_webhook()
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(15)

# ------------------------------------------------------------------
# 7. Main
# ------------------------------------------------------------------
if __name__ == '__main__':
    logger.info("AlienX Bot Starting...")

    # Start Flask keeper in background
    Thread(target=run_flask, daemon=True).start()
    time.sleep(2)

    # Start bot
    start_polling()
