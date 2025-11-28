# Quant Selector (Tushare Version)

一个基于 FastAPI 的量化选股与 Telegram 推送服务，使用 Tushare 获取行情数据，按照自定义规则筛选A股标的，并每日定时推送结果。

## 功能概览
- `GET /`：存活检测，返回服务状态。
- `GET /health`：健康检查。
- `GET /run_once`：手动运行一次选股并推送结果。
- 应用启动后会在后台线程按 `SCHEDULE_TIME` 指定的时间每天运行一次自动选股并推送。

## 环境变量
- `TUSHARE_TOKEN`：Tushare API 访问令牌。
- `TELEGRAM_BOT_TOKEN`：Telegram Bot 令牌，用于推送。
- `TELEGRAM_CHAT_ID`：接收推送的聊天 ID。
- `SCHEDULE_TIME`：每日定时任务触发时间（默认 `15:10`，24 小时制 `HH:MM`）。
- `BENCHMARK_INDEX`：计算 RS 使用的基准指数代码（默认 `000300.SH`）。
- `BREAKOUT_N`：箱体突破周期天数（默认 `55`）。
- `MAX_STOCKS_PER_DAY`：每日候选股票数量上限（默认 `500`）。

## 本地运行
1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
2. 设置必要的环境变量（至少需要 `TUSHARE_TOKEN`，否则无法获取数据）：
   ```bash
   export TUSHARE_TOKEN=你的token
   export TELEGRAM_BOT_TOKEN=你的bot令牌
   export TELEGRAM_CHAT_ID=你的chat_id
   # 可选：覆盖调度时间或策略参数
   export SCHEDULE_TIME=15:10
   ```
3. 启动服务：
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
4. 通过浏览器或 curl 访问接口，例如：
   ```bash
   curl http://localhost:8000/run_once
   ```

## 选股逻辑摘要
- 先按成交额选出前 `MAX_STOCKS_PER_DAY` 只股票作为候选。
- 为每只股票获取近 300 日 K 线、近 20 日资金流，并获取沪深300等指数行情用于 RS 计算。
- 依据以下条件过滤：
  - 箱体突破、放量、主力资金连续 3 日净流入。
  - 所属行业需同时处于 5 日涨幅与 5 日资金净流入排名前 20% 且净流入为正（主线板块）。
  - RS > 0.7，综合得分 ≥ 80（突破30% + 放量25% + 主力25% + 板块20% 权重）。
- 结果按得分排序，并通过 Telegram 推送摘要（最多展示前 30 条）。

## 部署提示
- 项目包含 `Procfile`，可用于在 Railway 等平台以 `uvicorn app.main:app` 方式运行。
- 若不配置 Telegram 环境变量，服务仍可运行选股逻辑，但不会发送推送（日志中会提示跳过）。
