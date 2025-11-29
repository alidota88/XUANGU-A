import os

# ===== Telegram 配置（Railway 环境变量） =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# 每天自动推送时间（服务器本地时间，格式 "HH:MM"）
# 比如 A 股收盘后跑："15:10"
SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "15:10")

# ===== Tushare 配置 =====
# 你在 https://tushare.pro 注册后拿到的 token，放到 Railway 环境变量 TUSHARE_TOKEN
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")

# 用来做 RS 的基准指数，Tushare 写法：沪深300 = "000300.SH"
BENCHMARK_INDEX = os.getenv("BENCHMARK_INDEX", "000300.SH")

# 选股宇宙：这里用沪深300成分股（更省 Tushare 调用次数）
INDEX_UNIVERSE = os.getenv("INDEX_UNIVERSE", "000300.SH")   # 你可以换成 399006.SZ 等

# 突破箱体周期
BREAKOUT_N = int(os.getenv("BREAKOUT_N", "55"))

# 评分阈值
MIN_SCORE = float(os.getenv("MIN_SCORE", "80"))

# RS 下限
MIN_RS = float(os.getenv("MIN_RS", "0.7"))
