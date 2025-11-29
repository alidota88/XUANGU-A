from telegram.ext import ApplicationBuilder, CommandHandler
from .strategy import run_selection
import os
import pytz
from datetime import time

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


async def command_check(update, context):
    msg = run_selection()
    await update.message.reply_text(msg)


async def job_daily(context):
    msg = run_selection()
    await context.bot.send_message(chat_id=CHAT_ID, text=msg)


def start_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # 用户手动触发
    app.add_handler(CommandHandler("check", command_check))

    # 每日17:00自动推送
    tz = pytz.timezone("Asia/Shanghai")
    app.job_queue.run_daily(job_daily, time=time(17,0,tzinfo=tz))

    app.run_polling()
