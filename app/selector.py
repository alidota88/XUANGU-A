import traceback

import numpy as np
import pandas as pd

from .config import BREAKOUT_N, MAX_STOCKS_PER_DAY
from .data_loader import (
    get_stock_list,
    get_industry_mapping,
    get_sector_fund_flow_rank,
    get_index_history,
    get_stock_history,
    get_realtime_spot,
    get_stock_fund_flow,
)
from .signals import (
    breakout_signal,
    volume_signal,
    money_flow_signal,
    calc_rs,
    compute_sector_scores,
    mark_main_sectors,
)
from .scoring import calc_total_score


def run_selection() -> pd.DataFrame:
    """
    主选股流程：
    - 返回符合全部严格条件的股票列表 DataFrame
    """
    # === 1. 静态数据（缓存） ===
    stock_list = get_stock_list()
    industry_map = get_industry_mapping()
    stock_base = stock_list.merge(industry_map, on="code", how="left")

    # === 2. 实时行情：选前 N 只成交额最大的股票，作为候选池 ===
    spot_df = get_realtime_spot()
    spot_df = spot_df.merge(stock_base, on=["code", "name"], how="left")
    if "成交额" in spot_df.columns:
        spot_df["成交额_num"] = pd.to_numeric(spot_df["成交额"], errors="coerce")
    else:
        spot_df["成交额_num"] = 0.0

    spot_df = spot_df.sort_values("成交额_num", ascending=False)
    candidates = spot_df.head(MAX_STOCKS_PER_DAY).copy()

    # === 3. 板块资金流 → 主线板块 ===
    sector_raw = get_sector_fund_flow_rank()
    sector_scores = compute_sector_scores(sector_raw)
    sector_marked = mark_main_sectors(sector_scores)

    # 字典：板块名称 -> (up_rank_pct, flow_rank_pct, is_main_sector)
    sector_dict = {}
    for _, row in sector_marked.iterrows():
        name = row["板块名称"]
        sector_dict[name] = {
            "up_rank_pct": row["up_rank_pct"],
            "flow_rank_pct": row["flow_rank_pct"],
            "is_main_sector": bool(row["is_main_sector"]),
            "main_net_in": row["main_net_in"],
        }

    # === 4. 指数行情（用于 RS） ===
    index_df = get_index_history(days=250)

    results = []

    for _, row in candidates.iterrows():
        code = str(row["code"])
        name = row["name"]
        industry = row.get("industry", None)

        try:
            # 如果没有行业归属，直接跳过（无法判断板块主线度）
            if not isinstance(industry, str) or industry.strip() == "":
                continue

            sector_info = sector_dict.get(industry)
            if not sector_info:
                # 该行业不在板块资金流列表中
                continue

            # 板块是否主线：最近 5 日涨幅 & 主力净流入都在前 20%
            is_main_sector = sector_info["is_main_sector"]
            if not is_main_sector:
                continue

            # 板块综合得分（0-1）：涨幅 rank + 资金流 rank 的平均值
            sector_score = float(
                (sector_info["up_rank_pct"] + sector_info["flow_rank_pct"]) / 2.0
            )

            # === 单股行情 & 资金流 ===
            price_df = get_stock_history(code)
            flow_df = get_stock_fund_flow(code)

            if price_df is None or len(price_df) < BREAKOUT_N + 5:
                continue

            # --- 信号 1：突破箱体 ---
            cond_breakout = breakout_signal(price_df, n=BREAKOUT_N)

            # --- 信号 2：放量 ---
            cond_volume = volume_signal(price_df)

            # --- 信号 4：主力资金流入 ---
            cond_money = money_flow_signal(flow_df)

            # --- RS 相对强弱 ---
            rs_value = calc_rs(price_df, index_df, lookback=20)
            if rs_value is None:
                continue

            # 规则：RS > 0.7
            if rs_value <= 0.7:
                continue

            # === 综合评分 ===
            total_score = calc_total_score(
                breakout_ok=cond_breakout,
                volume_ok=cond_volume,
                money_flow_ok=cond_money,
                sector_score=sector_score,
            )

            # === 最严格版过滤条件 ===
            if not cond_breakout:
                continue
            if not cond_volume:
                continue
            if not cond_money:
                continue
            if total_score < 80:
                continue

            results.append(
                {
                    "code": code,
                    "name": name,
                    "industry": industry,
                    "RS": round(rs_value, 2),
                    "sector_up_rank": round(sector_info["up_rank_pct"], 3),
                    "sector_flow_rank": round(sector_info["flow_rank_pct"], 3),
                    "sector_main_net_in": sector_info["main_net_in"],
                    "score": round(total_score, 2),
                }
            )

        except Exception as e:
            # 不要因为一只股出错就中断，继续下一只
            print(f"[selector] 处理 {code} {name} 失败: {e}")
            traceback.print_exc()
            continue

    if not results:
        return pd.DataFrame()

    df_res = pd.DataFrame(results)
    df_res = df_res.sort_values("score", ascending=False).reset_index(drop=True)
    return df_res
