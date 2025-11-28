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
    pro = get_pro()

    try:
        df = pro.stock_basic(exchange='', list_status='L',
                             fields='ts_code,name,area,industry,list_date')
    except Exception as e:
        print("[data_loader] stock_basic 调用失败，使用最小字段兜底方案", e)
        df = pro.stock_basic(exchange='', list_status='L',
                             fields='ts_code,name,list_date')
        df["industry"] = "未知"

    # 强制 industry 存在
    if "industry" not in df.columns:
        df["industry"] = "未知"

    df.rename(columns={"ts_code": "code"}, inplace=True)
    return df



# ================== 成交额前 N 名（EOD，用日线 amount 排序） ==================

def get_top_liquidity_stocks(top_n=500):
    pro = get_pro()
    trade_date = get_latest_trade_date()

    print(f"[data_loader] 获取 {trade_date} 全市场日线数据用于成交额排序")

    daily = pro.daily(trade_date=trade_date)

    if daily.empty:
        raise Exception("Tushare daily 返回为空")

    stock_list = get_stock_list()

    # 保证 industry 字段存在
    stock_list["industry"] = stock_list["industry"].fillna("未知")

    # merge
    df = daily.merge(stock_list, left_on="ts_code", right_on="code", how="left")

    # 再兜底
    df["industry"] = df["industry"].fillna("未知")
    df["name"] = df["name"].fillna("未知")

    # 处理 amount
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])
    df = df.sort_values("amount", ascending=False).head(top_n)

    return df[["code", "name", "industry", "close", "high", "low", "vol", "amount"]]



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
