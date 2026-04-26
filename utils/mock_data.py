"""
Generate mock data for testing without hitting live APIs.
"""

from datetime import datetime
from typing import Any, Dict

import numpy as np


def generate_mock_market_data(asset: str = "BTC", days: int = 30) -> Dict[str, Any]:
    """Generate realistic-looking mock data shaped like a real signal payload."""
    rng = np.random.default_rng(42)

    flow_score = float(rng.uniform(20, 85))
    google_trends = float(rng.uniform(10, 80))
    coingecko_trending = float(rng.uniform(10, 90))
    news_velocity = float(rng.uniform(5, 70))
    etf_flow_direction = float(rng.uniform(10, 90))
    funding_extremity = float(rng.uniform(5, 95))
    volume_momentum = float(rng.uniform(10, 85))

    return {
        "asset":                   asset,
        "timestamp_utc":           datetime.utcnow().isoformat() + "Z",
        "flow_score":              flow_score,
        "flow_score_delta_24h":    float(rng.uniform(-10, 10)),
        "confidence":              float(rng.uniform(0.7, 1.0)),
        "signal_strength":         str(rng.choice(["WEAK", "MODERATE", "STRONG"])),
        "component_breakdown": {
            "attention": (google_trends + coingecko_trending) / 2,
            "capital":   (etf_flow_direction + funding_extremity) / 2,
            "momentum":  volume_momentum,
        },
        "layers": {
            "attention": {
                "google_trends_spike":      google_trends,
                "coingecko_trending_rank":  int(rng.integers(1, 50)),
                "coingecko_trending_score": coingecko_trending,
                "news_velocity_score":      news_velocity,
                "narrative_intensity":      (google_trends + coingecko_trending + news_velocity) / 3,
            },
            "capital": {
                "etf_flow_latest_usd":      float(rng.uniform(-50_000_000, 50_000_000)),
                "etf_flow_5d_sum":          float(rng.uniform(-100_000_000, 100_000_000)),
                "etf_flow_direction_score": etf_flow_direction,
                "funding_rate_current":     float(rng.uniform(-0.0002, 0.0010)),
                "funding_rate_percentile":  float(rng.uniform(10, 90)),
                "funding_extremity_score":  funding_extremity,
                "open_interest_trend":      str(rng.choice(["UP", "FLAT", "DOWN"])),
            },
            "momentum": {
                "volume_momentum_score": volume_momentum,
                "price_change_24h":      float(rng.uniform(-5, 5)),
                "volatility_24h":        float(rng.uniform(0.5, 4.0)),
            },
        },
        "divergences": [
            {
                "pattern_name":     "momentum_breakout",
                "bias":             "BULLISH",
                "confidence":       0.85,
                "explanation":      "All signals aligned for sustained move.",
                "suggested_action": "Accumulate on dips.",
                "inputs_used":      {"flow_score": flow_score},
            }
        ],
        "risk_level": str(rng.choice(["CALM", "ELEVATED"])),
        "data_quality": {
            "sources_available": ["etf_flows", "funding_rates", "google_trends"],
            "sources_failed":    [],
            "last_updated": {
                "attention": datetime.utcnow().isoformat(),
                "capital":   datetime.utcnow().isoformat(),
                "momentum":  datetime.utcnow().isoformat(),
            },
        },
    }
