import threading
import time
from datetime import datetime, date
from typing import Optional

from fastapi import FastAPI, Request

from .config import SCHEDULE_TIME
from .selector import run_selection
from .telegram_bot import (
    build_action_keyboard,
    build_help_message,
    extract_chat_id,
    extract_command_from_update,
    format_selection_for_telegram,
    send_telegram_message,
)

app = FastAPI(title="Quant Selector (Tushare Version) on Railway")

_last_selection_text: Optional[str] = None
_last_selection_time: Optional[datetime] = None
_last_selection_count: Optional[int] = None
_state_lock = threading.Lock()


@app.get("/")
def root():
    return {"status": "ok", "message": "Quant selector (Tushare version) running on Railway."}


@app.get("/health")
def health():
    return {"status": "ok"}


def _remember_selection_result(result_text: str, count: int) -> None:
    global _last_selection_text, _last_selection_time, _last_selection_count

    with _state_lock:
        _last_selection_text = result_text
        _last_selection_count = count
        _last_selection_time = datetime.now()


def _format_status_message() -> str:
    with _state_lock:
        last_time = _last_selection_time
        last_count = _last_selection_count

    lines = ["📊 状态概览", f"⏰ 每日定时：{SCHEDULE_TIME}"]

    if last_time:
        lines.append(f"上次执行：{last_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"上次入选：{last_count or 0} 只")
    else:
        lines.append("上次执行：暂无记录")

    return "\n".join(lines)


@app.get("/run_once")
def run_once():
    """
    手动触发一次选股 + 推送
    """
    df = run_selection()
    text = format_selection_for_telegram(df)
    count = 0 if df is None else int(len(df))
    _remember_selection_result(text, count)
    send_telegram_message(text, reply_markup=build_action_keyboard())
    return {
        "status": "done",
        "selected_count": count,
    }


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """
    支持通过 Telegram 指令操作：运行、查看状态、重发结果、帮助。
    """

    update = await request.json()
    command_raw = extract_command_from_update(update)
    chat_id = extract_chat_id(update)

    if not command_raw:
        return {"status": "ignored", "reason": "no command"}

    command = command_raw.lower()
    keyboard = build_action_keyboard()

    if command in ("/start", "/help", "help", "/commands", "commands", "菜单", "帮助"):
        send_telegram_message(
            build_help_message(SCHEDULE_TIME),
            reply_markup=keyboard,
            disable_notification=True,
            chat_id=chat_id,
        )
        return {"status": "ok", "action": "help"}

    if command in ("/status", "status"):
        send_telegram_message(
            _format_status_message(),
            reply_markup=keyboard,
            disable_notification=True,
            chat_id=chat_id,
        )
        return {"status": "ok", "action": "status"}

    if command in ("/last", "last"):
        with _state_lock:
            last_text = _last_selection_text

        if last_text:
            send_telegram_message(
                last_text, reply_markup=keyboard, disable_notification=True, chat_id=chat_id
            )
            return {"status": "ok", "action": "last"}

        send_telegram_message(
            "暂无历史推送记录。", reply_markup=keyboard, disable_notification=True, chat_id=chat_id
        )
        return {"status": "ok", "action": "last_empty"}

    if command in ("/run", "run"):
        df = run_selection()
        text = format_selection_for_telegram(df)
        count = 0 if df is None else int(len(df))
        _remember_selection_result(text, count)
        send_telegram_message(text, reply_markup=keyboard, chat_id=chat_id)
        return {"status": "ok", "action": "run", "selected_count": count}

    send_telegram_message(
        "未识别的指令，发送 /help 查看可用操作。",
        reply_markup=keyboard,
        disable_notification=True,
        chat_id=chat_id,
    )
    return {"status": "ignored", "action": "unknown"}


# =============== 后台定时任务 ===============

def _scheduler_worker():
    """
    简单轮询定时器：
    - 每 60 秒检查一次时间
    - 当当前时间 >= SCHEDULE_TIME 且当天还没跑过，就执行一次
    """
    print(f"[scheduler] started, will run everyday at {SCHEDULE_TIME}")
    last_run_date: date | None = None

    while True:
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        today = now.date()

        try:
            if current_time_str >= SCHEDULE_TIME and last_run_date != today:
                print(f"[scheduler] running selection at {now}")
                df = run_selection()
                text = format_selection_for_telegram(df)
                count = 0 if df is None else int(len(df))
                _remember_selection_result(text, count)
                send_telegram_message(text, reply_markup=build_action_keyboard())
                last_run_date = today
        except Exception as e:
            print("[scheduler] error:", e)

        time.sleep(60)


@app.on_event("startup")
def on_startup():
    """
    FastAPI 启动时挂一个后台线程。
    """
    t = threading.Thread(target=_scheduler_worker, daemon=True)
    t.start()
    print("[main] scheduler thread started.")
