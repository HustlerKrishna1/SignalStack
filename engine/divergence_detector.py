"""
Detect divergence patterns (misalignment between signals).
"""

from typing import Any, Dict, List

from utils.config import (
    HYPE_NO_CONVICTION_THRESHOLD,
    MOMENTUM_BREAKOUT_THRESHOLD,
    SMART_MONEY_THRESHOLD,
    TRAPPED_LONGS_THRESHOLD,
)
from utils.logger import setup_logger

logger = setup_logger(__name__)


def detect_divergences(
    flow_score: float,
    google_trends: float,
    coingecko_trending: float,
    etf_flow_direction: float,
    funding_extremity: float,
    volume_momentum: float,
    price_change_24h: float,
) -> List[Dict[str, Any]]:
    """Detect divergence patterns across signals."""
    signals: List[Dict[str, Any]] = []

    # Pattern 1: Smart Money Accumulation
    if (etf_flow_direction > SMART_MONEY_THRESHOLD["etf_flow_min"]
            and google_trends < SMART_MONEY_THRESHOLD["trend_max"]):
        signals.append({
            "pattern_name":     "smart_money_accumulation",
            "bias":             "BULLISH",
            "confidence":       0.85,
            "explanation": (
                "Institutions quietly accumulating while retail attention remains low. "
                "Often precedes 2-4 week rally as narrative catches up to capital flow."
            ),
            "suggested_action": "Monitor for volume-on-up days; accumulate on pullbacks to moving averages.",
            "inputs_used": {
                "etf_flow_direction": etf_flow_direction,
                "google_trends":      google_trends,
            },
        })

    # Pattern 2: Hype Without Conviction
    if (google_trends > HYPE_NO_CONVICTION_THRESHOLD["trend_min"]
            and etf_flow_direction < HYPE_NO_CONVICTION_THRESHOLD["etf_flow_max"]):
        signals.append({
            "pattern_name":     "hype_without_conviction",
            "bias":             "BEARISH",
            "confidence":       0.75,
            "explanation": (
                "Retail FOMO and narrative hype without institutional capital backing. "
                "Institutions may be lightening exposure. High risk of pullback or consolidation."
            ),
            "suggested_action": "Reduce position size; wait for capitulation or accumulation signal.",
            "inputs_used": {
                "google_trends":      google_trends,
                "etf_flow_direction": etf_flow_direction,
            },
        })

    # Pattern 3: Trapped Longs
    if (funding_extremity > TRAPPED_LONGS_THRESHOLD["funding_extremity_min"]
            and abs(price_change_24h) < TRAPPED_LONGS_THRESHOLD["price_momentum_max"]):
        signals.append({
            "pattern_name":     "trapped_longs",
            "bias":             "BEARISH",
            "confidence":       0.80,
            "explanation": (
                "Funding rates at extreme levels signaling overcrowded long positions, "
                "yet price is stagnant or declining. Liquidation cascade risk if support breaks."
            ),
            "suggested_action": "Reduce leverage; tighten stop-loss; watch key support levels for breakdown.",
            "inputs_used": {
                "funding_extremity": funding_extremity,
                "price_change_24h":  price_change_24h,
            },
        })

    # Pattern 4: Momentum Breakout
    if (flow_score > MOMENTUM_BREAKOUT_THRESHOLD["flow_score_min"]
            and google_trends > MOMENTUM_BREAKOUT_THRESHOLD["trend_min"]
            and etf_flow_direction > MOMENTUM_BREAKOUT_THRESHOLD["etf_flow_min"]
            and funding_extremity < MOMENTUM_BREAKOUT_THRESHOLD["funding_extremity_max"]):
        signals.append({
            "pattern_name":     "momentum_breakout",
            "bias":             "BULLISH",
            "confidence":       0.90,
            "explanation": (
                "All signals aligned: retail attention rising, institutional capital inflow, "
                "strong flow score, and positioning not yet overcrowded. "
                "Clean setup for sustained directional move with room to run."
            ),
            "suggested_action": (
                "Strong buy signal; accumulate on pullbacks; target 4-8 week move. "
                "Monitor funding rates for signs of crowding."
            ),
            "inputs_used": {
                "flow_score":         flow_score,
                "google_trends":      google_trends,
                "etf_flow_direction": etf_flow_direction,
                "funding_extremity":  funding_extremity,
            },
        })

    # Pattern 5: Conflicting Signals
    attention_avg = (google_trends + coingecko_trending) / 2
    if abs(etf_flow_direction - attention_avg) > 40:
        signals.append({
            "pattern_name":     "conflicting_signals",
            "bias":             "NEUTRAL",
            "confidence":       0.40,
            "explanation": (
                "Institutions and retail are not aligned on direction. "
                "Capital flows diverge from attention. Expect heightened volatility but unclear direction."
            ),
            "suggested_action": "Reduce position size; avoid leverage; wait for consolidation and signal clarity.",
            "inputs_used": {
                "etf_flow_direction": etf_flow_direction,
                "attention_avg":      attention_avg,
            },
        })

    return signals
