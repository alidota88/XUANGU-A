import pandas as pd
import numpy as np


def calc_breakout(hist_df):
    """55 日突破箱体"""
    if len(hist_df) < 56:
        high55 = hist_df['high'][:-1].max()
    else:
        high55 = hist_df['high'].iloc[-56:-1].max()

    today_close = hist_df['close'].iloc[-1]
    return today_close > high55 * 1.01


def calc_volume_spike(hist_df):
    """放量：当日成交量 > MA20 * 1.5"""
    if len(hist_df) < 21:
        ma20 = hist_df['vol'][:-1].mean()
    else:
        ma20 = hist_df['vol'].iloc[-21:-1].mean()

    today_vol = hist_df['vol'].iloc[-1]
    return today_vol > ma20 * 1.5


def calc_rs(stock_ret, market_ret):
    """相对强弱 RS > 0.7"""
    if market_ret is None or abs(market_ret) < 1e-6:
        return True
    return (stock_ret / market_ret) >= 0.7
