"""
Central configuration file for SignalStack.
Change weights, thresholds, symbols here without touching other code.
"""

from typing import Dict, List, Optional

# ============================================================================
# SUPPORTED ASSETS
# ============================================================================
SUPPORTED_ASSETS = ["BTC", "ETH", "SOL", "XRP", "DOGE"]

ASSET_MAP = {
    "BTC":  {"binance": "BTCUSDT",  "coingecko": "bitcoin",  "farside": "btc"},
    "ETH":  {"binance": "ETHUSDT",  "coingecko": "ethereum", "farside": "eth"},
    "SOL":  {"binance": "SOLUSDT",  "coingecko": "solana",   "farside": "solana"},
    "XRP":  {"binance": "XRPUSDT",  "coingecko": "ripple",   "farside": None},
    "DOGE": {"binance": "DOGEUSDT", "coingecko": "dogecoin", "farside": None},
}

# ============================================================================
# FLOW SCORE WEIGHTS (sum to 1.0)
# ============================================================================
FLOW_SCORE_WEIGHTS = {
    "google_trends_spike":      0.15,
    "coingecko_trending_score": 0.15,
    "etf_flow_direction_score": 0.25,
    "funding_extremity_score":  0.20,
    "volume_momentum_score":    0.25,
}

assert abs(sum(FLOW_SCORE_WEIGHTS.values()) - 1.0) < 0.01, "Weights must sum to 1.0"

# ============================================================================
# DATA SOURCE THRESHOLDS & SETTINGS
# ============================================================================

# Google Trends
GOOGLE_TRENDS_TIMEFRAME = "now 7-d"
GOOGLE_TRENDS_MOVING_AVG_WINDOW = 3
GOOGLE_TRENDS_SPIKE_MULTIPLIER = 2.0

# CoinGecko Trending
COINGECKO_TRENDING_RANKS = {
    1: 90, 2: 90,
    3: 70, 4: 70, 5: 70,
    6: 50, 7: 50,
}
COINGECKO_NOT_TRENDING = 10

# News Velocity (CryptoPanic)
NEWS_VELOCITY_LOOKBACK_DAYS = 7
NEWS_VELOCITY_MULTIPLIER = 20

# ETF Flows (Farside)
ETF_FLOW_HISTORICAL_WINDOW = 365
ETF_FLOW_SUSTAINED_DAYS = 5

# Funding Rates (Binance)
FUNDING_RATE_LOOKBACK_DAYS = 30
FUNDING_RATE_THRESHOLDS = {
    "extreme_high": 0.0008,
    "elevated":     0.0005,
}

# Volume Momentum
VOLUME_MOMENTUM_LOOKBACK_HOURS = 24
VOLUME_MOMENTUM_PERCENTILE_THRESHOLD = 70

# Open Interest
OPEN_INTEREST_TREND_THRESHOLD = 0.05

# ============================================================================
# DIVERGENCE PATTERN THRESHOLDS
# ============================================================================
SMART_MONEY_THRESHOLD = {
    "etf_flow_min": 70,
    "trend_max":    40,
}

HYPE_NO_CONVICTION_THRESHOLD = {
    "trend_min":    70,
    "etf_flow_max": 30,
}

TRAPPED_LONGS_THRESHOLD = {
    "funding_extremity_min": 90,
    "price_momentum_max":    2,
}

MOMENTUM_BREAKOUT_THRESHOLD = {
    "flow_score_min":        75,
    "trend_min":             60,
    "etf_flow_min":          60,
    "funding_extremity_max": 70,
}

# ============================================================================
# RISK LEVELS
# ============================================================================
RISK_THRESHOLDS = {
    "EXTREME":  {"flow_score_min": 80, "funding_extremity_min": 85},
    "ELEVATED": {"flow_score_min": 70, "funding_extremity_min": 75},
    "CALM":     {},
}

# ============================================================================
# CACHING & API SETTINGS
# ============================================================================
CACHE_TTL = {
    "google_trends":      1440,
    "coingecko_trending": 60,
    "news_velocity":      30,
    "etf_flows":          1440,
    "funding_rates":      30,
    "open_interest":      120,
    "price_data":         15,
}

REQUEST_TIMEOUT = 10
USER_AGENT = "SignalStack/1.0 (+https://github.com/yourusername/signalstack)"

# ============================================================================
# LOGGING
# ============================================================================
LOG_LEVEL = "INFO"
LOG_FORMAT = "[%(asctime)s] %(name)s - %(levelname)s - %(message)s"

# ============================================================================
# STREAMLIT SETTINGS
# ============================================================================
STREAMLIT_PAGE_TITLE = "SignalStack: Crypto Intelligence Terminal"
STREAMLIT_PAGE_ICON = "📡"
STREAMLIT_LAYOUT = "wide"
STREAMLIT_INITIAL_SIDEBAR_STATE = "expanded"

COLOR_BULLISH  = "#00D084"
COLOR_BEARISH  = "#F44033"
COLOR_NEUTRAL  = "#9CA3AF"
COLOR_CHART_BG = "#0F1419"

# ============================================================================
# BACKTESTING SETTINGS
# ============================================================================
BACKTEST_MIN_DAYS = 30
BACKTEST_LOOKBACK_HOURS = 168
