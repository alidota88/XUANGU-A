from .cache_manager import load_cache, save_cache
# app/data_loader.py

import os
from datetime import datetime, timedelta

import pandas as pd
import tushare as ts

TS_TOKEN = os.getenv("TS_TOKEN")


def get_pro():
    if not TS_TOKEN:
        raise Exception("环境变量 TS_TOKEN 未设置")
    ts.set_token(TS_TOKEN)
    return ts.pro_api()


# ========= 获取最近交易日 =========
def get_latest_trade_date(days_back: int = 20) -> str:
    """
    返回最近一个交易日（YYYYMMDD）
    """
    pro = get_pro()
    today = datetime.today()
    start = (today - timedelta(days=days_back)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")

    cal = pro.trade_cal(exchange="SSE", start_date=start, end_date=end, is_open="1")
    if cal.empty:
        raise Exception("trade_cal 返回为空，检查 Tushare 权限或网络")

    last_trade_date = cal["cal_date"].iloc[-1]
    return last_trade_date


# ========= 获取全市场股票基础信息（含行业） =========
def get_stock_list() -> pd.DataFrame:
    """
    返回字段至少包含: code, name, industry, list_date
    """
    pro = get_pro()

    try:
        df = pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,name,area,industry,list_date",
        )
    except Exception as e:
        print("[data_loader] stock_basic 调用失败，使用兜底字段", e)
        df = pro.stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,name,list_date",
        )
        df["industry"] = "未知"

    # 强制保证有 industry 列
    if "industry" not in df.columns:
        df["industry"] = "未知"

    df.rename(columns={"ts_code": "code"}, inplace=True)
    df["industry"] = df["industry"].fillna("未知")
    df["name"] = df["name"].fillna("未知")
    return df


# ========= 这里就是关键：get_top_liquidity_stocks =========
def get_top_liquidity_stocks(top_n: int = 500) -> pd.DataFrame:
    """
    获取按当日成交额排序的前 top_n 只股票
    返回字段: code, name, industry, close, high, low, vol, amount
    """
    pro = get_pro()
    trade_date = get_latest_trade_date()
    print(f"[data_loader] 获取 {trade_date} 全市场日线数据用于成交额排序")

    daily = pro.daily(trade_date=trade_date)
    if daily.empty:
        raise Exception(f"Tushare daily({trade_date}) 返回为空")

    stock_list = get_stock_list()

    # 按 ts_code / code merge
    df = daily.merge(stock_list, left_on="ts_code", right_on="code", how="left")

    # 兜底
    df["industry"] = df.get("industry", "未知")
    df["industry"] = df["industry"].fillna("未知")
    df["name"] = df["name"].fillna("未知")

    # 成交额 amount 转成数值 & 排序
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])
    df = df.sort_values("amount", ascending=False).head(top_n)

    return df[["code", "name", "industry", "close", "high", "low", "vol", "amount"]]
