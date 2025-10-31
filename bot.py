import os
from datetime import datetime, timedelta
from threading import Thread
import time
import telebot
import firebase_admin
from firebase_admin import credentials, db
from flask import Flask

# Bot token
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ADMIN_IDS = [5316048641, 5819790024]

bot = telebot.TeleBot(BOT_TOKEN)

# Initialize Firebase
firebase_cred_path = os.environ.get('FIREBASE_CRED_PATH', 'firebase-key.json')
cred = credentials.Certificate(firebase_cred_path)
firebase_admin.initialize_app(cred, {
    'databaseURL': os.environ.get('FIREBASE_URL', 'https://alien-51afb-default-rtdb.firebaseio.com/')
})

users_ref = db.reference('users')
settings_ref = db.reference('settings')

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
    app.run(host='0.0.0.0', port=port, threaded=True)

# Helper functions
def is_trail_enabled():
    """Check if trail for ALL is enabled (public access)"""
    trail_setting = settings_ref.child('trail_enabled').get()
    return trail_setting if trail_setting is not None else False

def is_trial_enabled():
    """Check if trial system is enabled"""
    trial_setting = settings_ref.child('trial_enabled').get()
    return trial_setting if trial_setting is not None else False

def get_trial_duration():
    """Get trial duration in days (default 3 days)"""
    duration = settings_ref.child('trial_duration').get()
    return duration if duration else 3

def parse_duration(duration_str):
    """Parse duration string like 30d, 12h, 6m"""
    try:
        duration_value = int(duration_str[:-1])
        duration_unit = duration_str[-1].lower()
        
        if duration_unit == "d":
            return timedelta(days=duration_value)
        elif duration_unit == "h":
            return timedelta(hours=duration_value)
        elif duration_unit == "m":
            return timedelta(days=30 * duration_value)
        else:
            return None
    except:
        return None

def format_time_remaining(expiry_str):
    """Format remaining time nicely"""
    try:
        expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        
        if now > expiry_date:
            return "🔴 EXPIRED", "Access ended"
        
        remaining = expiry_date - now
        days = remaining.days
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60
        
        if days > 0:
            time_str = f"{days}d {hours}h"
        elif hours > 0:
            time_str = f"{hours}h {minutes}m"
        else:
            time_str = f"{minutes}m"
        
        return "🟢 ACTIVE", time_str
    except:
        return "⚠️ ERROR", "Invalid date"

def check_user_access(user_id):
    """Check if user has access (trail enabled for all OR specific access)"""
    # If trail is enabled for ALL, everyone has access
    if is_trail_enabled():
        return True, "🌍 Public Trail Access", None
    
    # Check if user has individual access
    user_data = users_ref.child(str(user_id)).get()
    
    if not user_data:
        return False, None, None
    
    expiry = user_data.get('expiry')
    user_type = user_data.get('type', 'unknown')
    
    status, remaining = format_time_remaining(expiry)
    
    if status == "🔴 EXPIRED":
        return False, None, None
    
    return True, user_type, user_data

# Bot handlers
@bot.message_handler(commands=['start'])
def start(message):
    is_admin = message.chat.id in ADMIN_IDS
    trail_status = "🟢 ON (Public Access)" if is_trail_enabled() else "🔴 OFF"
    trial_status = "🟢 ON" if is_trial_enabled() else "🔴 OFF"
    trial_days = get_trial_duration()
    
    if is_admin:
        response = (
            f"🚀 **AlienX Access Control Bot**\n\n"
            f"**👤 User Management:**\n"
            f"• `/add <id> <duration>` - Add premium user\n"
            f"• `/remove <id>` - Remove user\n"
            f"• `/check <id>` - Check user status\n"
            f"• `/users` - View all users\n\n"
            f"**🎯 Trail System (File Access):**\n"
            f"• `/trailon` - Enable access for EVERYONE\n"
            f"• `/trailoff` - Disable public access\n"
            f"• `/givetrail <id>` - Give trail to specific user\n"
            f"• `/removetrail <id>` - Remove trail access\n\n"
            f"**🎫 Trial System (Time-Limited):**\n"
            f"• `/trialon` - Enable trial requests\n"
            f"• `/trialoff` - Disable trial requests\n"
            f"• `/trialdays <days>` - Set trial duration\n\n"
            f"**📊 Statistics:**\n"
            f"• `/stats` - View bot statistics\n\n"
            f"🎯 Trail (Public): {trail_status}\n"
            f"🎫 Trial System: {trial_status}\n"
            f"⏰ Trial Duration: {trial_days} days\n\n"
            f"👥 Owners: @aurenkai | @alienxsexy"
        )
    else:
        response = (
            f"🚀 **AlienX Access Control Bot**\n\n"
            f"**Available Commands:**\n"
            f"• `/trial` - Request trial access\n"
            f"• `/check` - Check your access status\n\n"
            f"🎯 Trail (Public): {trail_status}\n"
            f"🎫 Trial System: {trial_status}\n"
            f"⏰ Trial Duration: {trial_days} days\n\n"
            f"👥 Contact: @aurenkai | @alienxsexy"
        )
    
    bot.reply_to(message, response, parse_mode="Markdown")

@bot.message_handler(commands=['add'])
def add_user(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return

    try:
        parts = message.text.split()
        if len(parts) != 3:
            raise ValueError("Invalid format")
        
        user_id = parts[1]
        duration_str = parts[2]
        
        duration_delta = parse_duration(duration_str)
        if not duration_delta:
            raise ValueError("Invalid duration")
        
        expiration = datetime.now() + duration_delta

        users_ref.child(user_id).set({
            'expiry': expiration.strftime("%Y-%m-%d %H:%M:%S"),
            'created': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'type': 'premium',
            'added_by': message.from_user.username or message.from_user.id
        })
        
        bot.reply_to(
            message,
            f"✅ **User Added Successfully!**\n\n"
            f"👤 User ID: `{user_id}`\n"
            f"⏰ Expires: `{expiration.strftime('%Y-%m-%d %H:%M')}`\n"
            f"📅 Duration: {duration_str}\n"
            f"🎫 Type: Premium",
            parse_mode="Markdown"
        )
    except:
        bot.reply_to(
            message,
            "**Format:** `/add <id> <duration>`\n\n"
            "**Examples:**\n"
            "• `/add john123 30d` (30 days)\n"
            "• `/add user456 12h` (12 hours)\n"
            "• `/add pro789 6m` (6 months)",
            parse_mode="Markdown"
        )

@bot.message_handler(commands=['remove'])
def remove_user(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return

    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError("Invalid format")
        
        user_id = parts[1]
        
        if users_ref.child(user_id).get():
            users_ref.child(user_id).delete()
            bot.reply_to(message, f"✅ User `{user_id}` removed successfully.", parse_mode="Markdown")
        else:
            bot.reply_to(message, f"❌ User `{user_id}` not found.")
    except:
        bot.reply_to(message, "**Usage:** `/remove <id>`", parse_mode="Markdown")

@bot.message_handler(commands=['trial'])
def request_trial(message):
    # User requesting trial
    if not is_trial_enabled():
        bot.reply_to(
            message,
            "❌ Trial system is currently disabled.\n\n"
            "👥 Contact: @aurenkai | @alienxsexy"
        )
        return
    
    user_id = str(message.from_user.id)
    existing_user = users_ref.child(user_id).get()
    
    if existing_user:
        bot.reply_to(
            message,
            "⚠️ **You already have access!**\n\n"
            "Use `/check` to view your status.\n\n"
            "👥 Contact: @aurenkai | @alienxsexy",
            parse_mode="Markdown"
        )
        return
    
    trial_days = get_trial_duration()
    expiration = datetime.now() + timedelta(days=trial_days)
    
    users_ref.child(user_id).set({
        'expiry': expiration.strftime("%Y-%m-%d %H:%M:%S"),
        'created': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'type': 'trial',
        'telegram_id': message.from_user.id,
        'username': message.from_user.username or 'N/A',
        'first_name': message.from_user.first_name or 'N/A'
    })
    
    bot.reply_to(
        message,
        f"🎉 **Trial Access Granted!**\n\n"
        f"👤 Your ID: `{user_id}`\n"
        f"⏰ Expires: `{expiration.strftime('%Y-%m-%d %H:%M')}`\n"
        f"📅 Duration: {trial_days} days\n\n"
        f"Enjoy your trial! 🚀\n\n"
        f"👥 Owners: @aurenkai | @alienxsexy",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['trailon'])
def trail_on(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return
    
    settings_ref.child('trail_enabled').set(True)
    bot.reply_to(
        message,
        "✅ **Trail Access Enabled for EVERYONE!** 🌍\n\n"
        "All users now have file access regardless of individual status.",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['trailoff'])
def trail_off(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return
    
    settings_ref.child('trail_enabled').set(False)
    bot.reply_to(
        message,
        "🔴 **Public Trail Access Disabled**\n\n"
        "Only users with individual access can use files now.",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['givetrail'])
def give_trail(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            raise ValueError("Invalid format")
        
        user_id = parts[1]
        
        # Optional: specify duration, default to permanent (100 years)
        if len(parts) == 3:
            duration_str = parts[2]
            duration_delta = parse_duration(duration_str)
            if not duration_delta:
                raise ValueError("Invalid duration")
        else:
            duration_delta = timedelta(days=36500)  # 100 years = permanent
        
        existing_user = users_ref.child(user_id).get()
        
        if existing_user and existing_user.get('type') in ['premium', 'trail']:
            bot.reply_to(
                message,
                f"⚠️ User `{user_id}` already has access!\n\n"
                f"Type: {existing_user.get('type')}\n"
                f"Use `/check {user_id}` to view status.",
                parse_mode="Markdown"
            )
            return
        
        expiration = datetime.now() + duration_delta
        
        users_ref.child(user_id).set({
            'expiry': expiration.strftime("%Y-%m-%d %H:%M:%S"),
            'created': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'type': 'trail',
            'given_by': message.from_user.username or message.from_user.id
        })
        
        duration_text = parts[2] if len(parts) == 3 else "Permanent"
        
        bot.reply_to(
            message,
            f"✅ **Trail Access Granted!**\n\n"
            f"👤 User ID: `{user_id}`\n"
            f"⏰ Expires: `{expiration.strftime('%Y-%m-%d %H:%M')}`\n"
            f"📅 Duration: {duration_text}\n"
            f"🎯 Type: Trail (Individual Access)",
            parse_mode="Markdown"
        )
    except:
        bot.reply_to(
            message,
            "**Usage:** `/givetrail <id> [duration]`\n\n"
            "**Examples:**\n"
            "• `/givetrail user123` (permanent)\n"
            "• `/givetrail user456 30d` (30 days)\n"
            "• `/givetrail user789 6m` (6 months)",
            parse_mode="Markdown"
        )

@bot.message_handler(commands=['removetrail'])
def remove_trail(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError("Invalid format")
        
        user_id = parts[1]
        user_data = users_ref.child(user_id).get()
        
        if not user_data:
            bot.reply_to(message, f"❌ User `{user_id}` not found.", parse_mode="Markdown")
            return
        
        if user_data.get('type') != 'trail':
            bot.reply_to(
                message,
                f"⚠️ User `{user_id}` is not a trail user.\n"
                f"Type: {user_data.get('type', 'unknown')}",
                parse_mode="Markdown"
            )
            return
        
        users_ref.child(user_id).delete()
        bot.reply_to(message, f"✅ Trail access removed for `{user_id}`", parse_mode="Markdown")
    except:
        bot.reply_to(message, "**Usage:** `/removetrail <id>`", parse_mode="Markdown")

@bot.message_handler(commands=['trialon'])
def trial_on(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return
    
    settings_ref.child('trial_enabled').set(True)
    bot.reply_to(message, "✅ Trial request system **ENABLED** 🟢", parse_mode="Markdown")

@bot.message_handler(commands=['trialoff'])
def trial_off(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return
    
    settings_ref.child('trial_enabled').set(False)
    bot.reply_to(message, "🔴 Trial request system **DISABLED**", parse_mode="Markdown")

@bot.message_handler(commands=['trialdays'])
def set_trial_days(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError("Invalid format")
        
        days = int(parts[1])
        
        if days < 1 or days > 365:
            bot.reply_to(message, "⚠️ Days must be between 1 and 365")
            return
        
        settings_ref.child('trial_duration').set(days)
        bot.reply_to(
            message,
            f"✅ Trial duration set to **{days} days**",
            parse_mode="Markdown"
        )
    except:
        bot.reply_to(
            message,
            "**Usage:** `/trialdays <number>`\n"
            "**Example:** `/trialdays 7`",
            parse_mode="Markdown"
        )

@bot.message_handler(commands=['check'])
def check_access(message):
    try:
        parts = message.text.split()
        
        if len(parts) == 1:
            # Check own access
            user_id = str(message.from_user.id)
        else:
            user_id = parts[1]
        
        has_access, access_type, user_data = check_user_access(user_id)
        
        if not has_access:
            bot.reply_to(
                message,
                f"❌ **No Access Found**\n\n"
                f"👤 User: `{user_id}`\n\n"
                f"Use `/trial` to request trial access.\n\n"
                f"👥 Contact: @aurenkai | @alienxsexy",
                parse_mode="Markdown"
            )
            return
        
        # If trail is enabled for all
        if access_type == "🌍 Public Trail Access":
            bot.reply_to(
                message,
                f"✅ **Access Status**\n\n"
                f"👤 User: `{user_id}`\n"
                f"🌍 Status: **PUBLIC TRAIL ACCESS**\n"
                f"🟢 Access: **ACTIVE**\n\n"
                f"Trail is enabled for everyone! 🎉",
                parse_mode="Markdown"
            )
            return
        
        # Individual access
        expiry = user_data.get('expiry')
        created = user_data.get('created', 'Unknown')
        status, remaining = format_time_remaining(expiry)
        
        type_emoji = {
            'premium': '👑',
            'trial': '🎫',
            'trail': '🎯'
        }.get(access_type, '❓')
        
        bot.reply_to(
            message,
            f"📊 **Access Status**\n\n"
            f"👤 User: `{user_id}`\n"
            f"{type_emoji} Type: {access_type.upper()}\n"
            f"📍 Status: {status}\n"
            f"⏰ Expires: `{expiry}`\n"
            f"⏳ Remaining: {remaining}\n"
            f"📅 Created: `{created}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['users'])
def list_users(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return

    try:
        all_users = users_ref.get()
        trail_enabled = is_trail_enabled()
        
        response = "📋 **User List**\n\n"
        
        if trail_enabled:
            response += "🌍 **PUBLIC TRAIL: ENABLED**\n"
            response += "_Everyone has file access!_\n\n"
        
        if not all_users:
            response += "📂 No individual users registered."
            bot.reply_to(message, response, parse_mode="Markdown")
            return
        
        premium_users = []
        trial_users = []
        trail_users = []
        expired_users = []
        
        for user_id, user_data in all_users.items():
            expiry = user_data.get('expiry', 'Unknown')
            user_type = user_data.get('type', 'unknown')
            
            status, remaining = format_time_remaining(expiry)
            
            if status == "🔴 EXPIRED":
                expired_users.append(f"❌ `{user_id}` - Expired")
            else:
                user_str = f"{status} `{user_id}` - {remaining}"
                
                if user_type == 'premium':
                    premium_users.append(user_str)
                elif user_type == 'trail':
                    trail_users.append(user_str)
                else:
                    trial_users.append(user_str)
        
        if premium_users:
            response += "**👑 Premium Users:**\n" + "\n".join(premium_users[:10]) + "\n\n"
        
        if trail_users:
            response += "**🎯 Trail Users (Individual):**\n" + "\n".join(trail_users[:10]) + "\n\n"
        
        if trial_users:
            response += "**🎫 Trial Users:**\n" + "\n".join(trial_users[:10]) + "\n\n"
        
        if expired_users:
            response += "**🔴 Expired:**\n" + "\n".join(expired_users[:5]) + "\n\n"
        
        response += f"**Total:** {len(all_users)} individual users"
        
        if len(premium_users) > 10 or len(trial_users) > 10:
            response += "\n\n_Showing first 10 of each category_"
        
        bot.reply_to(message, response, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if message.chat.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Not authorized.")
        return
    
    try:
        all_users = users_ref.get()
        trail_enabled = is_trail_enabled()
        
        response = "📊 **Bot Statistics**\n\n"
        
        if trail_enabled:
            response += "🌍 **PUBLIC TRAIL: ACTIVE**\n"
            response += "_All users have file access!_\n\n"
        
        if not all_users:
            response += "📂 No individual users registered.\n\n"
        else:
            total = len(all_users)
            active = 0
            expired = 0
            premium = 0
            trial = 0
            trail = 0
            
            for user_id, user_data in all_users.items():
                expiry = user_data.get('expiry', 'Unknown')
                user_type = user_data.get('type', 'unknown')
                
                status, _ = format_time_remaining(expiry)
                
                if status == "🔴 EXPIRED":
                    expired += 1
                else:
                    active += 1
                    if user_type == 'premium':
                        premium += 1
                    elif user_type == 'trail':
                        trail += 1
                    else:
                        trial += 1
            
            response += (
                f"**Individual Users:**\n"
                f"👥 Total: {total}\n"
                f"🟢 Active: {active}\n"
                f"🔴 Expired: {expired}\n\n"
                f"**User Types:**\n"
                f"👑 Premium: {premium}\n"
                f"🎯 Trail: {trail}\n"
                f"🎫 Trial: {trial}\n\n"
            )
        
        trial_status = "🟢 Enabled" if is_trial_enabled() else "🔴 Disabled"
        trial_days = get_trial_duration()
        
        response += (
            f"**Systems:**\n"
            f"🎯 Public Trail: {'🟢 ON' if trail_enabled else '🔴 OFF'}\n"
            f"🎫 Trial Requests: {trial_status}\n"
            f"⏰ Trial Duration: {trial_days} days\n\n"
            f"👥 Owners: @aurenkai | @alienxsexy"
        )
        
        bot.reply_to(message, response, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_all(message):
    bot.reply_to(
        message,
        "⚠️ Unknown command. Use /start to see available commands.\n\n"
        "👥 Contact: @aurenkai | @alienxsexy"
    )

def start_bot_polling():
    """Start bot with retry logic"""
    while True:
        try:
            print("🤖 Starting bot polling...")
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
            print("🔄 Restarting in 15 seconds...")
            time.sleep(15)

if __name__ == "__main__":
    print("🚀 AlienX Bot Started on Render!")
    print("👥 Owners: @aurenkai | @alienxsexy")
    
    # Delete any existing webhook first
    try:
        bot.remove_webhook()
        print("✅ Webhook removed")
    except:
        pass
    
    # Start Flask server in background thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("✅ Flask server started on port 10000")
    
    # Wait a bit for Flask to start
    time.sleep(2)
    
    # Start bot polling with retry logic
    start_bot_polling()
