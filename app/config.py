import os

# ================== Tushare Token ==================
# 在 Railway 的环境变量中设置：TUSHARE_TOKEN=你的token
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")

# ================== Telegram 推送 ==================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# 每天推送时间（服务器本地时间，24H 制，HH:MM）
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "15:10")

# ================== 策略参数 ==================
# 用哪个指数来计算 RS（沪深300）
BENCHMARK_INDEX = os.getenv("BENCHMARK_INDEX", "000300.SH")

# 箱体突破周期
BREAKOUT_N = int(os.getenv("BREAKOUT_N", "55"))

# 每天最多处理候选股数量（前 N 成交额）
MAX_STOCKS_PER_DAY = int(os.getenv("MAX_STOCKS_PER_DAY", "500"))
