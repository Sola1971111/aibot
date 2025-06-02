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
    CREATE TABLE IF NOT EXISTS paid_predictions (
        id SERIAL PRIMARY KEY,
        user_id BIGINT UNIQUE,
        amount INTEGER,
        duration INTEGER,
        expires_at TIMESTAMP
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

cursor.execute("""
CREATE TABLE IF NOT EXISTS daily_pick (
    id SERIAL PRIMARY KEY,
    image_file_id TEXT,
    date DATE
)
""")
conn.commit()

cursor.execute("""
CREATE TABLE IF NOT EXISTS rollover (
    id SERIAL PRIMARY KEY,
    image_file_id TEXT,
    date DATE
)
""")
conn.commit()

# Logging setup
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    user = update.effective_user
    user_id = user_id
    first_name = user.first_name
     
    # Save user to prediction_users if not already there
    cursor.execute("INSERT INTO prediction_users (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
    conn.commit()
     
    keyboard = [
        [InlineKeyboardButton("📢 Join Our Community", url="https://t.me/cooziepicksAI")],
        [InlineKeyboardButton("💎 Get Premium Prediction", callback_data="subscription")],
        [InlineKeyboardButton("📸 Testimonies from Community", callback_data="view_testimonies")],
        [InlineKeyboardButton("🎯 Today’s Pick", callback_data="view_pick")],
        [InlineKeyboardButton("📈 2 Odds Rollover", callback_data="view_rollover")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

# Persistent keyboard
    persistent_keyboard = ReplyKeyboardMarkup(
        [["💎 Get Prediction", "📸 Testimonies"],
         ["📈 2 Odds Rollover", "🎯 Today’s Pick"]],
        resize_keyboard=True, one_time_keyboard=False
    )

    await update.message.reply_text(
        f"🔥 Welcome to CooziePicks! \n\nYour #1 home for ⚽ premium football predictions, 🤖 expert AI picks, and 📅 daily tips.🎯\n\nWhy thousands trust CooziePicks:\n• 💎 Access VIP football predictions \n• 🤖 Use AI to get smarter betting insights \n• 📈 Boost your wins with our expert-curated picks",
        reply_markup=reply_markup
    )

    await update.message.reply_text(
        "Choose an Option",
        reply_markup=persistent_keyboard
    )

app.add_handler(CommandHandler("start", start))


async def update_bot_description(context: ContextTypes.DEFAULT_TYPE):
    """Updates the bot's profile description with the total user count from PostgreSQL."""
    try:
        cursor.execute("SELECT COUNT(*) FROM prediction_users")
        result = cursor.fetchone()
        total_users = result['count'] if result else 0

        new_description = (
            f"🌍 {total_users} users are using this bot!\n\n"
            "Get AI/Expert predicted football picks"
        )

        await context.bot.set_my_description(new_description)
        print(f"✅ Bot description updated: {new_description}")

    except Exception as e:
        print(f"❌ Failed to update bot description: {e}")

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ContextTypes


async def won_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to send this message.")
        return

    message_text = "🎉 *Today`s Game WON!*\n\nIf you won, share your testimony below to inspire others!"
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
                parse_mode="Markdown",
                reply_markup=reply_markup
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

app.add_handler(CallbackQueryHandler(view_testimonies, pattern="view_testimonies"))


async def view_testimonies_p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

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

app.add_handler(MessageHandler(filters.Text("📸 Testimonies"), view_testimonies_p))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

async def show_subscription_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = update.effective_chat.id

    # ✅ STEP 1: Check for active subscription
    cursor.execute("SELECT expires_at FROM paid_predictions WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()

    if row:
        expires_at = row["expires_at"]
        now = datetime.now()

        if expires_at > now and (expires_at - now).days > 2:
            await query.message.reply_text("✅ You already have an active subscription.")
            return
    
    caption = (
        "🛡️ *VIP Subscriptions Available!*\n\n"
        "Choose your plan below and enjoy:\n"
        "✅ Daily expert football predictions\n"
        "✅ Exclusive AI picks\n"
        "✅ Direct access to our winning community"
    )


    keyboard = [
        [InlineKeyboardButton("1 Month - ₦9500", callback_data="sub_9500")],
        [InlineKeyboardButton("3 Months - ₦25000", callback_data="sub_25000")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_deposit")]
    ]

    await context.bot.send_photo(
        chat_id=chat_id,
        photo="https://imgur.com/a/rJ4q3N3",  # Replace with your hosted image URL
        caption=caption,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

app.add_handler(CallbackQueryHandler(show_subscription_options, pattern="subscription"))


async def show_subscription_options_p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id


    # ✅ STEP 1: Check for active subscription
    cursor.execute("SELECT expires_at FROM paid_predictions WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()

    if row:
        expires_at = row["expires_at"]
        now = datetime.now()

        if expires_at > now and (expires_at - now).days > 2:
            await update.message.reply_text("✅ You already have an active subscription.")
            return
    caption = (
        "🛡️ *VIP Subscriptions Available!*\n\n"
        "Choose your plan below and enjoy:\n"
        "✅ Daily expert football predictions\n"
        "✅ Exclusive AI picks\n"
        "✅ Direct access to our winning community"
    )

    keyboard = [
        [InlineKeyboardButton("1 Month - ₦9500", callback_data="sub_9500")],
        [InlineKeyboardButton("3 Months - ₦25000", callback_data="sub_25000")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_deposit")]
    ]
    
    await context.bot.send_photo(
        chat_id=chat_id,
        photo="https://imgur.com/a/rJ4q3N3",  # Replace with your hosted image URL
        caption=caption,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

app.add_handler(MessageHandler(filters.TEXT & filters.Regex("💎 Get Prediction"), show_subscription_options_p))


import requests
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

async def handle_subscription_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    plan = int(query.data.split("_")[1])

    # Map plan amount to duration
    duration = 30 if plan == 9500 else 90 if plan == 25000 else 30

    email = f"user_{user_id}@cooziepicks.com"
    headers = {
        "Authorization": f"Bearer {os.getenv('PAYSTACK_SECRET_KEY')}",
        "Content-Type": "application/json"
    }

    payload = {
        "email": email,
        "amount": plan * 100,
        "callback_url": "https://cooziepicks.com/thank-you/",  # or your deployed webhook URL
        "metadata": {
            "user_id": user_id,
            "plan": plan,
            "duration": duration,
            "type": "vip"
        }
    }

    response = requests.post("https://api.paystack.co/transaction/initialize", json=payload, headers=headers)
    data = response.json()

    if data.get("status"):
        payment_url = data["data"]["authorization_url"]
        await query.message.reply_text(
            f"💳 Click below to complete your VIP subscription of ₦{plan}.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Pay Now", url=payment_url)],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_deposit")]
            ])
        )
    else:
        await query.message.reply_text("❌ Failed to create payment link. Please try again later.")

app.add_handler(CallbackQueryHandler(handle_subscription_payment, pattern="^sub_"))

async def cancel_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the deposit flow by deleting the message."""
    query = update.callback_query
    await query.message.delete()
    await query.answer("🚫 Deposit canceled.")
    context.user_data.pop("awaiting_deposit", None)  # Clear state if used

app.add_handler(CallbackQueryHandler(cancel_deposit, pattern="^cancel_deposit$"))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta, time

async def check_sub_expiry(context):
    today = datetime.now().date()

    # Fetch users whose subscription expires in 2 or 1 days
    cursor.execute("""
        SELECT user_id, expires_at FROM paid_predictions
        WHERE DATE(expires_at) IN (%s, %s)
    """, (today + timedelta(days=2), today + timedelta(days=1)))
    
    expiring_users = cursor.fetchall()

    for user in expiring_users:
        expires_on = user["expires_at"].strftime("%Y-%m-%d")
        await context.bot.send_message(
            chat_id=user["user_id"],
            text=(
                f"⚠️ Your VIP subscription will expire on *{expires_on}*.\n"
                "Click below to renew now."
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔁 Renew Now", callback_data="subscription")
            ]])
        )

# Schedule this to run daily
job_queue = app.job_queue
job_queue.run_daily(check_sub_expiry, time=time(hour=8, minute=0))

from datetime import datetime
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler

async def check_expiry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    cursor.execute("SELECT expires_at FROM paid_predictions WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()

    if result and result["expires_at"]:
        expires_at = result["expires_at"]
        days_left = (expires_at.date() - datetime.now().date()).days

        if days_left > 0:
            msg = (
                f"✅ Your VIP subscription is active.\n"
                f"Expires on *{expires_at.strftime('%Y-%m-%d')}* ({days_left} day(s) left)."
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            msg = (
                "⚠️ Your VIP subscription has *expired*.\n"
                "Click below to renew now."
            )
            keyboard = [[InlineKeyboardButton("🔁 Renew Now", callback_data="subscription")]]
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        msg = (
            "❌ You don't have an active VIP subscription.\n"
            "Click below to subscribe and start receiving premium predictions."
        )
        keyboard = [[InlineKeyboardButton("📥 Subscribe", callback_data="subscription")]]
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# Register the command
app.add_handler(CommandHandler("checkexpiry", check_expiry))

async def test_expiry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await check_sub_expiry(context)

app.add_handler(CommandHandler("testexpiry", test_expiry))


import openai
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import time, datetime
from telegram.constants import ParseMode

# Replace with your actual values
YOUR_BOT_USERNAME = "CoozieAibot"
import os
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Function to generate football content
async def generate_football_post():
    prompt = (
        "write a short smart betting tup  for fottball bettors avoid predictions focus on strategy and discipline and add an emoji "
        "After the tip, end with a short line like:\n"
        "For more AI-powered predictions, tap below 👇\n\n"
        "Keep the full response under 40 words. Use clean formatting and 1–2 emojis only."
    )


    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=250
    )
    return response.choices[0].message.content.strip()

# Function to generate football image
async def generate_football_image():
    dalle_response = client.images.generate(
        prompt="high-stakes football match in a modern stadium, dramatic lighting, passionate fans cheering, players in motion, grass flying, high-resolution, realistic style",
        n=1,
        size="1024x1024"
    )
    return dalle_response.data[0].url

async def post_football_content(context):
    try:
        content = await generate_football_post()
        image_url = await generate_football_image()

        full_text = f"{content}\n\nSponsored by CooziePicks AI 🚀"

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("⚽ Get AI Football Picks", url=f"https://t.me/{YOUR_BOT_USERNAME}")
        ]])

        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=image_url,
            caption=full_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )

        print(f"✅ Posted football content at {datetime.now()}")
    except Exception as e:
        print(f"❌ Failed to post football content: {e}")


from telegram.ext import ApplicationBuilder

# Inside your bot startup logic
job_queue.run_daily(post_football_content, time=time(hour=9, minute=0))   # Morning

from telegram.ext import CommandHandler

async def test_ai_post(update, context):
    await post_football_content(context)
    await update.message.reply_text("✅ Test AI content posted.")

app.add_handler(CommandHandler("testaipost", test_ai_post))


from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

async def upload_today_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You’re not allowed to upload picks.")
        return

    # Reply with a button, not immediately asking for the image
    await update.message.reply_text(
        "📝 Click the button below to upload today’s pick:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📎 Upload Now", callback_data="start_upload_pick")]
        ])
    )


awaiting_upload = set()
awaiting_rollover = set()


async def handle_upload_pick_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id != ADMIN_ID:
        await query.message.reply_text("❌ You’re not allowed to upload.")
        return

    awaiting_upload.add(user_id)
    await query.message.reply_text("📸 Now send the image you want to upload for today’s pick.")



from datetime import date
awaiting_upload = set()  # make sure this is global

async def save_today_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # ⛔ Only proceed if admin and awaiting upload
    if user_id != ADMIN_ID or user_id not in awaiting_upload:
        return

    awaiting_upload.remove(user_id)

    # ✅ Get photo file_id
    try:
        file_id = update.message.photo[-1].file_id
    except:
        await update.message.reply_text("❌ Couldn't read the image. Try again.")
        return

    today = date.today()

    # ✅ Save in database
    try:
        cursor.execute("DELETE FROM daily_pick WHERE date = %s", (today,))
        cursor.execute("INSERT INTO daily_pick (image_file_id, date) VALUES (%s, %s)", (file_id, today))
        conn.commit()
    except Exception as e:
        await update.message.reply_text(f"❌ DB error: {e}")
        return

    # ✅ Send to channel (text only)
    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text="📢 *Today's Premium/Ai Pick is ready!*\n\nClick below to view the game of the day!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔍 View Today’s Pick", url=f"https://t.me/CoozieAibot")
            ]])
        )
    except Exception as e:
        print(f"❌ Failed to send to channel: {e}")

    # ✅ Send to VIP users (with image)
    try:
        cursor.execute("SELECT user_id FROM paid_predictions WHERE expires_at > NOW()")
        vip_users = cursor.fetchall()

        tasks = []

        for user in vip_users:
            user_id = user["user_id"]

            task = context.bot.send_photo(
                chat_id=user_id,
                photo=file_id,
                caption="🎯 Today's Pick is live!"
            )
            tasks.append(task)

        # Run all send_photo tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle individual failures
        for user, result in zip(vip_users, results):
            if isinstance(result, Exception):
                print(f"❌ Could not send to {user['user_id']}: {result}")

        await context.bot.send_message(
            chat_id=ADMIN_ID,  # Replace with your actual admin ID
            text="✅ Today’s Pick has been sent to all VIP users and posted in the channel."
        )

    except Exception as e:
        print(f"❌ Error fetching VIP users or sending photos: {e}")

async def handle_view_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # Check subscription
    cursor.execute("SELECT expires_at FROM paid_predictions WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    is_active = row and row["expires_at"] > datetime.now()

    if not is_active:
        await query.message.reply_text(
            "❌ You don't have an active subscription.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 Subscribe Now", callback_data="subscription")]
            ])
        )
        return

    # Get today's pick
    today = date.today()
    cursor.execute("SELECT image_file_id FROM daily_pick WHERE date = %s", (today,))
    row = cursor.fetchone()

    if row:
        await context.bot.send_photo(
            chat_id=user_id,
            photo=row["image_file_id"],
            caption="🎯 Here's today's expert pick!"
        )
    else:
        await query.message.reply_text("⚠️ No game has been uploaded yet today.")




app.add_handler(CommandHandler("upload", upload_today_pick))
app.add_handler(CallbackQueryHandler(handle_view_pick, pattern="view_pick"))
app.add_handler(CallbackQueryHandler(handle_upload_pick_button, pattern="^start_upload_pick$"))


async def handle_view_pick_p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    # Check subscription
    cursor.execute("SELECT expires_at FROM paid_predictions WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    is_active = row and row["expires_at"] > datetime.now()

    if not is_active:
        await update.message.reply_text(
            "❌ You don't have an active subscription.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 Subscribe Now", callback_data="subscription")]
            ])
        )
        return

    # Get today's pick
    today = date.today()
    cursor.execute("SELECT image_file_id FROM daily_pick WHERE date = %s", (today,))
    row = cursor.fetchone()

    if row:
        await context.bot.send_photo(
            chat_id=user_id,
            photo=row["image_file_id"],
            caption="🎯 Here's today's expert pick!"
        )
    else:
        await update.message.reply_text("⚠️ No game has been uploaded yet today.")

app.add_handler(MessageHandler(filters.TEXT & filters.Regex("🎯 Today’s Pick"), handle_view_pick_p))


async def upload_today_rollover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ You’re not allowed to upload picks.")
        return

    # Reply with a button, not immediately asking for the image
    await update.message.reply_text(
        "📝 Click the button below to upload today’s pick:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📎 Upload Now", callback_data="start_upload_rollover")]
        ])
    )


awaiting_rollover = set()

app.add_handler(CommandHandler("rollover", upload_today_rollover))


async def handle_upload_pick_but(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id != ADMIN_ID:
        await query.message.reply_text("❌ You’re not allowed to upload.")
        return

    awaiting_rollover.add(user_id)
    await query.message.reply_text("📸 Now send the image you want to upload for today’s rollover.")

app.add_handler(CallbackQueryHandler(handle_upload_pick_but, pattern="^start_upload_rollover$"))


from datetime import date
awaiting_rollover = set()  # make sure this is global

async def save_today_rollover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # ⛔ Only proceed if admin and awaiting upload
    if user_id != ADMIN_ID or user_id not in awaiting_rollover:
        return

    awaiting_rollover.remove(user_id)

    # ✅ Get photo file_id
    try:
        file_id = update.message.photo[-1].file_id
    except:
        await update.message.reply_text("❌ Couldn't read the image. Try again.")
        return

    today = date.today()

    # ✅ Save in database
    try:
        cursor.execute("DELETE FROM rollover WHERE date = %s", (today,))
        cursor.execute("INSERT INTO rollover (image_file_id, date) VALUES (%s, %s)", (file_id, today))
        conn.commit()
    except Exception as e:
        await update.message.reply_text(f"❌ DB error: {e}")
        return

    # ✅ Send to channel (text only)
    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text="📢 *Today's Rollover Pick is ready!*\n\nClick below to view the game of the day!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔍 View Today’s Pick", url=f"https://t.me/CoozieAibot")
            ]])
        )
    except Exception as e:
        print(f"❌ Failed to send to channel: {e}")

        await context.bot.send_message(
            chat_id=ADMIN_ID,  # Replace with your actual admin ID
            text="✅ Today’s rollover has been sent to all VIP users and posted in the channel."
        )


async def handle_view_rollover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    # Check subscription
    cursor.execute("SELECT expires_at FROM paid_predictions WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    is_active = row and row["expires_at"] > datetime.now()

    if not is_active:
        await query.message.reply_text(
            "❌ You don't have an active subscription.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 Subscribe Now", callback_data="subscription")]
            ])
        )
        return

    # Get today's pick
    today = date.today()
    cursor.execute("SELECT image_file_id FROM rollover WHERE date = %s", (today,))
    row = cursor.fetchone()

    if row:
        await context.bot.send_photo(
            chat_id=user_id,
            photo=row["image_file_id"],
            caption="🎯 Here's today's rollover pick!"
        )
    else:
        await query.message.reply_text("⚠️ No game has been uploaded yet today.")

app.add_handler(CallbackQueryHandler(handle_view_rollover, pattern="view_rollover"))


async def handle_view_rollover_p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    # Check subscription
    cursor.execute("SELECT expires_at FROM paid_predictions WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    is_active = row and row["expires_at"] > datetime.now()

    if not is_active:
        await update.message.reply_text(
            "❌ You don't have an active subscription.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 Subscribe Now", callback_data="subscription")]
            ])
        )
        return

    # Get today's pick
    today = date.today()
    cursor.execute("SELECT image_file_id FROM rollover WHERE date = %s", (today,))
    row = cursor.fetchone()

    if row:
        await context.bot.send_photo(
            chat_id=user_id,
            photo=row["image_file_id"],
            caption="🎯 Here's today's rollover pick!"
        )
    else:
        await update.message.reply_text("⚠️ No game has been uploaded yet today.")

app.add_handler(MessageHandler(filters.TEXT & filters.Regex("📈 2 Odds Rollover"), handle_view_rollover_p))


async def handle_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in awaiting_upload:
        await save_today_image(update, context)
    if user_id in awaiting_rollover:
        await save_today_rollover(update, context)
    elif context.user_data.get(f"uploading_testimony_{user_id}"):
        await handle_uploaded_testimony(update, context)

app.add_handler(MessageHandler(filters.PHOTO, handle_photos))

import asyncio
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, MessageHandler, filters

discount_active_until = None  # Global tracker

async def handle_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return await update.message.reply_text("⛔ You're not authorized to send discounts.")

    try:
        days = int(update.message.text.split("|")[1])
    except (IndexError, ValueError):
        return await update.message.reply_text("❌ Invalid format. Use: /discount|30")

    global discount_active_until
    discount_active_until = datetime.now() + timedelta(days=days)

    cursor.execute("SELECT user_id FROM prediction_users")
    all_users = cursor.fetchall()

    async def send_discount(uid):
        # Check VIP status
        cursor.execute("SELECT expires_at FROM paid_predictions WHERE user_id = %s", (uid,))
        sub = cursor.fetchone()
        if sub and sub["expires_at"] > datetime.now():
            return  # User already has an active sub

        try:
            await context.bot.send_photo(
                chat_id=uid,
                photo="https://imgur.com/a/rJ4q3N3",  # Replace with real file ID
                caption=(
                    f"🔥 *Limited-Time Offer!*\n\n"
                    f"Subscribe for 1 month at just ₦6,500 (instead of ₦9,500).\n"
                    f"Offer expires in {days} days!\n\n"
                    f"Don't miss out! 💼"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Pay ₦6,500 Now", callback_data="sub_200")]
                ])
            )
        except:
            pass

    # Run all send tasks in parallel
    tasks = [asyncio.create_task(send_discount(row["user_id"])) for row in all_users]
    await asyncio.gather(*tasks)

    await update.message.reply_text("✅ Discount broadcast sent to all non-VIP users.")

# Register the handler
app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/discount\|"), handle_discount))


# Support message text
SUPPORT_MESSAGE = (
    "🛠 *Need Help?*\n\n"
    "If you're experiencing issues or need assistance:\n\n"
    "💬 Contact our admin: @cooziepicks\n"
    "We're here to help you enjoy the platform!"
)

# Support command handler function
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(SUPPORT_MESSAGE, parse_mode="Markdown")

# Register the command with your bot application
app.add_handler(CommandHandler("support", support))

async def user_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT COUNT(*) AS count FROM predictions_users")
    result = cursor.fetchone()
    total_users = result["count"] if result else 0

    await update.message.reply_text(f"📊 Total Users: {total_users}")

app.add_handler(CommandHandler("usercount", user_count))


from telegram.ext import ApplicationBuilder
from telegram import BotCommand
from telegram.ext import Application

async def set_bot_commands(application):
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("checkexpiry", "Check Sub Expiry date"),
        BotCommand("support", "Get help or contact admin"),
    ])

# Set bot commands when the bot starts
app.post_init = set_bot_commands


if __name__ == "__main__":
    app.run_polling()