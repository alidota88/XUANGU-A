import traceback

import numpy as np
import pandas as pd

from .config import BREAKOUT_N, MAX_STOCKS_PER_DAY
from .data_loader import (
    get_top_liquidity_stocks,            # 新增
    get_industry_mapping,
    get_sector_fund_flow_rank,
    get_index_history,
    get_stock_history,
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


def run_selection(top_n=500) -> pd.DataFrame:
    """
    主选股逻辑（最佳方案：只处理成交额排名前 500 的股票）
    Railway 稳定、速度快、不会漏主线资金龙头。
    """

    # === 1. 获取实时成交额前 top_n 股票（最重要优化点） ===
    print("[selector] 获取实时成交额榜 top", top_n)
    candidates = get_top_liquidity_stocks(top_n=top_n)

    # === 2. 行业映射（读本地缓存，不会被墙） ===
    print("[selector] 加载行业映射...")
    industry_map = get_industry_mapping()
    candidates = candidates.merge(industry_map, on="code", how="left")

    # === 3. 板块资金流（判断主线方向） ===
    print("[selector] 获取板块资金流...")
    sector_raw = get_sector_fund_flow_rank()
    sector_scores = compute_sector_scores(sector_raw)
    sector_marked = mark_main_sectors(sector_scores)

    # 构建板块评分字典
    sector_dict = {}
    for _, row in sector_marked.iterrows():
        sector_dict[row["板块名称"]] = row

    # === 4. 获取指数行情用于计算 RS ===
    print("[selector] 获取指数行情...")
    index_df = get_index_history(days=300)

    results = []

    # === 5. 主循环（仅 500 只，不会超时） ===
    print("[selector] 处理股票数量：", len(candidates))
    for _, row in candidates.iterrows():
        code = row["code"]
        name = row["name"]
        industry = row.get("industry")

        try:
            if not isinstance(industry, str):
                continue

            # 行业板块是否为主线？
            if industry not in sector_dict:
                continue

            sector_info = sector_dict[industry]
            if not sector_info["is_main_sector"]:
                continue

            # 板块综合得分
            sector_score = float(
                (sector_info["up_rank_pct"] + sector_info["flow_rank_pct"]) / 2
            )

            # === 获取个股行情 + 资金流（这两项可能被限流，但数量少了不会报错） ===
            price_df = get_stock_history(code)
            flow_df = get_stock_fund_flow(code)

            # --- 信号计算 ---
            cond_breakout = breakout_signal(price_df, n=BREAKOUT_N)
            cond_volume = volume_signal(price_df)
            cond_money = money_flow_signal(flow_df)

            rs_value = calc_rs(price_df, index_df)
            if not rs_value or rs_value < 0.7:
                continue

            # 综合评分
            total_score = calc_total_score(
                breakout_ok=cond_breakout,
                volume_ok=cond_volume,
                money_flow_ok=cond_money,
                sector_score=sector_score,
            )

            if (
                cond_breakout
                and cond_volume
                and cond_money
                and total_score >= 80
            ):
                results.append({
                    "code": code,
                    "name": name,
                    "industry": industry,
                    "RS": round(rs_value, 2),
                    "sector_up_rank": sector_info["up_rank_pct"],
                    "sector_flow_rank": sector_info["flow_rank_pct"],
                    "score": round(total_score, 2),
                })

        except Exception as e:
            print(f"[selector] 处理 {code} {name} 出错：{e}")
            traceback.print_exc()
            continue

    print("[selector] 完成，总共选出", len(results), "只股票")
    return pd.DataFrame(results)
