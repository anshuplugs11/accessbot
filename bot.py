import os
from datetime import datetime, timedelta
from threading import Thread
import telebot
import firebase_admin
from firebase_admin import credentials, db
from flask import Flask

# Bot token
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ADMIN_IDS = [7380972597, 7307878729]

bot = telebot.TeleBot(BOT_TOKEN)

# Initialize Firebase
firebase_cred_path = os.environ.get('FIREBASE_CRED_PATH', 'firebase-key.json')
cred = credentials.Certificate(firebase_cred_path)
firebase_admin.initialize_app(cred, {
    'databaseURL': os.environ.get('FIREBASE_URL', 'https://alienx-access-control-default-rtdb.firebaseio.com/')
})

users_ref = db.reference('users')

# Flask app to keep Render service alive
app = Flask(__name__)

@app.route('/')
def home():
    return "🚀 AlienX Bot is running!"

@app.route('/health')
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# Bot handlers
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(
        message,
        "🚀 AlienX Access Control Bot\n\n"
        "Commands:\n"
        "• /register <id> <duration>\n"
        "• /list\n"
        "• /delete <id>\n\n"
        "Contact: @alienx"
    )

@bot.message_handler(commands=['register'])
def register_user(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return

    try:
        _, user_id, duration = message.text.split()
        duration_value = int(duration[:-1])
        duration_unit = duration[-1]
    except:
        bot.reply_to(
            message,
            "Format: /register <id> <duration>\n"
            "Example: /register john123 30d"
        )
        return

    try:
        if duration_unit == "d":
            expiration = datetime.now() + timedelta(days=duration_value)
        elif duration_unit == "h":
            expiration = datetime.now() + timedelta(hours=duration_value)
        elif duration_unit == "m":
            expiration = datetime.now() + timedelta(days=30 * duration_value)
        else:
            raise ValueError()

        # Save to Firebase
        users_ref.child(user_id).set({
            'expiry': expiration.strftime("%Y-%m-%d %H:%M:%S"),
            'created': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        bot.reply_to(
            message,
            f"✅ User `{user_id}` registered!\n"
            f"⏰ Expires: {expiration}\n"
            f"📅 Duration: {duration}",
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['list'])
def list_users(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return

    try:
        all_users = users_ref.get()
        
        if not all_users:
            bot.reply_to(message, "📂 No users registered.")
            return
        
        response = "📋 **Registered Users:**\n\n"
        for user_id, user_data in all_users.items():
            expiry = user_data.get('expiry', 'Unknown')
            try:
                expiry_date = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
                if datetime.now() > expiry_date:
                    status = "🔴 EXPIRED"
                else:
                    remaining = expiry_date - datetime.now()
                    status = f"🟢 {remaining.days}d left"
            except:
                status = "⚠️"
            
            response += f"`{user_id}` - {status}\n{expiry}\n\n"
        
        bot.reply_to(message, response, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['delete'])
def delete_user(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return

    try:
        _, user_id = message.text.split()
        
        if users_ref.child(user_id).get():
            users_ref.child(user_id).delete()
            bot.reply_to(message, f"✅ User `{user_id}` deleted.", parse_mode="Markdown")
        else:
            bot.reply_to(message, f"❌ User not found.")
    except:
        bot.reply_to(message, "Format: /delete <id>")

@bot.message_handler(func=lambda message: True)
def handle_all(message):
    bot.reply_to(message, "⚠️ Unknown command. Use /start")

if __name__ == "__main__":
    print("🚀 AlienX Bot Started on Render!")
    
    # Start Flask server in background thread
    Thread(target=run_flask, daemon=True).start()
    
    # Start bot polling
    bot.polling(none_stop=True, interval=0, timeout=60)
