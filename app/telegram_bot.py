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
    lines.append("📈 今日量化选股结果（前 {} 只）".format(min(len(df), max_rows)))
    lines.append("（条件：突破箱体+放量+主力 3 日净流入+主线板块+RS>0.7+得分>=80）")
    lines.append("")

    show_df = df.head(max_rows)
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


def send_telegram_message(text: str) -> Optional[dict]:
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
    }

    resp = requests.post(url, json=payload, timeout=15)
    if resp.status_code != 200:
        print("[telegram] 发送失败:", resp.text)
        return None

    return resp.json()
