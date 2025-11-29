import os
from datetime import datetime, timedelta

import pandas as pd
import tushare as ts

from .config import TUSHARE_TOKEN, BENCHMARK_INDEX, INDEX_UNIVERSE

# =============== 初始化 Tushare ===============
if not TUSHARE_TOKEN:
    raise RuntimeError("TUSHARE_TOKEN 未设置，请在 Railway 环境变量中配置。")

ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()

# =============== 缓存目录 ===============
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)


def _csv_path(name: str) -> str:
    return os.path.join(DATA_DIR, name)


# =============== 交易日工具 ===============

def get_last_trade_date() -> str:
    """
    获取最近一个交易日（上交所）YYYYMMDD 字符串
    """
    today = datetime.today()
    start = (today - timedelta(days=10)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    cal = pro.trade_cal(exchange="SSE", start_date=start, end_date=end, is_open="1")
    last = cal["cal_date"].max()
    return str(last)


# =============== 股票基础信息 ===============

def get_stock_basic(force_update: bool = False) -> pd.DataFrame:
    """
    获取全市场股票基础信息，并缓存到 data/stock_basic.csv
    字段：ts_code, symbol, name, area, industry, market, list_date
    """
    path = _csv_path("stock_basic.csv")
    if not force_update and os.path.exists(path):
        return pd.read_csv(path, dtype={"ts_code": str, "symbol": str})

    df = pro.stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,symbol,name,area,industry,market,list_date",
    )
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return df


# =============== 指数成分股（选股宇宙） ===============

def get_index_universe(force_update: bool = False) -> pd.DataFrame:
    """
    获取指数成分股列表，例如沪深300：INDEX_UNIVERSE = "000300.SH"
    返回列：code(=ts_code), name, industry
    """
    path = _csv_path(f"universe_{INDEX_UNIVERSE.replace('.', '')}.csv")
    if not force_update and os.path.exists(path):
        return pd.read_csv(path, dtype={"code": str})

    last_trade = get_last_trade_date()
    weight_df = pro.index_weight(
        index_code=INDEX_UNIVERSE,
        trade_date=last_trade,
    )
    # weight_df: index_code, con_code, trade_date, weight
    basic_df = get_stock_basic()
    merged = weight_df.merge(
        basic_df,
        left_on="con_code",
        right_on="ts_code",
        how="left",
    )

    merged["code"] = merged["ts_code"]
    universe = merged[["code", "name", "industry"]].dropna(subset=["code"])

    universe.to_csv(path, index=False, encoding="utf-8-sig")
    return universe


# =============== 指数历史行情 ===============

def get_index_history(days: int = 300) -> pd.DataFrame:
    """
    指数日线历史，用于计算 RS
    """
    end = datetime.today()
    start = (end - timedelta(days=days * 2)).strftime("%Y%m%d")

    df = pro.index_daily(
        ts_code=BENCHMARK_INDEX,
        start_date=start,
        end_date=end.strftime("%Y%m%d"),
    )
    if df.empty:
        return df

    # Tushare 默认按日期从近到远，需要反转一下
    df = df.sort_values("trade_date")
    df = df.tail(days)

    df = df.rename(
        columns={
            "trade_date": "date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "vol": "volume",
            "amount": "amount",
        }
    )
    df["date"] = pd.to_datetime(df["date"])
    return df.reset_index(drop=True)


# =============== 个股历史行情 ===============

def get_stock_history(
    ts_code: str,
    start_date: str | None = None,
) -> pd.DataFrame:
    """
    获取单只股票历史日线
    """
    if start_date is None:
        start_date = (datetime.today() - timedelta(days=400)).strftime("%Y%m%d")
    end_date = datetime.today().strftime("%Y%m%d")

    df = pro.daily(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
    )
    if df.empty:
        return df

    df = df.sort_values("trade_date")

    df = df.rename(
        columns={
            "trade_date": "date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "vol": "volume",
            "amount": "amount",
        }
    )
    df["date"] = pd.to_datetime(df["date"])
    return df.reset_index(drop=True)


# =============== 个股资金流（主力净流入） ===============

def get_stock_moneyflow(ts_code: str, days: int = 60) -> pd.DataFrame:
    """
    Tushare moneyflow:
      ts_code, trade_date, buy_sm_vol, ..., net_mf_vol, net_mf_amount, net_mf_ratio, ...
    我们用：
      main_net_in   := net_mf_amount
      main_net_ratio := net_mf_ratio
    """
    end = datetime.today()
    start = (end - timedelta(days=days * 2)).strftime("%Y%m%d")

    df = pro.moneyflow(
        ts_code=ts_code,
        start_date=start,
        end_date=end.strftime("%Y%m%d"),
    )
    if df.empty:
        return df

    df = df.sort_values("trade_date")
    df = df.tail(days)

    # 有的字段名字可能不同，这里做一次兼容
    if "net_mf_amount" in df.columns:
        main_in = df["net_mf_amount"]
    else:
        # 兜底：如果没有 net_mf_amount，就用 0
        main_in = 0

    if "net_mf_ratio" in df.columns:
        main_ratio = df["net_mf_ratio"]
    else:
        main_ratio = 0

    df = df.assign(
        main_net_in=main_in,
        main_net_ratio=main_ratio,
    )
    df = df.rename(columns={"trade_date": "date"})
    df["date"] = pd.to_datetime(df["date"])
    return df.reset_index(drop=True)
