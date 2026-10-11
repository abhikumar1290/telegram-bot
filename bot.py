import logging
import random
import sqlite3
from datetime import date, datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Logging Setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Bot Configuration
TOKEN = "8488142985:AAEdAaKMMcwfePB7yYcTpFQHKgngsknGDmc"
ADMIN_ID = 123456789  # Yahan apni Telegram Admin Numeric ID daalein

# Database Setup
def init_db():
    conn = sqlite3.connect('bot_user_data.db')
    cursor = conn.cursor()
    # Daily usage tracking (Short vs Long videos)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage (
            user_id INTEGER,
            usage_date TEXT,
            short_video_count INTEGER DEFAULT 0,
            long_video_count INTEGER DEFAULT 0,
            photo_count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, usage_date)
        )
    ''')
    # Media storage database with duration
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT UNIQUE,
            media_type TEXT,
            duration INTEGER DEFAULT 0
        )
    ''')
    # Premium Subscriptions database
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS premium (
            user_id INTEGER PRIMARY KEY,
            expiry_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_media(file_id, media_type, duration=0):
    conn = sqlite3.connect('bot_user_data.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO media (file_id, media_type, duration) VALUES (?, ?, ?)", (file_id, media_type, duration))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

def get_random_media(media_type, is_short=False):
    conn = sqlite3.connect('bot_user_data.db')
    cursor = conn.cursor()
    if media_type == 'video':
        if is_short:
            cursor.execute("SELECT file_id FROM media WHERE media_type = 'video' AND duration <= 10 ORDER BY RANDOM() LIMIT 1")
        else:
            cursor.execute("SELECT file_id FROM media WHERE media_type = 'video' AND duration > 10 ORDER BY RANDOM() LIMIT 1")
    else:
        cursor.execute("SELECT file_id FROM media WHERE media_type = 'photo' ORDER BY RANDOM() LIMIT 1")
    
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def is_premium(user_id):
    if user_id == ADMIN_ID:
        return True
    conn = sqlite3.connect('bot_user_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT expiry_date FROM premium WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        expiry_date = datetime.strptime(row[0], '%Y-%m-%d')
        if datetime.now() <= expiry_date:
            return True
    return False

def get_usage(user_id):
    today = str(date.today())
    conn = sqlite3.connect('bot_user_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT short_video_count, long_video_count, photo_count FROM usage WHERE user_id = ? AND usage_date = ?", (user_id, today))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO usage (user_id, usage_date, short_video_count, long_video_count, photo_count) VALUES (?, ?, 0, 0, 0)", (user_id, today))
        conn.commit()
        conn.close()
        return 0, 0, 0
    conn.close()
    return row[0], row[1], row[2]

def increment_usage(user_id, content_type):
    today = str(date.today())
    get_usage(user_id)
    conn = sqlite3.connect('bot_user_data.db')
    cursor = conn.cursor()
    if content_type == 'short_video':
        cursor.execute("UPDATE usage SET short_video_count = short_video_count + 1 WHERE user_id = ? AND usage_date = ?", (user_id, today))
    elif content_type == 'long_video':
        cursor.execute("UPDATE usage SET long_video_count = long_video_count + 1 WHERE user_id = ? AND usage_date = ?", (user_id, today))
    elif content_type == 'photo':
        cursor.execute("UPDATE usage SET photo_count = photo_count + 1 WHERE user_id = ? AND usage_date = ?", (user_id, today))
    conn.commit()
    conn.close()

# Message & Media Handler (Admin saving videos/photos)
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id
    
    if user_id == ADMIN_ID and (msg.video or msg.photo):
        if msg.video:
            duration = msg.video.duration or 0
            save_media(msg.video.file_id, 'video', duration)
            await msg.reply_text(f"✅ Short Video Saved! (Duration: {duration}s)")
        elif msg.photo:
            save_media(msg.photo[-1].file_id, 'photo', 0)
            await msg.reply_text("✅ Photo Saved!")
        return

# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 **Welcome to Media Bot!**\n\n"
        "Aapko rozana milta hai:\n"
        "📸 **100 Free Photos / Day**\n"
        "⚡ **50 Short Videos (≤10s) / Day**\n"
        "🎬 **7 Full Videos (>10s) / Day**\n\n"
        "Niche diye gaye options me se chuniye:"
    )
    keyboard = [
        [InlineKeyboardButton("📸 Free Photos (100 Limit)", callback_data='menu_photo')],
        [InlineKeyboardButton("⚡ Short Videos (50 Limit)", callback_data='menu_short_video')],
        [InlineKeyboardButton("🎬 Full Videos (7 Limit)", callback_data='menu_long_video')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)

# Callback Handler
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    short_v, long_v, p_count = get_usage(user_id)
    user_is_prem = is_premium(user_id)

    # Short Videos (≤10 seconds - Limit 50)
    if data == 'menu_short_video':
        if not user_is_prem and short_v >= 50:
            await query.message.reply_text("🚫 **Daily Short Video Limit Reached! (50/50)**")
        else:
            video_file_id = get_random_media('video', is_short=True)
            if not video_file_id:
                await query.message.reply_text("Abhi database mein koi short video (≤10s) nahi hai!")
                return

            if not user_is_prem:
                increment_usage(user_id, 'short_video')
            
            keyboard = [[InlineKeyboardButton("⚡ Next Short Video 🍿", callback_data='menu_short_video')]]
            cap = "Enjoy short video! 🍿" if user_is_prem else f"Enjoy short video! 🍿\n(Today's Used: {short_v + 1}/50)"
            await query.message.reply_video(video=video_file_id, caption=cap, reply_markup=InlineKeyboardMarkup(keyboard))

    # Full Videos (>10 seconds - Limit 7)
    elif data == 'menu_long_video':
        if not user_is_prem and long_v >= 7:
            await query.message.reply_text("🚫 **Daily Full Video Limit Reached! (7/7)**")
        else:
            video_file_id = get_random_media('video', is_short=False)
            if not video_file_id:
                await query.message.reply_text("Abhi database mein koi full video (>10s) nahi hai!")
                return

            if not user_is_prem:
                increment_usage(user_id, 'long_video')
            
            keyboard = [[InlineKeyboardButton("🎬 Next Full Video 🍿", callback_data='menu_long_video')]]
            cap = "Enjoy full video! 🍿" if user_is_prem else f"Enjoy full video! 🍿\n(Today's Used: {long_v + 1}/7)"
            await query.message.reply_video(video=video_file_id, caption=cap, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'menu_photo':
        if not user_is_prem and p_count >= 100:
            await query.message.reply_text("🚫 **Daily Photo Limit Reached! (100/100)**")
        else:
            photo_file_id = get_random_media('photo')
            if not photo_file_id:
                await query.message.reply_text("Abhi database mein koi photo nahi hai!")
                return

            if not user_is_prem:
                increment_usage(user_id, 'photo')
            
            keyboard = [[InlineKeyboardButton("🖼️ Next Photo 📸", callback_data='menu_photo')]]
            cap = "Here is your photo! 📸" if user_is_prem else f"Here is your photo! 📸\n(Today's Used: {p_count + 1}/100)"
            await query.message.reply_photo(photo=photo_file_id, caption=cap, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'main_menu':
        await start(update, context)

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.VIDEO | filters.PHOTO, handle_messages))

    print("Bot chalu ho gaya hai...")
    app.run_polling(poll_interval=1.0, timeout=30, read_timeout=30, connect_timeout=30)

if __name__ == "__main__":
    main()
