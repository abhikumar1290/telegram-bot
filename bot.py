import logging
import random
import sqlite3
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Logging Setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Bot Configuration
TOKEN = "8488142985:AAEdAaKMMcwfePB7yYcTpFQHKgngsknGDmc"
YOUR_UPI_ID = "varshneyrishabh@fam"
QR_FILE_ID = "YOUR_QR_CODE_FILE_ID_HERE"

# Database Setup
def init_db():
    conn = sqlite3.connect('bot_user_data.db')
    cursor = conn.cursor()
    # Daily usage tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage (
            user_id INTEGER,
            usage_date TEXT,
            video_count INTEGER DEFAULT 0,
            photo_count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, usage_date)
        )
    ''')
    # Media storage database
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT UNIQUE,
            media_type TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_media(file_id, media_type):
    conn = sqlite3.connect('bot_user_data.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO media (file_id, media_type) VALUES (?, ?)", (file_id, media_type))
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Duplicate file_id ignore ho jayega
    conn.close()

def get_random_media(media_type):
    conn = sqlite3.connect('bot_user_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT file_id FROM media WHERE media_type = ? ORDER BY RANDOM() LIMIT 1", (media_type,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_usage(user_id):
    today = str(date.today())
    conn = sqlite3.connect('bot_user_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT video_count, photo_count FROM usage WHERE user_id = ? AND usage_date = ?", (user_id, today))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO usage (user_id, usage_date, video_count, photo_count) VALUES (?, ?, 0, 0)", (user_id, today))
        conn.commit()
        conn.close()
        return 0, 0
    conn.close()
    return row[0], row[1]

def increment_usage(user_id, content_type):
    today = str(date.today())
    get_usage(user_id)
    conn = sqlite3.connect('bot_user_data.db')
    cursor = conn.cursor()
    if content_type == 'video':
        cursor.execute("UPDATE usage SET video_count = video_count + 1 WHERE user_id = ? AND usage_date = ?", (user_id, today))
    elif content_type == 'photo':
        cursor.execute("UPDATE usage SET photo_count = photo_count + 1 WHERE user_id = ? AND usage_date = ?", (user_id, today))
    conn.commit()
    conn.close()

# Admin Auto-Media Save Handler
async def handle_admin_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    
    if msg.video:
        file_id = msg.video.file_id
        save_media(file_id, 'video')
        await msg.reply_text("✅ Video database mein save ho gayi!")
    elif msg.photo:
        file_id = msg.photo[-1].file_id
        save_media(file_id, 'photo')
        await msg.reply_text("✅ Photo database mein save ho gayi!")

# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 **Welcome to Premium Media Bot!**\n\n"
        "Aapko rozana milta hai:\n"
        "📸 **100 Free Photos / Day**\n"
        "🎬 **7 Free Videos / Day**\n\n"
        "Niche diye gaye options me se chuniye:"
    )
    keyboard = [
        [InlineKeyboardButton("📸 Free Photos (100 Limit)", callback_data='menu_photo')],
        [InlineKeyboardButton("🎬 Free Videos (7 Limit)", callback_data='menu_video')],
        [InlineKeyboardButton("💎 Buy Premium Access", callback_data='show_plans')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)

# Show Premium Plans
async def send_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    plan_text = (
        "💎 **UPGRADE TO PREMIUM ACCESS** 💎\n\n"
        "✨ Unlimited Photos & Videos\n"
        "⚡ Fast Speed Download\n"
        "🚫 No Daily Limits\n\n"
        "👇 **Choose Your Plan:**"
    )
    keyboard = [
        [InlineKeyboardButton("⚡ 2 Days — ₹2", callback_data='pay_2')],
        [InlineKeyboardButton("🔥 15 Days — ₹15 (50% OFF)", callback_data='pay_15')],
        [InlineKeyboardButton("🏆 2 Months — ₹60", callback_data='pay_60')],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text(plan_text, parse_mode='Markdown', reply_markup=reply_markup)

# Send Payment Details
async def send_payment_qr(update: Update, amount: str, plan_name: str):
    query = update.callback_query
    caption_text = (
        f"🚨 **PAYMENT FOR {plan_name.upper()}** 🌿\n\n"
        f"💳 **PAYMENT STEPS:**\n"
        f"1️⃣ Pay **{amount}** to UPI ID:\n`{YOUR_UPI_ID}`\n"
        f"2️⃣ QR Code ko scan karke payment karein.\n"
        f"3️⃣ Payment ka screenshot is chat me bhejein.\n\n"
        f"⚡ Fast Activation Instant!"
    )
    keyboard = [[InlineKeyboardButton("✅ Verify / Screenshot Bhejein", callback_data='verify_pay')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.message.reply_photo(photo=QR_FILE_ID, caption=caption_text, parse_mode='Markdown', reply_markup=reply_markup)
    except Exception:
        await query.message.reply_text(caption_text, parse_mode='Markdown', reply_markup=reply_markup)

# Callback Handler
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    v_count, p_count = get_usage(user_id)

    if query.data == 'menu_video':
        if v_count >= 7:
            await query.message.reply_text(
                "🚫 **Daily Video Limit Reached! (7/7)**\n\n"
                "Aapki aaj ki 7 free videos ki limit khatam ho chuki hai.\n"
                "Aage dekhne ke liye Premium membership lein!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 Buy Premium", callback_data='show_plans')]])
            )
        else:
            video_file_id = get_random_media('video')
            if not video_file_id:
                await query.message.reply_text("Abhi database mein koi video nahi hai. Admin ko videos upload karne dein!")
                return

            increment_usage(user_id, 'video')
            keyboard = [[InlineKeyboardButton("▶️ Next Video 🍿", callback_data='menu_video')]]
            await query.message.reply_video(
                video=video_file_id,
                caption=f"Enjoy your video! 🍿\n(Today's Used: {v_count + 1}/7)",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif query.data == 'menu_photo':
        if p_count >= 100:
            await query.message.reply_text(
                "🚫 **Daily Photo Limit Reached! (100/100)**\n\n"
                "Aapki aaj ki 100 free photos ki limit khatam ho chuki hai.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 Buy Premium", callback_data='show_plans')]])
            )
        else:
            photo_file_id = get_random_media('photo')
            if not photo_file_id:
                await query.message.reply_text("Abhi database mein koi photo nahi hai. Admin ko photos upload karne dein!")
                return

            increment_usage(user_id, 'photo')
            keyboard = [[InlineKeyboardButton("🖼️ Next Photo 📸", callback_data='menu_photo')]]
            await query.message.reply_photo(
                photo=photo_file_id,
                caption=f"Here is your photo! 📸\n(Today's Used: {p_count + 1}/100)",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    elif query.data == 'show_plans':
        await send_plans(update, context)

    elif query.data == 'pay_2':
        await send_payment_qr(update, "₹2", "2 Days Plan")
    elif query.data == 'pay_15':
        await send_payment_qr(update, "₹15", "15 Days Plan")
    elif query.data == 'pay_60':
        await send_payment_qr(update, "₹60", "2 Months Plan")
    elif query.data == 'verify_pay':
        await query.message.reply_text("📸 Kripya payment ka screenshot is chat me bhejein. Admin verification ke baad aapka plan active kar diya jayega!")
    elif query.data == 'main_menu':
        await start(update, context)

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    
    # Media Forward Handler
    app.add_handler(MessageHandler(filters.VIDEO | filters.PHOTO, handle_admin_media))

    print("Bot chalu ho gaya hai...")
    app.run_polling()

if __name__ == "__main__":
    main()