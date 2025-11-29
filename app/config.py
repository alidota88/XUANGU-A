# app/config.py
import os

# ========== Telegram 配置 ==========
# 这两个在 Railway 里配置环境变量：
# TELEGRAM_BOT_TOKEN = "你的 Bot Token"
# TELEGRAM_CHAT_ID   = "你的聊天 ID（可以是群，也可以是你自己的 ID）"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ========== 定时推送配置 ==========
# 每天什么时间跑一次策略（服务器时间，24 小时制，格式 "HH:MM"）
# 比如中国 A 股收盘后，可以设成 "15:10"（如果服务器时区不是上海，你按服务器时区调）
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "15:10")  # 默认 15:10

# 是否开启自动定时
AUTO_RUN_ENABLED = os.getenv("AUTO_RUN_ENABLED", "true").lower() in ("1", "true", "yes")

# ========== 选股参数 ==========
# 可以根据你想要的周期调
BREAKOUT_N = int(os.getenv("BREAKOUT_N", "55"))   # 箱体突破 N 日高
VOL_MA_N = int(os.getenv("VOL_MA_N", "20"))       # 成交量均线周期

# 评分阈值
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "80.0"))

# 调试模式：为 true 时，不会真的发 Telegram，只打印到日志
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() in ("1", "true", "yes")
