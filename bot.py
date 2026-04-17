import telebot
from telebot import types
import os
import random
import threading
import time
from flask import Flask

# --- CONFIG ---
API_TOKEN = '8681343917:AAFeqQZT8x_0KN8htB0efWSBWMF6Mo2cUcQ'
ADMIN_ID = 7776219392
OTP_LINK = "https://t.me/sfcoreoay"
DB_FILE = "numbers_db.txt"

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# --- GLOBAL VARIABLES ---
REFRESH_COOLDOWN = 5  # Default 5 seconds
last_refresh_time = {}

# --- WEB SERVER FOR RENDER ---
@app.route('/')
def index():
    return "Bot is Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# --- DATABASE FUNCTIONS ---
def load_db():
    data = {}
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                parts = line.strip().split("|")
                if len(parts) >= 3:
                    country, emoji, numbers_str = parts[0], parts[1], parts[2]
                    num_list = [n.strip() for n in numbers_str.split(',') if n.strip()]
                    if num_list:
                        data[country] = {'emoji': emoji, 'numbers': num_list}
    return data

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        for country, info in data.items():
            if info['numbers']:
                numbers_str = ",".join(info['numbers'])
                f.write(f"{country}|{info['emoji']}|{numbers_str}\n")

# --- UI LAYOUTS ---
def get_user_menu(db):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(f"{info['emoji']} {name}", callback_data=f"get_{name}") 
               for name, info in db.items()]
    markup.add(*buttons)
    return markup

def get_number_layout(country):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔄 Refresh", callback_data=f"get_{country}"),
        types.InlineKeyboardButton("🌍 Change Country", callback_data="main_menu"),
        types.InlineKeyboardButton("📲 View OTP", url=OTP_LINK)
    )
    return markup

# --- HANDLERS ---

@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id == ADMIN_ID:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ ADD NUMBERS", callback_data="add_num"),
            types.InlineKeyboardButton("🗑️ DELETE COUNTRY", callback_data="del_num"),
            types.InlineKeyboardButton("⏳ SET REFRESH TIMER", callback_data="set_timer")
        )
        bot.send_message(message.chat.id, "🛠 **Admin Panel**", reply_markup=markup, parse_mode="Markdown")
    else:
        db = load_db()
        bot.send_message(message.chat.id, "✨ **Select a Country**", reply_markup=get_user_menu(db))

@bot.message_handler(commands=['cap'])
def cap_command(message):
    db = load_db()
    if not db:
        bot.send_message(message.chat.id, "❌ Stock empty!")
        return
    
    grand_total = sum(len(info['numbers']) for info in db.values())
    text = "🌍 **Available Countries:**\n\n"
    for country, info in db.items():
        count = len(info['numbers'])
        text += f"   {info['emoji']} {country} → {count} numbers\n"
    text += f"\n📊 **Grand Total: {grand_total} numbers available**"
    bot.send_message(message.chat.id, text, reply_markup=get_user_menu(db), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("get_"))
def show_numbers(call):
    user_id = call.from_user.id
    current_time = time.time()
    
    # Timer Check
    if user_id in last_refresh_time:
        elapsed = current_time - last_refresh_time[user_id]
        if elapsed < REFRESH_COOLDOWN:
            wait_time = int(REFRESH_COOLDOWN - elapsed)
            bot.answer_callback_query(call.id, f"⏳ Wait {wait_time}s before refresh!", show_alert=True)
            return

    country = call.data.replace("get_", "")
    db = load_db()
    
    if country in db and db[country]['numbers']:
        # Ekta number random select kora ebong remove kora
        num = random.choice(db[country]['numbers'])
        db[country]['numbers'].remove(num)
        save_db(db) # Database update (permanent removal)
        
        last_refresh_time[user_id] = current_time # Timer update
        
        emoji = db[country]['emoji']
        msg_text = f"📍 **Country:** {country} {emoji}\n\n"
        msg_text += "👇 **Click on the number to copy:**\n\n"
        msg_text += f"📋 `{num}`\n\n"
        msg_text += f"⚠️ *This number is removed from stock and won't be shown again.*"
            
        bot.edit_message_text(msg_text, call.message.chat.id, call.message.message_id, 
                              reply_markup=get_number_layout(country), 
                              parse_mode="Markdown")
    else:
        bot.answer_callback_query(call.id, "⚠️ No more numbers left in stock!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_home(call):
    db = load_db()
    bot.edit_message_text("✨ **Select a Country**", call.message.chat.id, call.message.message_id, 
                          reply_markup=get_user_menu(db))

# --- ADMIN PROCESS ---

@bot.callback_query_handler(func=lambda call: call.data == "set_timer")
def admin_timer(call):
    msg = bot.send_message(call.message.chat.id, "⏱ **Enter timer in seconds (e.g., 5):**")
    bot.register_next_step_handler(msg, process_timer)

def process_timer(message):
    global REFRESH_COOLDOWN
    try:
        REFRESH_COOLDOWN = int(message.text)
        bot.send_message(message.chat.id, f"✅ Refresh Timer set to **{REFRESH_COOLDOWN} seconds**.")
    except:
        bot.send_message(message.chat.id, "❌ Invalid number. Please enter only digits.")

@bot.callback_query_handler(func=lambda call: call.data == "add_num")
def admin_add(call):
    msg = bot.send_message(call.message.chat.id, "⌨️ Country Name:")
    bot.register_next_step_handler(msg, lambda m: bot.register_next_step_handler(bot.send_message(m.chat.id, "Emoji:"), step_final, m.text))

def step_final(message, country):
    emoji = message.text
    msg = bot.send_message(message.chat.id, "Send TXT or Paste Numbers:")
    bot.register_next_step_handler(msg, process_numbers, country, emoji)

def process_numbers(message, country, emoji):
    nums = []
    if message.content_type == 'document':
        raw = bot.download_file(bot.get_file(message.document.file_id).file_path).decode('utf-8')
        nums = [l.strip() for l in raw.splitlines() if l.strip()]
    elif message.text:
        nums = [l.strip() for l in message.text.splitlines() if l.strip()]
    
    if nums:
        db = load_db()
        if country in db: db[country]['numbers'].extend(nums)
        else: db[country] = {'emoji': emoji, 'numbers': nums}
        save_db(db)
        bot.send_message(message.chat.id, f"✅ Added {len(nums)} numbers!")

@bot.callback_query_handler(func=lambda call: call.data == "del_num")
def admin_del_menu(call):
    db = load_db()
    markup = types.InlineKeyboardMarkup()
    for n in db.keys(): markup.add(types.InlineKeyboardButton(f"❌ {n}", callback_data=f"del_{n}"))
    bot.send_message(call.message.chat.id, "Select country to delete:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def handle_del(call):
    c = call.data.replace("del_", "")
    db = load_db()
    if c in db:
        del db[c]
        save_db(db)
        bot.send_message(call.message.chat.id, f"🗑️ Deleted {c}.")

# --- START ---
if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    bot.infinity_polling()
