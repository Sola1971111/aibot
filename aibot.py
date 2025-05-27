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

# Initialize bot application
app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):    
    keyboard = [
        [InlineKeyboardButton("📢 Join Our Community", url="https://t.me/taskpaybot122")],
        [InlineKeyboardButton("💎 Get Premium Prediction", callback_data="whatsapp_task")],
        [InlineKeyboardButton("📸 Testimonies from Community", callback_data="daily_bonus")],
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
        f"Welcome to CooziePicks! /n/nYour #1 home for premium football predictions, expert AI picks, daily tips, and real earnings through engaging tasks. Join now and win smarter!",
        reply_markup=reply_markup
    )

    await update.message.reply_text(
        "Choose an Option",
        reply_markup=persistent_keyboard
    )

app.add_handler(CommandHandler("start", start))


if __name__ == "__main__":
    app.run_polling()