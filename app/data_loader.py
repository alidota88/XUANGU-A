from .cache_manager import load_cache, save_cache
# app/data_loader.py

import os
from datetime import datetime, timedelta

import pandas as pd
import tushare as ts

from .config import BENCHMARK_INDEX, TUSHARE_TOKEN

# 兼容旧变量名
TS_TOKEN = TUSHARE_TOKEN or os.getenv("TS_TOKEN", "")


def get_pro():
    if not TS_TOKEN:
        raise Exception("环境变量 TUSHARE_TOKEN 未设置")
    ts.set_token(TS_TOKEN)
    return ts.pro_api()


def _load_cached_df(name: str) -> pd.DataFrame | None:
    data = load_cache(name)
    if not data:
        return None
    if isinstance(data, dict) and "data" in data:
        data = data.get("data")
    if not data:
        return None
    return pd.DataFrame(data)


def _save_cached_df(name: str, df: pd.DataFrame):
    if df is None or df.empty:
        return
    save_cache(name, df.to_dict(orient="records"))


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
    today = datetime.today().strftime("%Y%m%d")

    cache = load_cache("stock_list.json")
    if isinstance(cache, dict) and cache.get("date") == today:
        cached_data = cache.get("data", [])
        if cached_data:
            return pd.DataFrame(cached_data)

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

    save_cache("stock_list.json", {"date": today, "data": df.to_dict(orient="records")})
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


def _get_start_date(days: int) -> str:
    return (datetime.today() - timedelta(days=days)).strftime("%Y%m%d")


def get_index_history(code: str | None = None, days: int = 250) -> pd.DataFrame:
    """
    获取指数历史行情，用于 RS 计算
    返回字段至少包含: date, close, high, low, volume
    """
    if code is None:
        code = BENCHMARK_INDEX

    latest = get_latest_trade_date()
    start = _get_start_date(days)
    cache_name = f"index_{code}_{start}_{latest}.json"
    cache_df = _load_cached_df(cache_name)
    if cache_df is not None and not cache_df.empty:
        return cache_df

    pro = get_pro()
    df = pro.index_daily(ts_code=code, start_date=start, end_date=latest)
    if df.empty:
        raise Exception(f"index_daily({code}) 返回为空")

    df = df.sort_values("trade_date")
    df.rename(columns={"trade_date": "date", "vol": "volume"}, inplace=True)
    _save_cached_df(cache_name, df)
    return df[["date", "close", "high", "low", "volume"]]


def get_stock_history(code: str, days: int = 300) -> pd.DataFrame:
    """
    获取个股日线行情
    返回字段至少包含: date, close, high, low, volume
    """
    latest = get_latest_trade_date()
    start = _get_start_date(days)
    cache_name = f"price_{code}_{start}_{latest}.json"
    cache_df = _load_cached_df(cache_name)
    if cache_df is not None and not cache_df.empty:
        return cache_df

    pro = get_pro()
    df = pro.daily(ts_code=code, start_date=start, end_date=latest)
    if df.empty:
        return pd.DataFrame()

    df = df.sort_values("trade_date")
    df.rename(columns={"trade_date": "date", "vol": "volume"}, inplace=True)
    _save_cached_df(cache_name, df)
    return df[["date", "close", "high", "low", "volume"]]


def get_stock_moneyflow(code: str, days: int = 20) -> pd.DataFrame:
    """
    获取个股资金流，计算主力净流入及占比
    返回字段至少包含: date, main_net_in, main_net_ratio
    """
    latest = get_latest_trade_date()
    start = _get_start_date(days)
    cache_name = f"money_{code}_{start}_{latest}.json"
    cache_df = _load_cached_df(cache_name)
    if cache_df is not None and not cache_df.empty:
        return cache_df

    pro = get_pro()
    df = pro.moneyflow(ts_code=code, start_date=start, end_date=latest)
    if df.empty:
        return pd.DataFrame()

    df["main_net_in"] = (
        df["buy_elg_amount"].fillna(0)
        + df["buy_lg_amount"].fillna(0)
        - df["sell_elg_amount"].fillna(0)
        - df["sell_lg_amount"].fillna(0)
    )

    total_turnover = (
        df["buy_sm_amount"].fillna(0)
        + df["sell_sm_amount"].fillna(0)
        + df["buy_md_amount"].fillna(0)
        + df["sell_md_amount"].fillna(0)
        + df["buy_lg_amount"].fillna(0)
        + df["sell_lg_amount"].fillna(0)
        + df["buy_elg_amount"].fillna(0)
        + df["sell_elg_amount"].fillna(0)
    )

    with pd.option_context("mode.use_inf_as_na", True):
        ratio = df["main_net_in"] / total_turnover.replace({0: pd.NA}) * 100
    df["main_net_ratio"] = ratio.fillna(0)

    df = df.sort_values("trade_date")
    df.rename(columns={"trade_date": "date"}, inplace=True)
    df_res = df[["date", "main_net_in", "main_net_ratio"]].copy()
    _save_cached_df(cache_name, df_res)
    return df_res
