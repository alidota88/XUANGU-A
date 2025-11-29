import traceback

import numpy as np
import pandas as pd

from .config import BREAKOUT_N, MIN_SCORE, MIN_RS
from .data_loader import (
    get_index_universe,
    get_index_history,
    get_stock_history,
    get_stock_moneyflow,
)
from .signals import (
    breakout_signal,
    volume_signal,
    money_flow_signal,
    calc_rs,
)
from .scoring import calc_total_score


def run_selection() -> pd.DataFrame:
    """
    选股主流程（Tushare 版）：
    - 选股宇宙：指数成分股（默认沪深300）
    - 对每只股票计算：
        * 突破箱体（规则1）
        * 放量（规则2）
        * 主力资金流向（规则4）
        * RS 相对强弱（规则5）
    - 以“行业”为板块：
        * 行业 5 日平均涨幅
        * 行业 5 日主力净流入总和
        * 各行业做百分位排名，取前 20% 为主线
    - 综合评分 ≥ MIN_SCORE & 严格过滤条件
    """

    # === 1. 选股宇宙 & 指数历史 ===
    universe = get_index_universe()
    if universe.empty:
        print("[selector] universe is empty.")
        return pd.DataFrame()

    index_df = get_index_history(days=250)
    if index_df.empty:
        print("[selector] index history is empty.")
        return pd.DataFrame()

    stock_rows = []

    # === 2. 遍历宇宙中每一只股票，先算个股指标 ===
    for _, u in universe.iterrows():
        ts_code = u["code"]
        name = u["name"]
        industry = u.get("industry", None)

        if not isinstance(industry, str) or industry.strip() == "":
            # 没有行业信息的就跳过
            continue

        try:
            price_df = get_stock_history(ts_code)
            if price_df is None or price_df.empty or len(price_df) < BREAKOUT_N + 20:
                continue

            flow_df = get_stock_moneyflow(ts_code)
            if flow_df is None or flow_df.empty:
                continue

            # 最近 5 日涨幅（个股）——用于行业聚合
            if len(price_df) < 6:
                continue
            last6 = price_df.tail(6)
            p0 = last6["close"].iloc[0]
            p1 = last6["close"].iloc[-1]
            stock_ret_5d = p1 / p0 - 1

            # 最近 5 日主力净流入（个股）——用于行业聚合
            flow_tail5 = flow_df.sort_values("date").tail(5)
            stock_main_5d = flow_tail5["main_net_in"].sum()

            # 单股信号
            cond_breakout = breakout_signal(price_df, n=BREAKOUT_N)
            cond_volume = volume_signal(price_df)
            cond_money = money_flow_signal(flow_df)

            # RS
            rs_val = calc_rs(price_df, index_df, lookback=20)
            if rs_val is None:
                continue

            stock_rows.append(
                {
                    "code": ts_code,
                    "name": name,
                    "industry": industry,
                    "ret_5d": stock_ret_5d,
                    "main_5d": stock_main_5d,
                    "cond_breakout": cond_breakout,
                    "cond_volume": cond_volume,
                    "cond_money": cond_money,
                    "RS": rs_val,
                }
            )

        except Exception as e:
            print(f"[selector] error on {ts_code} {name}: {e}")
            traceback.print_exc()
            continue

    if not stock_rows:
        print("[selector] no stock metrics computed.")
        return pd.DataFrame()

    metrics = pd.DataFrame(stock_rows)

    # === 3. 行业维度的主线度计算（规则 3 & 6） ===
    # 行业 5 日平均涨幅
    industry_ret = metrics.groupby("industry")["ret_5d"].mean().rename("ind_ret_5d")
    # 行业 5 日主力净流入总和
    industry_flow = (
        metrics.groupby("industry")["main_5d"].sum().rename("ind_main_5d")
    )

    sector_df = pd.concat([industry_ret, industry_flow], axis=1).reset_index()
    # 百分位排名
    sector_df["up_rank_pct"] = sector_df["ind_ret_5d"].rank(pct=True)
    sector_df["flow_rank_pct"] = sector_df["ind_main_5d"].rank(pct=True)
    # 主线板块条件：涨幅、资金流都在前 20% 且资金净流入 > 0
    sector_df["is_main_sector"] = (
        (sector_df["up_rank_pct"] > 0.8)
        & (sector_df["flow_rank_pct"] > 0.8)
        & (sector_df["ind_main_5d"] > 0)
    )

    # 回写回每只股票
    metrics = metrics.merge(sector_df, on="industry", how="left")

    # 行业主线度 = (涨幅百分位 + 资金流百分位)/2
    metrics["sector_score"] = (
        metrics["up_rank_pct"] + metrics["flow_rank_pct"]
    ) / 2.0

    # === 4. 单股严格过滤 + 综合评分（规则 7 & 最终条件） ===
    results = []

    for _, row in metrics.iterrows():
        # 行业必须是主线
        if not bool(row.get("is_main_sector", False)):
            continue

        # 单股条件
        if not row["cond_breakout"]:
            continue
        if not row["cond_volume"]:
            continue
        if not row["cond_money"]:
            continue

        # RS > MIN_RS
        if row["RS"] <= MIN_RS:
            continue

        # 综合评分
        total_score = calc_total_score(
            breakout_ok=row["cond_breakout"],
            volume_ok=row["cond_volume"],
            money_flow_ok=row["cond_money"],
            sector_score=row["sector_score"],
        )
        if total_score < MIN_SCORE:
            continue

        results.append(
            {
                "code": row["code"],
                "name": row["name"],
                "industry": row["industry"],
                "RS": round(row["RS"], 2),
                "sector_up_rank": round(row["up_rank_pct"], 3),
                "sector_flow_rank": round(row["flow_rank_pct"], 3),
                "sector_ret_5d": round(row["ind_ret_5d"], 4),
                "sector_main_5d": float(row["ind_main_5d"]),
                "score": round(total_score, 2),
            }
        )

    if not results:
        print("[selector] no stock passes strict filters.")
        return pd.DataFrame()

    df_res = pd.DataFrame(results)
    df_res = df_res.sort_values("score", ascending=False).reset_index(drop=True)
    return df_res
