# app/data_loader.py
"""
数据加载模块

实际生产使用时，你需要把这里的假数据替换成：
- Tushare / Akshare / 你的本地数据库
- 返回格式按下面的注释即可
"""

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def load_market_data() -> pd.DataFrame:
    """
    加载最近一段时间的个股行情数据（含历史价格，用于计算突破、RS 等）。

    期望返回 DataFrame，至少包含列：
    - ts_code: 股票代码
    - trade_date: 交易日期（datetime 或 str 'YYYY-MM-DD'）
    - name: 股票名称
    - industry: 所属行业 / 概念
    - close: 收盘价
    - high: 最高价
    - open: 开盘价（用于构造伪“主力净流入”）
    - volume: 成交量
    - amount: 成交额

    下面是一个“假数据示例”，仅用于代码能直接跑通。
    请根据你自己的数据源改写。
    """
    logger.warning("正在使用假数据生成行情，请尽快替换为真实数据源！")

    np.random.seed(42)
    today = datetime.today().date()
    days = 90  # 近 90 个交易日

    stock_list = [
        ("000001.SZ", "平安银行", "银行"),
        ("000002.SZ", "万科A", "地产"),
        ("600519.SH", "贵州茅台", "白酒"),
        ("300750.SZ", "宁德时代", "新能源"),
        ("688981.SH", "中芯国际", "半导体"),
    ]

    rows = []
    for ts_code, name, industry in stock_list:
        price = 50 + np.random.rand() * 100
        for i in range(days):
            date = today - timedelta(days=days - i)
            if date.weekday() >= 5:
                continue  # 跳过周末

            change = np.random.randn() * 0.02  # ±2%
            open_price = price * (1 + np.random.randn() * 0.005)
            close = max(1, price * (1 + change))
            high = max(open_price, close) * (1 + abs(np.random.randn()) * 0.01)
            volume = np.random.randint(1e5, 5e6)
            amount = volume * close

            rows.append({
                "ts_code": ts_code,
                "trade_date": date,
                "name": name,
                "industry": industry,
                "open": open_price,
                "close": close,
                "high": high,
                "volume": volume,
                "amount": amount,
            })
            price = close

    df = pd.DataFrame(rows)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


def load_index_history(days: int = 90) -> pd.DataFrame:
    """
    加载指数（日线），用于计算 RS（相对强弱）。

    期望返回 DataFrame，至少包含：
    - trade_date
    - close

    这里同样用假数据。
    """
    logger.warning("正在使用假数据生成指数，请尽快替换为真实指数数据源！")

    today = datetime.today().date()
    rows = []
    price = 3000
    for i in range(days):
        date = today - timedelta(days=days - i)
        if date.weekday() >= 5:
            continue
        change = np.random.randn() * 0.01
        close = price * (1 + change)
        rows.append({
            "trade_date": date,
            "close": close,
        })
        price = close

    df = pd.DataFrame(rows)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df
