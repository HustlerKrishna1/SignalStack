"""
Composite Flow Score: weighted aggregation of all normalized signals.
"""

from datetime import datetime
from typing import Any, Dict

import numpy as np

from utils.config import FLOW_SCORE_WEIGHTS
from utils.logger import setup_logger

logger = setup_logger(__name__)


def normalize_score(value: float, min_val: float = 0, max_val: float = 100) -> float:
    """Normalize a value to 0-100 range."""
    if max_val <= min_val:
        return 50.0
    normalized = ((value - min_val) / (max_val - min_val)) * 100
    return float(np.clip(normalized, 0, 100))


def compute_flow_score(
    google_trends_spike: float,
    coingecko_trending_score: float,
    etf_flow_direction_score: float,
    funding_extremity_score: float,
    volume_momentum_score: float,
    confidence: float = 1.0,
) -> Dict[str, Any]:
    """
    Compute composite Flow Score from normalized sub-scores.
    All input scores must be in 0-100.
    """
    raw_score = (
        google_trends_spike      * FLOW_SCORE_WEIGHTS["google_trends_spike"]
        + coingecko_trending_score * FLOW_SCORE_WEIGHTS["coingecko_trending_score"]
        + etf_flow_direction_score * FLOW_SCORE_WEIGHTS["etf_flow_direction_score"]
        + funding_extremity_score  * FLOW_SCORE_WEIGHTS["funding_extremity_score"]
        + volume_momentum_score    * FLOW_SCORE_WEIGHTS["volume_momentum_score"]
    )

    flow_score = float(np.clip(raw_score * confidence, 0, 100))

    attention_component = float((google_trends_spike + coingecko_trending_score) / 2)
    capital_component   = float((etf_flow_direction_score + funding_extremity_score) / 2)
    momentum_component  = float(volume_momentum_score)

    if flow_score > 70:
        signal_strength = "STRONG"
    elif flow_score > 40:
        signal_strength = "MODERATE"
    else:
        signal_strength = "WEAK"

    percentile = float(np.clip(flow_score * 1.1, 0, 100))

    return {
        "flow_score":            flow_score,
        "flow_score_percentile": percentile,
        "confidence":            float(np.clip(confidence, 0, 1)),
        "component_breakdown": {
            "attention": attention_component,
            "capital":   capital_component,
            "momentum":  momentum_component,
        },
        "signal_strength":  signal_strength,
        "timestamp_utc":    datetime.utcnow().isoformat() + "Z",
    }
