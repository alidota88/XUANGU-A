# app/telegram_bot.py
import logging
import requests

from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DEBUG_MODE

logger = logging.getLogger(__name__)


def send_telegram_message(text: str) -> bool:
    """
    使用 Telegram Bot API 直接发消息，最简单稳定的方式。
    """
    if DEBUG_MODE:
        logger.info("[DEBUG MODE] Telegram message would be:\n%s", text)
        return True

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 未配置，无法发送消息。")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",  # 简单用 Markdown 格式
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info("Telegram 消息发送成功。")
            return True
        else:
            logger.error("Telegram 发送失败: status=%s, body=%s",
                         resp.status_code, resp.text)
            return False
    except Exception as e:
        logger.exception("Telegram 发送异常: %s", e)
        return False


def format_selection_for_telegram(summary: dict) -> str:
    """
    把选股结果格式化成 Telegram 文本。
    summary 结构来自 selector.run_selection 返回。
    """

    header = (
        "📈 *量化主升浪选股结果*\n"
        "规则：突破箱体 + 放量异动 + 主力/板块资金 + RS 强势 + 综合评分\n\n"
    )

    meta = summary.get("meta", {})
    picks = summary.get("picks", [])
    run_time = meta.get("run_time", "")
    universe_size = meta.get("universe_size", 0)

    if not picks:
        body = f"本次扫描时间：{run_time}\n本次共扫描：{universe_size} 只股票\n\n未找到满足严格条件的标的。"
        return header + body

    body_lines = [
        f"本次扫描时间：{run_time}",
        f"本次共扫描：{universe_size} 只股票",
        f"满足严格条件：{len(picks)} 只\n",
        "前 20 只如下（按综合评分排序）：\n"
    ]

    for i, stock in enumerate(picks[:20], start=1):
        line = (
            f"{i}. `{stock.get('ts_code', '')}` {stock.get('name', '')}\n"
            f"   收盘：{stock.get('close', 0):.2f}  "
            f"评分：{stock.get('score', 0):.1f}\n"
            f"   RS：{stock.get('rs', 0):.2f}  "
            f"板块：{stock.get('industry', '未知')}  "
            f"板块强度：{stock.get('sector_strength', 0):.2f}\n"
        )
        body_lines.append(line)

    return header + "\n".join(body_lines)
