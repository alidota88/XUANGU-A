from datetime import datetime
from typing import Optional

import pandas as pd
import requests

from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def format_selection_for_telegram(df: pd.DataFrame, max_rows: int = 30) -> str:
    """
    把选股结果格式化为 Telegram 文本消息。
    """
    if df is None or df.empty:
        return "📭 今日没有符合严格条件的标的。"

    lines = []
    run_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append("📈 今日量化选股结果")
    lines.append("运行时间：{}".format(run_time))
    lines.append(
        "满足条件：突破箱体 + 放量 + 主力 3 日净流入 + 主线板块 + RS>0.7 + 得分>=80"
    )
    lines.append("")

    show_df = df.head(max_rows)
    lines.append(f"入选 {len(df)} 只，展示前 {len(show_df)} 只：")
    for _, row in show_df.iterrows():
        line = (
            f"{row['code']} {row['name']} | "
            f"行业: {row['industry']} | "
            f"RS: {row['RS']:.2f} | "
            f"板块涨幅Rank: {row['sector_up_rank']:.2f} | "
            f"板块资金Rank: {row['sector_flow_rank']:.2f} | "
            f"总分: {row['score']:.1f}"
        )
        lines.append(line)

    msg = "\n".join(lines)
    return msg[:4000]


_COMMANDS = [
    ("/run", "立即跑一次选股并推送结果"),
    ("/status", "查看下一次定时任务以及上次选股时间"),
    ("/last", "重发最近一次推送的结果"),
    ("/help", "查看帮助信息"),
    ("/commands", "查看全部支持的命令"),
]


def build_help_message(schedule_time: str) -> str:
    """生成 /help 的说明文案。"""

    lines = ["🤖 机器人指令", ""]

    for command, description in _COMMANDS:
        lines.append(f"{command} - {description}")

    lines.extend(
        [
            "",
            "ℹ️ 也可以直接点击下方的快捷按钮操作。",
            "",
            f"⏰ 每日定时：{schedule_time}",
        ]
    )

    return "\n".join(lines)


def build_action_keyboard() -> dict:
    """生成操作快捷按钮的 inline keyboard。"""

    return {
        "inline_keyboard": [
            [
                {"text": "▶️ 立即运行", "callback_data": "run"},
                {"text": "ℹ️ 状态", "callback_data": "status"},
            ],
            [
                {"text": "📩 最近结果", "callback_data": "last"},
                {"text": "❓ 帮助", "callback_data": "help"},
            ],
            [
                {"text": "📜 命令一览", "callback_data": "commands"},
            ],
        ]
    }


def send_telegram_message(
    text: str,
    reply_markup: Optional[dict] = None,
    disable_notification: bool = False,
) -> Optional[dict]:
    """
    使用 Telegram Bot API 发送消息。
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[telegram] TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 未设置，跳过发送。")
        return None

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_notification": disable_notification,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    resp = requests.post(url, json=payload, timeout=15)
    if resp.status_code != 200:
        print("[telegram] 发送失败:", resp.text)
        return None

    return resp.json()


def extract_command_from_update(update: dict) -> Optional[str]:
    """从 Telegram update 中提取命令，兼容 /help@bot 这样的格式。"""

    message = update.get("message") or update.get("callback_query", {}).get("message")
    if not message:
        return None

    if "text" in message:
        raw_text: str = message["text"]
        text = raw_text.strip().split()[0]  # 只取第一个词，忽略参数
        if text.startswith("/"):
            # 处理 /help@my_bot 这类指令
            text = "/" + text[1:].split("@", maxsplit=1)[0]
    elif "data" in update.get("callback_query", {}):
        text = update["callback_query"]["data"]
    else:
        return None

    return text.strip()
