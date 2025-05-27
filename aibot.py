import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.ext import JobQueue
from telegram import ReplyKeyboardMarkup
from telegram.ext import CallbackContext
import datetime
import random
import asyncio  # Needed for async delays
import requests
import os
from datetime import time
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

from dotenv import load_dotenv
load_dotenv()


# Replace with your Bot API Token from BotFather
TOKEN = os.getenv("TOKEN")

# Admin ID (Replace with your own Telegram ID to receive withdrawal requests)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Replace this with your Telegram user ID



# Initialize bot application
app = Application.builder().token(TOKEN).build()

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


# ✅ Connect to PostgreSQL (Railway)
conn = psycopg2.connect(
    DATABASE_URL,
    cursor_factory=RealDictCursor
)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS pending_testimonies (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    file_id TEXT,
    caption TEXT,
    username TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS testimonies (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    file_id TEXT,
    caption TEXT,
    username TEXT
)
""")

conn.commit()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS prediction_users (
        user_id BIGINT PRIMARY KEY,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()


# Logging setup
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id

    # Save user to prediction_users if not already there
    cursor.execute("INSERT INTO prediction_users (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
    conn.commit()
     
    keyboard = [
        [InlineKeyboardButton("📢 Join Our Community", url="https://t.me/cooziepicksAI")],
        [InlineKeyboardButton("💎 Get Premium Prediction", callback_data="whatsapp_task")],
        [InlineKeyboardButton("📸 Testimonies from Community", callback_data="view_testimonies")],
        [InlineKeyboardButton("🎯 Today’s Pick", callback_data="deposit_now")],
        [InlineKeyboardButton("🤖 AI Daily Picks", callback_data="get_vip")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

# Persistent keyboard
    persistent_keyboard = ReplyKeyboardMarkup(
        [["💎 Get Prediction", "📸 Testimonies"],
         ["🤖 AI Picks", "🎯 Today’s Pick"]],
        resize_keyboard=True, one_time_keyboard=False
    )

    await update.message.reply_text(
        f"Welcome to CooziePicks! \n\nYour #1 home for premium football predictions, expert AI picks, daily tips, and real earnings through engaging tasks. Join now and win smarter!",
        reply_markup=reply_markup
    )

    await update.message.reply_text(
        "Choose an Option",
        reply_markup=persistent_keyboard
    )

app.add_handler(CommandHandler("start", start))

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes


async def won_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to send this message.")
        return

    message_text = "🎉 *Game WON!*\n\nIf you won, share your testimony below to inspire others!"
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 Upload Your Testimony", callback_data="upload_testimony")]
    ])

    # Get all users
    cursor.execute("SELECT user_id FROM prediction_users")
    users = cursor.fetchall()

    # Send messages concurrently
    async def send_to_user(user_id):
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Failed to send to {user_id}: {e}")

    tasks = [send_to_user(user["user_id"]) for user in users]
    await asyncio.gather(*tasks)

    await update.message.reply_text("✅ Broadcast sent to all users.")

# Register the command
app.add_handler(CommandHandler("won", won_command))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes

# When user taps the "Upload Testimony" button
async def upload_testimony_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    context.user_data[f"uploading_testimony_{user_id}"] = True

    await query.message.reply_text("📸 Please send the image and add a caption(Optional) you'd like to upload as your testimony.")

app.add_handler(CallbackQueryHandler(upload_testimony_prompt, pattern="^upload_testimony$"))


from telegram.ext import MessageHandler, filters

async def handle_uploaded_testimony(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Check if the user is in upload mode
    if not context.user_data.get(f"uploading_testimony_{user_id}"):
        return  # Ignore if not part of upload flow

    photo = update.message.photo[-1]
    file_id = photo.file_id
    caption = update.message.caption or ""
    username = update.effective_user.username or ""

    # Save to pending_testimonies
    cursor.execute("""
        INSERT INTO pending_testimonies (user_id, file_id, caption, username)
        VALUES (%s, %s, %s, %s)
    """, (user_id, file_id, caption, username))
    conn.commit()

    # Notify user
    await update.message.reply_text("✅ Testimony submitted! Awaiting admin approval.")

    # Notify admin
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=file_id,
        caption=f"📝 *New Testimony Pending Approval*\nFrom: @{username}\n\nReview: {caption}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_testimony_{user_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_testimony_{user_id}")
            ]
        ])
    )

    # Reset the flag
    context.user_data[f"uploading_testimony_{user_id}"] = False

# Register the photo handler
app.add_handler(MessageHandler(filters.PHOTO, handle_uploaded_testimony))

CHANNEL_ID = -1002565085815  # Replace with your actual channel ID


async def handle_testimony_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split("_")[0], int(query.data.split("_")[2])

    # Get testimony
    cursor.execute("SELECT * FROM pending_testimonies WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()

    if not row:
        await query.edit_message_text("❌ Testimony not found or already handled.")
        return

    if "approve" in query.data:
        # Save to approved table
        cursor.execute("""
            INSERT INTO testimonies (user_id, file_id, caption, username)
            VALUES (%s, %s, %s, %s)
        """, (user_id, row["file_id"], row["caption"], row["username"]))
        conn.commit()
         
        # Send to channel
        caption = f"🧾 *Testimony from Anonymous*\n\n{row['caption'] or ''}"

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 Get Today’s Games", url="https://t.me/CoozieAIbot")]
        ])
        
        try:
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=row["file_id"],
                caption=caption,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"❌ Failed to send to channel: {e}")

        await query.edit_message_caption("✅ Testimony approved and published.")
    else:
        await query.edit_message_caption("❌ Testimony rejected.")

    # Remove from pending
    cursor.execute("DELETE FROM pending_testimonies WHERE user_id = %s", (user_id,))
    conn.commit()

app.add_handler(CallbackQueryHandler(handle_testimony_approval, pattern="^(approve_testimony|reject_testimony)_"))

async def view_testimonies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    cursor.execute("""
        SELECT file_id, caption FROM testimonies
        ORDER BY id DESC LIMIT 10
    """)
    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("📭 No testimonies available yet.")
        return

    for row in rows:
        caption = f"🧾 *Testimony from Anonymous*\n\n{row['caption'] or ''}"
        try:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=row["file_id"],
                caption=caption,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Failed to send testimony: {e}")

app.add_handler(CallbackQueryHandler("view_testimonies", pattern="^view_testimonies$"))


if __name__ == "__main__":
    app.run_polling()