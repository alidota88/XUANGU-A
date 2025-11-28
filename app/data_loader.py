from .cache_manager import load_cache, save_cache
import os
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import tushare as ts

from .config import TUSHARE_TOKEN, BENCHMARK_INDEX

# ================== 基础设置 ==================

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

_pro = None  # 全局 Tushare pro 实例


def get_pro():
    """
    懒加载 Tushare pro 对象，只初始化一次。
    """
    global _pro
    if _pro is None:
        if not TUSHARE_TOKEN:
            raise RuntimeError("TUSHARE_TOKEN 未设置，请在 Railway 环境变量里配置。")
        ts.set_token(TUSHARE_TOKEN)
        _pro = ts.pro_api()
    return _pro


def _csv_path(name: str) -> str:
    return os.path.join(DATA_DIR, name)


# ================== 交易日工具 ==================

def get_latest_trade_date() -> str:
    """
    获取最近一个交易日（格式: YYYYMMDD）
    """
    pro = get_pro()
    today = datetime.today().strftime("%Y%m%d")
    start = (datetime.today() - timedelta(days=10)).strftime("%Y%m%d")
    cal = pro.trade_cal(exchange="SSE", start_date=start, end_date=today, is_open="1")
    if cal.empty:
        raise RuntimeError("无法获取交易日历")
    return cal["cal_date"].iloc[-1]


# ================== 股票基础信息 ==================

def get_stock_list():
    cached = load_cache("stock_list.json")
    if cached:
        return pd.DataFrame(cached)

    ... # 调用 Tushare

    save_cache("stock_list.json", df.to_dict(orient="records"))
    return df




# ================== 成交额前 N 名（EOD，用日线 amount 排序） ==================

    cache_name = f"daily_{trade_date}.json"
    cached = load_cache(cache_name)
    if cached:
        daily = pd.DataFrame(cached)
    else:
        daily = pro.daily(trade_date=trade_date)
        save_cache(cache_name, daily.to_dict(orient="records"))



# ================== 指数行情（用于 RS） ==================

def get_index_history(days: int = 250) -> pd.DataFrame:
    """
    获取基准指数最近 N 日行情，用于计算 RS。
    """
    pro = get_pro()
    end_date = get_latest_trade_date()
    start_date = (datetime.strptime(end_date, "%Y%m%d") - timedelta(days=days * 2)).strftime("%Y%m%d")

    df = pro.index_daily(ts_code=BENCHMARK_INDEX, start_date=start_date, end_date=end_date)
    if df.empty:
        raise RuntimeError("无法获取指数行情 index_daily")

    df = df.sort_values("trade_date")
    df = df.rename(
        columns={
            "trade_date": "date",
        }
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


# ================== 个股日线 ==================

def get_stock_history(code: str, days: int = 300) -> pd.DataFrame:
    """
    获取单只股票最近 N 日日线数据。
    code 为 ts_code，例如 '000001.SZ'
    """
    pro = get_pro()
    end_date = get_latest_trade_date()
    start_date = (datetime.strptime(end_date, "%Y%m%d") - timedelta(days=days * 2)).strftime("%Y%m%d")

    df = pro.daily(ts_code=code, start_date=start_date, end_date=end_date)
    if df.empty:
        return pd.DataFrame()

    df = df.sort_values("trade_date")
    df = df.rename(
        columns={
            "trade_date": "date",
            "vol": "volume",
        }
    )
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "open", "high", "low", "close", "volume", "amount"]]


# ================== 个股资金流 ==================

def get_stock_moneyflow(code: str, days: int = 20) -> pd.DataFrame:
    """
    获取单只股票最近 N 日资金流数据（moneyflow）。
    """
    pro = get_pro()
    end_date = get_latest_trade_date()
    start_date = (datetime.strptime(end_date, "%Y%m%d") - timedelta(days=days * 2)).strftime("%Y%m%d")

    df = pro.moneyflow(ts_code=code, start_date=start_date, end_date=end_date)
    if df.empty:
        return pd.DataFrame()

    df = df.sort_values("trade_date")
    df = df.rename(columns={"trade_date": "date"})
    df["date"] = pd.to_datetime(df["date"])

    # 资金流：使用 net_mf_amount 作为“主力净流入金额”
    # 资金流占比：用 net_mf_amount / amount 粗略近似（金额比重）
    df["main_net_in"] = df["net_mf_amount"]
    # 避免除零错误
    df["main_net_ratio"] = df["net_mf_amount"] / (df["amount"].replace(0, pd.NA)) * 100
    df["main_net_ratio"] = df["main_net_ratio"].fillna(0)

    return df[["date", "main_net_in", "main_net_ratio"]]
