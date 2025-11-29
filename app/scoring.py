from dataclasses import dataclass


@dataclass
class ScoreWeights:
    breakout: float = 0.30       # 突破箱体/新高
    volume: float = 0.25         # 放量
    money_flow: float = 0.25     # 主力净流入
    sector: float = 0.20         # 板块主线度（基于行业 5 日涨幅 & 资金流）


WEIGHTS = ScoreWeights()


def calc_total_score(
    breakout_ok: bool,
    volume_ok: bool,
    money_flow_ok: bool,
    sector_score: float,
) -> float:
    """
    返回 [0,100] 的总分
    sector_score：行业主线度，取 [0,1]，通常为 (rank_up + rank_flow)/2
    """
    score = 0.0
    score += (1.0 if breakout_ok else 0.0) * WEIGHTS.breakout
    score += (1.0 if volume_ok else 0.0) * WEIGHTS.volume
    score += (1.0 if money_flow_ok else 0.0) * WEIGHTS.money_flow
    score += float(sector_score) * WEIGHTS.sector
    return score * 100.0
