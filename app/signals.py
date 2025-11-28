import numpy as np
import pandas as pd


# =============== 规则 1：突破箱体 / 接近历史新高 ===============

def breakout_signal(price_df: pd.DataFrame, n: int = 55) -> bool:
    """
    Close > Highest(High, n) * 1.01
    """
    if len(price_df) < n + 1:
        return False
    window = price_df.tail(n + 1)
    highest = window["high"].iloc[:-1].max()
    last_close = window["close"].iloc[-1]
    return last_close > highest * 1.01


def near_all_time_high(price_df: pd.DataFrame, tolerance: float = 0.98) -> bool:
    """
    Close >= HistoricalHigh * 0.98
    """
    all_high = price_df["high"].max()
    last_close = price_df["close"].iloc[-1]
    return last_close >= all_high * tolerance


# =============== 规则 2：放量异动 ===============

def volume_signal(price_df: pd.DataFrame, ma_window: int = 20) -> bool:
    """
    Volume > MA(20) * 1.5
    连续 3 日成交量 > MA(20)
    """
    if len(price_df) < ma_window + 3:
        return False
    df = price_df.copy()
    df["vol_ma20"] = df["volume"].rolling(ma_window).mean()
    last3 = df.tail(3)
    cond_today = last3["volume"].iloc[-1] > last3["vol_ma20"].iloc[-1] * 1.5
    cond_3days = (last3["volume"] > last3["vol_ma20"]).all()
    return bool(cond_today and cond_3days)


# =============== 规则 4：主力资金流入 ===============

def money_flow_signal(flow_df: pd.DataFrame) -> bool:
    """
    连续 3 日主力净流入 > 0
    主力资金占比 > 20%（最近一天）
    """
    if flow_df is None or len(flow_df) < 3:
        return False
    last3 = flow_df.sort_values("date").tail(3)
    cond_3_days = (last3["main_net_in"] > 0).all()
    last_ratio = last3["main_net_ratio"].iloc[-1]
    cond_ratio = last_ratio > 20
    return bool(cond_3_days and cond_ratio)


# =============== 规则 5：RS 相对强弱（去弱留强） ===============

def calc_rs(
    stock_price: pd.DataFrame,
    index_price: pd.DataFrame,
    lookback: int = 20,
) -> float | None:
    """
    RS = 股票最近 20 日涨幅 / 指数最近 20 日涨幅
    > 0.7 即认为强于大盘
    """
    if len(stock_price) < lookback + 1 or len(index_price) < lookback + 1:
        return None

    s = stock_price["close"].iloc[-lookback - 1 :]
    i = index_price["close"].iloc[-lookback - 1 :]

    stock_ret = s.iloc[-1] / s.iloc[0] - 1
    index_ret = i.iloc[-1] / i.iloc[0] - 1
    if index_ret == 0:
        return None
    return float(stock_ret / index_ret)


# =============== 规则 3 & 6：板块主线度（基于板块资金流 DataFrame） ===============

def compute_sector_scores(sector_df: pd.DataFrame) -> pd.DataFrame:
    """
    输入: stock_sector_fund_flow_rank 返回的 DataFrame
    输出: 增加两列：
        - up_rank_pct: 涨跌幅百分位排名
        - flow_rank_pct: 主力净流入百分位排名
    """
    df = sector_df.copy()

    # 转成数值
    if "涨跌幅" in df.columns:
        df["涨跌幅_num"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
    else:
        df["涨跌幅_num"] = 0.0

    if "主力净流入-净额" in df.columns:
        df["main_net_in"] = pd.to_numeric(df["主力净流入-净额"], errors="coerce")
    else:
        df["main_net_in"] = 0.0

    df["up_rank_pct"] = df["涨跌幅_num"].rank(pct=True)
    df["flow_rank_pct"] = df["main_net_in"].rank(pct=True)

    return df


def mark_main_sectors(sector_scores: pd.DataFrame) -> pd.DataFrame:
    """
    标记“主线板块”：
    - 最近 5 日板块涨幅前 20% （up_rank_pct > 0.8）
    - 最近 5 日主力净流入前 20%（flow_rank_pct > 0.8）
    - 主力净流入 > 0
    """
    df = sector_scores.copy()
    df["is_main_sector"] = (
        (df["up_rank_pct"] > 0.8)
        & (df["flow_rank_pct"] > 0.8)
        & (df["main_net_in"] > 0)
    )
    return df
