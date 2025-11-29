import aiohttp
import asyncio
import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

async def async_send_message(text: str):
    """
    完全异步的发送 Telegram 消息版本
    不阻塞，不会把服务器拖死
    自动重试 3 次
    """

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    for attempt in range(3):
        try:
            timeout = aiohttp.ClientTimeout(total=3)   # 限制最多 3 秒
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(API_URL, json=payload) as resp:
                    if resp.status == 200:
                        return True
                    else:
                        print(f"[telegram] error status {resp.status}")
        except Exception as e:
            print(f"[telegram] send error: {e}")

        await asyncio.sleep(0.5)

    return False


def send_telegram_message(text: str):
    """
    对外仍然保持同步接口
    但内部用 asyncio 创建异步任务
    避免阻塞 uvicorn
    """
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(async_send_message(text))
    except RuntimeError:
        # 在没有 event loop 情况下的新 loop
        asyncio.run(async_send_message(text))
