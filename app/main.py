import threading
import time
from datetime import datetime, date

from fastapi import FastAPI

from .config import SCHEDULE_TIME
from .selector import run_selection
from .telegram_bot import format_selection_for_telegram, send_telegram_message

app = FastAPI(title="Quant Selector (Tushare Version) on Railway")


@app.get("/")
def root():
    return {"status": "ok", "message": "Quant selector (Tushare version) running on Railway."}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/run_once")
def run_once():
    """
    手动触发一次选股 + 推送
    """
    df = run_selection()
    text = format_selection_for_telegram(df)
    send_telegram_message(text)
    return {
        "status": "done",
        "selected_count": 0 if df is None else int(len(df)),
    }


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
                send_telegram_message(text)
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
