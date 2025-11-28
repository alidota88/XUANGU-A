import os

# 从 Railway 环境变量里读取
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# 每天自动推送的时间（服务器本地时间，格式 HH:MM）
# 比如 15:10（收盘后跑），你可以自己改
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "15:10")

# 选股时使用的大盘指数（用来算 RS）
# 这里用沪深300
BENCHMARK_INDEX = os.getenv("BENCHMARK_INDEX", "sh000300")

# 突破箱体周期
BREAKOUT_N = int(os.getenv("BREAKOUT_N", "55"))

# 每天最多处理多少只股票（避免 AkShare 请求太多被封）
MAX_STOCKS_PER_DAY = int(os.getenv("MAX_STOCKS_PER_DAY", "500"))
