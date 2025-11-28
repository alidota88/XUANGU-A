import os
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

from .config import BENCHMARK_INDEX

# 缓存目录：app/data
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)


# =============== 工具函数 ===============

def _csv_path(name: str) -> str:
    return os.path.join(DATA_DIR, name)


# =============== 可复用静态数据：股票列表 ===============

def get_stock_list(force_update: bool = False) -> pd.DataFrame:
    """
    获取 A 股列表，并缓存到 data/stock_list.csv
    """
    path = _csv_path("stock_list.csv")
    if not force_update and os.path.exists(path):
        df = pd.read_csv(path, dtype={"code": str})
        return df

    df = ak.stock_info_a_code_name()  # 接口: stock_info_a_code_name
    # 统一字段
    df = df.rename(columns={"code": "code", "name": "name"})
    df["code"] = df["code"].astype(str)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return df


# =============== 可复用静态数据：行业成分 ===============

def get_industry_mapping(force_update: bool = False) -> pd.DataFrame:
    """
    使用东方财富行业板块：
    - ak.stock_board_industry_name_em() 获取所有行业
    - ak.stock_board_industry_cons_em(symbol=行业名) 获取成份股
    结果缓存到 data/industry_map.csv
    """
    path = _csv_path("industry_map.csv")
    if not force_update and os.path.exists(path):
        return pd.read_csv(path, dtype={"code": str})

    # 行业列表
    industry_df = ak.stock_board_industry_name_em()  # 板块名称、板块代码等
    rows = []
    for _, row in industry_df.iterrows():
        industry_name = row["板块名称"]
        try:
            cons_df = ak.stock_board_industry_cons_em(symbol=industry_name)
        except Exception as e:
            print(f"[industry] 获取板块成份失败: {industry_name} - {e}")
            continue

        for _, c in cons_df.iterrows():
            code = str(c["代码"])
            rows.append({"code": code, "industry": industry_name})

    map_df = pd.DataFrame(rows).drop_duplicates(subset=["code"])
    map_df.to_csv(path, index=False, encoding="utf-8-sig")
    return map_df


# =============== 每天更新的数据：板块资金流（行业维度） ===============

def get_sector_fund_flow_rank() -> pd.DataFrame:
    """
    板块资金流排名（行业资金流，5日）
    接口: stock_sector_fund_flow_rank(indicator="5日", sector_type="行业资金流")
    """
    df = ak.stock_sector_fund_flow_rank(
        indicator="5日",
        sector_type="行业资金流"
    )
    # 统一一下列名，方便后面用
    # 一般会有: "板块名称", "主力净流入-净额", "涨跌幅", "主力净流入-净占比" 等
    return df


# =============== 每天更新的数据：指数历史行情 ===============

def get_index_history(days: int = 250) -> pd.DataFrame:
    """
    获取沪深 300 等指数最近 N 天，用于计算 RS
    接口: stock_zh_index_daily
    """
    df = ak.stock_zh_index_daily(symbol=BENCHMARK_INDEX)
    df = df.tail(days).reset_index(drop=True)
    # 列一般为: date, open, close, high, low, volume, amount
    return df


# =============== 每天更新的数据：个股行情 ===============

def get_stock_history(
    code: str,
    start_date: str | None = None,
    adjust: str = "qfq"
) -> pd.DataFrame:
    """
    获取单只股票历史行情（日线）
    接口: stock_zh_a_hist
    """
    if start_date is None:
        # 默认取最近 400 天
        start_date = (datetime.today() - timedelta(days=400)).strftime("%Y%m%d")

    df = ak.stock_zh_a_hist(
        symbol=code,
        period="daily",
        start_date=start_date,
        end_date=datetime.today().strftime("%Y%m%d"),
        adjust=adjust,
    )

    # 中文列名转成英文，方便后面统一处理
    df = df.rename(
        columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "涨跌幅": "pct_chg",
        }
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


# =============== 每天更新的数据：实时快照（用来选前 MAX_STOCKS_PER_DAY） ===============

def get_realtime_spot() -> pd.DataFrame:
    """
    东方财富 A 股实时行情
    接口: stock_zh_a_spot_em
    """
    df = ak.stock_zh_a_spot_em()
    # 列通常包括: "代码", "名称", "最新价", "涨跌幅", "成交额", ...
    df = df.rename(columns={"代码": "code", "名称": "name"})
    df["code"] = df["code"].astype(str)
    return df


# =============== 每天更新的数据：个股资金流 ===============

def _code_to_market(code: str) -> str:
    """
    简单规则：
    - 6xxxxxx -> 上交所 sh
    - 其他 -> 深交所 sz
    """
    return "sh" if code.startswith("6") else "sz"


def get_stock_fund_flow(code: str) -> pd.DataFrame:
    """
    获取个股资金流，近 100 个交易日
    接口: stock_individual_fund_flow(stock="000651", market="sz")
    """
    market = _code_to_market(code)
    df = ak.stock_individual_fund_flow(stock=code, market=market)
    # 列一般包括: 日期, 主力净流入-净额, 主力净流入-净占比, 收盘价, 涨跌幅 等
    df = df.rename(
        columns={
            "日期": "date",
            "主力净流入-净额": "main_net_in",
            "主力净流入-净占比": "main_net_ratio",
        }
    )
    df["date"] = pd.to_datetime(df["date"])
    return df
