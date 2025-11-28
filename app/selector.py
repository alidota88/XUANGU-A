import traceback
from collections import defaultdict

import numpy as np
import pandas as pd

from .config import BREAKOUT_N, MAX_STOCKS_PER_DAY
from .data_loader import (
    get_stock_list,
    get_latest_trade_date,
    get_top_liquidity_stocks,
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


def run_selection(top_n: int | None = None) -> pd.DataFrame:
    """
    主选股流程（Tushare 版）

    流程：
    1. 使用 daily + amount 排序：取成交额前 N 只股票（默认 MAX_STOCKS_PER_DAY）
    2. 每只股票获取最近 300 日 K 线 + 最近 20 日资金流
    3. 计算：
        - 箱体突破（规则1）
        - 放量（规则2）
        - 主力资金流入（规则4）
        - RS 强弱（规则5）
        - 板块强度（用候选池内 5 日涨幅 + 5 日净流入聚合到行业）
    4. 综合评分：突破30% + 放量25% + 主力25% + 板块20%
    5. 最严格过滤条件：
        - 突破箱体
        - 放量
        - 主力资金连续3天净流入
        - 行业为主线板块（前20%）
        - RS > 0.7
        - 得分 >= 80
    """
    if top_n is None:
        top_n = MAX_STOCKS_PER_DAY

    print(f"[selector] 获取成交额前 {top_n} 只股票...")
    candidates = get_top_liquidity_stocks(top_n=top_n)
    print("[selector] 候选股数量：", len(candidates))

    # 获取指数行情用于 RS
    print("[selector] 获取指数行情用于 RS 计算...")
    index_df = get_index_history(days=250)

    # 先一遍循环：获取每只股票的 K 线和资金流，并累计行业级统计，用于板块打分
    price_map: dict[str, pd.DataFrame] = {}
    flow_map: dict[str, pd.DataFrame] = {}
    industry_ret5: dict[str, list[float]] = defaultdict(list)
    industry_net5: dict[str, list[float]] = defaultdict(list)

    for _, row in candidates.iterrows():
        code = row["code"]
        name = row["name"]
        industry = row.get("industry") or "未知"

        try:
            price_df = get_stock_history(code, days=300)
            if price_df.empty:
                continue

            flow_df = get_stock_moneyflow(code, days=20)
            if flow_df.empty:
                continue

            price_map[code] = price_df
            flow_map[code] = flow_df

            # 计算个股 5 日涨幅
            if len(price_df) >= 6:
                p = price_df["close"].iloc[-6:]
                ret5 = p.iloc[-1] / p.iloc[0] - 1
                industry_ret5[industry].append(float(ret5))

            # 计算个股 5 日资金净流入
            if len(flow_df) >= 5:
                net5 = flow_df.sort_values("date")["main_net_in"].tail(5).sum()
                industry_net5[industry].append(float(net5))

        except Exception as e:
            print(f"[selector] 预处理 {code} {name} 出错：{e}")
            traceback.print_exc()
            continue

    if not price_map:
        print("[selector] 没有成功获取任何股票的行情数据")
        return pd.DataFrame()

    # 根据行业 5 日涨幅 & 5 日资金流，生成板块强度得分
    sector_stats = []
    for ind, rets in industry_ret5.items():
        avg_ret5 = np.mean(rets) if rets else 0.0
        net5 = np.sum(industry_net5.get(ind, [0.0]))
        sector_stats.append(
            {
                "industry": ind,
                "ret5": avg_ret5,
                "net5": net5,
            }
        )

    sector_df = pd.DataFrame(sector_stats)
    # 如果有行业统计，则计算百分位排名
    if not sector_df.empty:
        sector_df["up_rank_pct"] = sector_df["ret5"].rank(pct=True)
        sector_df["flow_rank_pct"] = sector_df["net5"].rank(pct=True)
        # 主线板块：涨幅前20% & 净流入前20% & 净流入>0
        sector_df["is_main_sector"] = (
            (sector_df["up_rank_pct"] > 0.8)
            & (sector_df["flow_rank_pct"] > 0.8)
            & (sector_df["net5"] > 0)
        )
        sector_df["sector_score"] = (sector_df["up_rank_pct"] + sector_df["flow_rank_pct"]) / 2.0
    else:
        # 极端情况：没有任何行业统计
        sector_df = pd.DataFrame(columns=["industry", "up_rank_pct", "flow_rank_pct", "is_main_sector", "sector_score"])

    sector_dict = {
        row["industry"]: row
        for _, row in sector_df.iterrows()
    }

    # 第二遍循环：根据已缓存的行情 + 板块打分进行最终选股
    results = []
    for _, row in candidates.iterrows():
        code = row["code"]
        name = row["name"]
        industry = row.get("industry") or "未知"

        price_df = price_map.get(code)
        flow_df = flow_map.get(code)
        if price_df is None or flow_df is None:
            continue

        try:
            # 板块信息
            sec_info = sector_dict.get(industry)
            if sec_info is None:
                continue

            if not bool(sec_info["is_main_sector"]):
                # 行业不在主线板块中
                continue

            sector_score = float(sec_info["sector_score"])
            up_rank_pct = float(sec_info["up_rank_pct"])
            flow_rank_pct = float(sec_info["flow_rank_pct"])

            # 信号：突破 + 放量 + 主力流入
            cond_breakout = breakout_signal(price_df, n=BREAKOUT_N)
            cond_volume = volume_signal(price_df)
            cond_money = money_flow_signal(flow_df)

            # RS 强弱
            rs_value = calc_rs(price_df, index_df, lookback=20)
            if rs_value is None or rs_value <= 0.7:
                continue

            # 综合得分
            total_score = calc_total_score(
                breakout_ok=cond_breakout,
                volume_ok=cond_volume,
                money_flow_ok=cond_money,
                sector_score=sector_score,
            )

            # 最严格过滤条件
            if not (cond_breakout and cond_volume and cond_money):
                continue
            if total_score < 80:
                continue

            results.append(
                {
                    "code": code,
                    "name": name,
                    "industry": industry,
                    "RS": round(rs_value, 2),
                    "sector_up_rank": round(up_rank_pct, 3),
                    "sector_flow_rank": round(flow_rank_pct, 3),
                    "score": round(total_score, 2),
                }
            )

        except Exception as e:
            print(f"[selector] 最终处理 {code} {name} 出错：{e}")
            traceback.print_exc()
            continue

    df_res = pd.DataFrame(results)
    if df_res.empty:
        print("[selector] 本次无标的入选。")
        return df_res

    df_res = df_res.sort_values("score", ascending=False).reset_index(drop=True)
    print("[selector] 完成选股，入选数量：", len(df_res))
    return df_res
