"""
Binance public API client (no auth required).
Funding rates, klines (OHLCV).
Rate limit: 1200 requests/minute.
"""

from datetime import datetime
from typing import Any, Dict

import pandas as pd
import requests

from utils.cache import cache
from utils.config import ASSET_MAP, REQUEST_TIMEOUT, USER_AGENT
from utils.logger import log_data_fetch, setup_logger

logger = setup_logger(__name__)
BASE_URL = "https://fapi.binance.com"


def get_funding_rates(asset: str) -> Dict[str, Any]:
    """Fetch funding rates from Binance futures public API."""
    binance_symbol = ASSET_MAP.get(asset, {}).get("binance")
    if not binance_symbol:
        return _empty_funding_response(f"Asset {asset} not mapped to Binance")

    cache_key = f"funding_rates_{asset}"
    cached = cache.get(cache_key, ttl_minutes=30)
    if cached:
        return cached

    start_time = datetime.utcnow()
    try:
        url = f"{BASE_URL}/fapi/v1/fundingRate"

        resp_latest = requests.get(
            url,
            params={"symbol": binance_symbol, "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp_latest.raise_for_status()
        latest_payload = resp_latest.json()
        if not latest_payload:
            raise ValueError("Empty funding rate response")
        current_funding_rate = float(latest_payload[0]["fundingRate"])

        resp_hist = requests.get(
            url,
            params={"symbol": binance_symbol, "limit": 90},
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp_hist.raise_for_status()
        hist_data = resp_hist.json()
        hist_rates = [float(item["fundingRate"]) for item in hist_data]

        rows = [
            {
                "timestamp":    datetime.utcfromtimestamp(int(item["fundingTime"]) / 1000),
                "funding_rate": float(item["fundingRate"]),
                "symbol":       binance_symbol,
            }
            for item in hist_data
        ]
        df = pd.DataFrame(rows)

        funding_rate_24h_avg = (
            sum(hist_rates[-3:]) / 3
            if len(hist_rates) >= 3
            else current_funding_rate
        )

        if hist_rates:
            count_lower = sum(1 for r in hist_rates if r < current_funding_rate)
            funding_rate_30d_percentile = (count_lower / len(hist_rates)) * 100
        else:
            funding_rate_30d_percentile = 50.0

        funding_extremity_score = funding_rate_30d_percentile

        if current_funding_rate < 0:
            interpretation = "Negative (longs paid)"
        elif funding_rate_30d_percentile > 90:
            interpretation = "Very High (crowded longs)"
        elif funding_rate_30d_percentile > 70:
            interpretation = "Elevated"
        else:
            interpretation = "Normal"

        result = {
            "raw":                          df,
            "current_funding_rate":         current_funding_rate,
            "funding_rate_24h_avg":         float(funding_rate_24h_avg),
            "funding_rate_30d_percentile":  float(funding_rate_30d_percentile),
            "funding_extremity_score":      float(funding_extremity_score),
            "interpretation":               interpretation,
            "data_freshness_minutes":       0,
            "error":                        None,
        }

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        log_data_fetch("Binance Funding Rates", asset, True, duration_ms)
        cache.set(cache_key, result)
        return result

    except Exception as e:
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        log_data_fetch("Binance Funding Rates", asset, False, duration_ms, str(e))
        return _empty_funding_response(str(e))


def _empty_funding_response(error_msg: str) -> Dict[str, Any]:
    return {
        "raw":                          pd.DataFrame(),
        "current_funding_rate":         0.0,
        "funding_rate_24h_avg":         0.0,
        "funding_rate_30d_percentile":  0.0,
        "funding_extremity_score":      0.0,
        "interpretation":               "N/A",
        "data_freshness_minutes":       0,
        "error":                        error_msg,
    }


def get_klines(asset: str, interval: str = "1h", limit: int = 24) -> Dict[str, Any]:
    """Fetch candlestick (OHLCV) data for computing momentum."""
    binance_symbol = ASSET_MAP.get(asset, {}).get("binance")
    if not binance_symbol:
        return {"raw": pd.DataFrame(), "error": f"Asset {asset} not mapped"}

    cache_key = f"klines_{asset}_{interval}_{limit}"
    cached = cache.get(cache_key, ttl_minutes=15)
    if cached:
        return cached

    start_time = datetime.utcnow()
    try:
        url = f"{BASE_URL}/fapi/v1/klines"
        resp = requests.get(
            url,
            params={"symbol": binance_symbol, "interval": interval, "limit": limit},
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        rows = []
        for candle in data:
            rows.append({
                "timestamp": datetime.utcfromtimestamp(int(candle[0]) / 1000),
                "open":      float(candle[1]),
                "high":      float(candle[2]),
                "low":       float(candle[3]),
                "close":     float(candle[4]),
                "volume":    float(candle[7]),  # quote asset volume
            })
        df = pd.DataFrame(rows)

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        log_data_fetch(f"Binance Klines ({interval})", asset, True, duration_ms)
        result = {"raw": df, "error": None}
        cache.set(cache_key, result)
        return result

    except Exception as e:
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        log_data_fetch(f"Binance Klines ({interval})", asset, False, duration_ms, str(e))
        return {"raw": pd.DataFrame(), "error": str(e)}


def get_open_interest_proxy(asset: str) -> Dict[str, Any]:
    """
    Compute a lightweight OI trend proxy from kline volume changes.
    Real OI data requires either premium endpoints or longer-running snapshots.
    """
    klines = get_klines(asset, interval="1d", limit=30)
    df = klines.get("raw", pd.DataFrame())
    if df.empty or len(df) < 5:
        return {"oi_trend": "FLAT", "oi_30d_change_pct": 0.0, "error": klines.get("error")}

    recent_avg = float(df["volume"].tail(7).mean())
    older_avg = float(df["volume"].head(7).mean())
    change_pct = ((recent_avg - older_avg) / (older_avg + 1e-9)) * 100

    if change_pct > 5:
        trend = "UP"
    elif change_pct < -5:
        trend = "DOWN"
    else:
        trend = "FLAT"

    return {
        "oi_trend":          trend,
        "oi_30d_change_pct": float(change_pct),
        "error":             None,
    }
