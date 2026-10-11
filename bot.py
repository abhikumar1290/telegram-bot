import os
import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Logging Setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN =("8488142985:AAEdAaKMMcwfePB7yYcTpFQHKgngsknGDmc") 
CHANNEL_ID = -1004306101830  # Aapke Private Channel ki ID

# Database Setup
def init_db():
    conn = sqlite3.connect("bot_media.db")
    cursor = conn.cursor()
    
    # Media Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT UNIQUE,
            media_type TEXT, -- 'photo', 'short_video', 'full_video'
            duration INTEGER DEFAULT 0
        )
    """)
    
    # User Daily Usage Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_limits (
            user_id INTEGER PRIMARY KEY,
            photos_count INTEGER DEFAULT 0,
            short_videos_count INTEGER DEFAULT 0,
            full_videos_count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

# Main UI Menu
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("📸 Free Photos (100 Limit)", callback_data="get_photo")],
        [InlineKeyboardButton("⚡ Short Videos (50 Limit)", callback_data="get_short_video")],
        [InlineKeyboardButton("🎬 Full Videos (7 Limit)", callback_data="get_full_video")]
    ]
    return InlineKeyboardMarkup(keyboard)

# /start Command Handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    text = (
        f"👋 Welcome to Media Bot, {user_name}!\n\n"
        "Aapko rozana milta hai:\n"
        "📸 100 Free Photos / Day\n"
        "⚡ 50 Short Videos (≤10s) / Day\n"
        "🎬 7 Full Videos (>10s) / Day\n\n"
        "Niche diye gaye options me se chuniye:"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=get_main_menu())
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=get_main_menu())

# Channel Post Handler (Automatically stores Media File IDs)
async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post
    if not post or post.chat.id != CHANNEL_ID:
        return

    conn = sqlite3.connect("bot_media.db")
    cursor = conn.cursor()

    # Photo Upload
    if post.photo:
        file_id = post.photo[-1].file_id
        cursor.execute("INSERT OR IGNORE INTO media (file_id, media_type) VALUES (?, 'photo')", (file_id,))
        logger.info(f"Saved Photo: {file_id}")

    # Video Upload (Short vs Full Filter)
    elif post.video:
        file_id = post.video.file_id
        duration = post.video.duration or 0
        media_type = "short_video" if duration <= 10 else "full_video"
        
        cursor.execute("INSERT OR IGNORE INTO media (file_id, media_type, duration) VALUES (?, ?, ?)", 
                       (file_id, media_type, duration))
        logger.info(f"Saved Video ({media_type}): {file_id}")

    conn.commit()
    conn.close()

# Button Click / Media Retrieval Handler
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    media_type = None
    if query.data == "get_photo":
        media_type = "photo"
    elif query.data == "get_short_video":
        media_type = "short_video"
    elif query.data == "get_full_video":
        media_type = "full_video"

    if media_type:
        conn = sqlite3.connect("bot_media.db")
        cursor = conn.cursor()
        
        # Get random media item from DB
        cursor.execute("SELECT file_id FROM media WHERE media_type = ? ORDER BY RANDOM() LIMIT 1", (media_type,))
        row = cursor.fetchone()
        conn.close()

        if row:
            file_id = row[0]
            if media_type == "photo":
                await query.message.reply_photo(photo=file_id, caption="Here is your Photo 📸", reply_markup=get_main_menu())
            else:
                await query.message.reply_video(video=file_id, caption="Here is your Video 🎬", reply_markup=get_main_menu())
        else:
            msg = "Abhi database mein koi photo nahi hai!" if media_type == "photo" else f"Abhi database mein koi {media_type.replace('_', ' ')} nahi hai!"
            await query.message.reply_text(msg, reply_markup=get_main_menu())

def main():
    init_db()
    
    app = Application.builder().token(TOKEN).build()

    # Command & Callback Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))

    # Channel Handler (Saves new photos/videos automatically from channel)
    app.add_handler(MessageHandler(filters.Chat(CHANNEL_ID) & (filters.PHOTO | filters.VIDEO), channel_post_handler))

    logger.info("Bot started successfully...")
    
    # Clean Polling call for python-telegram-bot v20+
    app.run_polling(poll_interval=1.0)

if __name__ == "__main__":
    main()
