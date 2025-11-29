import pandas as pd


# =============== 规则 1：突破箱体 / 接近历史新高 ===============

def breakout_signal(price_df: pd.DataFrame, n: int = 55) -> bool:
    """
    Close > Highest(High, n) * 1.01
    """
    if price_df is None or len(price_df) < n + 1:
        return False
    window = price_df.tail(n + 1)
    highest = window["high"].iloc[:-1].max()
    last_close = window["close"].iloc[-1]
    return bool(last_close > highest * 1.01)


def near_all_time_high(price_df: pd.DataFrame, tolerance: float = 0.98) -> bool:
    """
    Close >= HistoricalHigh * 0.98
    """
    if price_df is None or price_df.empty:
        return False
    all_high = price_df["high"].max()
    last_close = price_df["close"].iloc[-1]
    return bool(last_close >= all_high * tolerance)


# =============== 规则 2：放量异动 ===============

def volume_signal(price_df: pd.DataFrame, ma_window: int = 20) -> bool:
    """
    Volume > MA(20) * 1.5
    且 最近 3 日 Volume > MA(20)
    """
    if price_df is None or len(price_df) < ma_window + 3:
        return False
    df = price_df.copy()
    df["vol_ma"] = df["volume"].rolling(ma_window).mean()
    last3 = df.tail(3)
    cond_today = last3["volume"].iloc[-1] > last3["vol_ma"].iloc[-1] * 1.5
    cond_3days = (last3["volume"] > last3["vol_ma"]).all()
    return bool(cond_today and cond_3days)


# =============== 规则 4：主力资金流入 ===============

def money_flow_signal(flow_df: pd.DataFrame) -> bool:
    """
    连续 3 日 main_net_in > 0 且 最近一天 main_net_ratio > 20
    """
    if flow_df is None or len(flow_df) < 3:
        return False
    df = flow_df.sort_values("date").tail(3)
    cond_3 = (df["main_net_in"] > 0).all()
    last_ratio = df["main_net_ratio"].iloc[-1]
    cond_ratio = last_ratio > 20
    return bool(cond_3 and cond_ratio)


# =============== 规则 5：RS 相对强弱 ===============

def calc_rs(
    stock_price: pd.DataFrame,
    index_price: pd.DataFrame,
    lookback: int = 20,
) -> float | None:
    """
    RS = 股票最近 20 日涨幅 / 指数最近 20 日涨幅
    """
    if (
        stock_price is None
        or index_price is None
        or len(stock_price) < lookback + 1
        or len(index_price) < lookback + 1
    ):
        return None

    s = stock_price["close"].iloc[-lookback - 1 :]
    i = index_price["close"].iloc[-lookback - 1 :]

    stock_ret = s.iloc[-1] / s.iloc[0] - 1
    index_ret = i.iloc[-1] / i.iloc[0] - 1
    if index_ret == 0:
        return None
    return float(stock_ret / index_ret)
