from .data_loader import *
from .indicators import *
import numpy as np


def run_selection():
    """返回选股文本内容，用于 telegram 推送"""

    # 基础数据
    basic = get_stock_basic()
    name_map = dict(zip(basic.ts_code, basic.name))
    ind_map = dict(zip(basic.ts_code, basic.industry))

    # 获取交易日
    trade_dates = get_trade_dates(20)
    last = trade_dates[-1]
    first20 = trade_dates[0]
    first5 = trade_dates[-5:]

    # ==== 20 日涨幅 ====
    df_first = get_daily(first20)
    df_last = get_daily(last)
    df_20 = df_first[['ts_code', 'close']].merge(
        df_last[['ts_code', 'close']], on='ts_code', suffixes=('_first', '_last')
    )
    df_20['ret'] = df_20['close_last'] / df_20['close_first'] - 1
    ret_map = dict(zip(df_20.ts_code, df_20.ret))

    # ==== 大盘 20 日涨幅 ====
    idx = get_index(first20, last)
    try:
        idx_ret = idx['close'].iloc[-1] / idx['close'].iloc[0] - 1
    except:
        idx_ret = None

    # ==== 板块 5 日涨幅 ====
    df_f5 = get_daily(first5[0])
    df_l5 = get_daily(last)
    df_5 = df_f5[['ts_code','close']].merge(
        df_l5[['ts_code','close']], on='ts_code', suffixes=('_5','_t')
    )
    df_5['ret5'] = df_5['close_t']/df_5['close_5'] - 1
    df_5['industry'] = df_5['ts_code'].map(ind_map)

    sector_perf = df_5.groupby('industry')['ret5'].mean().to_dict()

    # ==== 板块 5 日资金流 ====
    sector_flow5 = {}
    sector_flow_today = {}
    for d in first5:
        df = get_moneyflow(d)
        if df.empty:
            continue
        df['industry'] = df['ts_code'].map(ind_map)
        grp = df.groupby('industry')['net_mf_amount'].sum()
        for i,v in grp.items():
            sector_flow5[i] = sector_flow5.get(i, 0) + v
            if d == last:
                sector_flow_today[i] = v

    # ==== 主线板块 ====
    inds = list(sector_perf.keys())
    if len(inds)==0:
        return "今日无板块数据"

    topN = max(1, int(len(inds)*0.2))
    perf_top = sorted(sector_perf.items(), key=lambda x: x[1], reverse=True)[:topN]
    flow_top = sorted(sector_flow5.items(), key=lambda x: x[1], reverse=True)[:topN]

    perf_set = {i for i,_ in perf_top}
    flow_set = {i for i,_ in flow_top}

    main_sectors = [i for i in perf_set & flow_set if sector_flow_today.get(i,0) > 0]

    # ==== 当日候选（必须属于主线板块） ====
    today = get_daily(last)
    candidates = today[today['ts_code'].map(lambda x: ind_map.get(x) in main_sectors)]
    if candidates.empty:
        return "今日无主线板块股票"

    # ==== 逐个股票检查策略 ====
    selected = []
    for _,row in candidates.iterrows():
        code = row['ts_code']

        # RS
        if not calc_rs(ret_map.get(code,0), idx_ret):
            continue

        # 历史K线
        start = (datetime.strptime(last,"%Y%m%d") - timedelta(days=90)).strftime("%Y%m%d")
        hist = pro.daily(ts_code=code, start_date=start, end_date=last)
        if hist.empty:
            continue
        hist.sort_values("trade_date", inplace=True)

        # 突破
        if not calc_breakout(hist):
            continue

        # 放量
        if not calc_volume_spike(hist):
            continue

        # 连续3日净流入
        df_flow = pro.moneyflow(ts_code=code, start_date=trade_dates[-3], end_date=last)
        if len(df_flow) < 3 or (df_flow['net_mf_amount'] <= 0).any():
            continue

        selected.append((code, name_map.get(code, ""), ind_map.get(code,"")))

    if not selected:
        return "今日无符合策略股票"

    msg = f"📈 今日选股（{last}）\n"
    for c,n,i in selected:
        msg += f"{c} {n} [{i}]\n"

    return msg
