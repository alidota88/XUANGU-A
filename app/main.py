import threading
import time
from datetime import datetime, date

from fastapi import FastAPI, Request
import requests

from .config import SCHEDULE_TIME, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from .selector import run_selection
from .telegram_bot import format_selection_for_telegram, send_telegram_message
from .data_loader import get_index_history


app = FastAPI(title="Tushare Quant Selector with Telegram Commands")


# ===========================
#  基本服务接口
# ===========================

@app.get("/")
def root():
    return {"status": "ok", "message": "Quant selector running."}

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/run_once")
def run_once():
    df = run_selection()
    text = format_selection_for_telegram(df)
    send_telegram_message(text)
    return {"status": "done", "count": len(df) if df is not None else 0}



# ===========================
# Telegram 指令处理接口
# ===========================

@app.post("/telegram")
async def telegram_webhook(req: Request):
    data = await req.json()

    # 解析 telegram 消息
    if "message" not in data:
        return {"ok": True}

    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    # 只响应你的 chat_id
    if str(chat_id) != str(TELEGRAM_CHAT_ID):
        return {"ok": True}

    # ============ 命令解析 ============
    if text.startswith("/help"):
        send_telegram_message(
            "📘 支持命令：\n"
            "/run_once - 立即执行选股\n"
            "/today - 查看指数与市场简况\n"
            "/status - 查看系统运行状态\n"
            "/help - 查看命令说明"
        )
        return {"ok": True}

    elif text.startswith("/run_once"):
        df = run_selection()
        send_telegram_message(format_selection_for_telegram(df))
        return {"ok": True}

    elif text.startswith("/today"):
        # 简单获取沪深300最近数据
        idx = get_index_history(days=5)
        last = idx.tail(1).iloc[0]
        send_telegram_message(
            f"📊 今日指数概况：\n"
            f"沪深300 收盘：{last['close']}\n"
            f"最高：{last['high']} 最低：{last['low']}\n"
        )
        return {"ok": True}

    elif text.startswith("/status"):
        msg = (
            "🟢 服务正常运行中\n"
            f"自动推送时间：{SCHEDULE_TIME}\n"
            "缓存目录：/app/data\n"
            "使用 /run_once 测试选股\n"
        )
        send_telegram_message(msg)
        return {"ok": True}

    else:
        send_telegram_message("未知命令，发送 /help 查看帮助。")
        return {"ok": True}



# ===========================
#  每日定时任务
# ===========================

def _scheduler_worker():
    print(f"[scheduler] Running everyday at {SCHEDULE_TIME}")
    last_run_date = None

    while True:
        now = datetime.now()
        cur = now.strftime("%H:%M")
        today = now.date()

        if cur >= SCHEDULE_TIME and last_run_date != today:
            df = run_selection()
            send_telegram_message(format_selection_for_telegram(df))
            last_run_date = today

        time.sleep(60)


@app.on_event("startup")
def on_startup():
    # 启动定时任务线程
    t = threading.Thread(target=_scheduler_worker, daemon=True)
    t.start()
    print("[startup] scheduler started.")


