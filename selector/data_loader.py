import tushare as ts
import pandas as pd
from datetime import datetime, timedelta

# 初始化 tushare
import os
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN")
ts.set_token(TUSHARE_TOKEN)
pro = ts.pro_api()


def get_trade_dates(n=60):
    """获取最近 n 个交易日"""
    dates = []
    d = datetime.now().date()
    while len(dates) < n:
        ds = d.strftime('%Y%m%d')
        df = pro.daily(trade_date=ds)
        if not df.empty:
            dates.append(ds)
        d -= timedelta(days=1)
    return list(reversed(dates))


def get_daily(trade_date):
    """获取某日 A 股行情"""
    return pro.daily(trade_date=trade_date)


def get_moneyflow(trade_date):
    """获取某日主力资金流"""
    return pro.moneyflow(trade_date=trade_date)


def get_index_history(start, end):
    """获取上证指数，用于 RS 计算"""
    return pro.index_daily(ts_code='000001.SH', start_date=start, end_date=end)


def get_stock_basic():
    """一次性获取所有股票基础信息"""
    df = pro.stock_basic(exchange='', list_status='L',
                         fields='ts_code,name,industry,list_date')
    return df
