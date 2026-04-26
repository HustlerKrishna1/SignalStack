"""
CoinGecko API client for price, market data, and trending.
Free tier: no auth, generous rate limits.
"""

from datetime import datetime
from typing import Any, Dict

import pandas as pd
import requests

from utils.cache import cache
from utils.config import (
    ASSET_MAP,
    COINGECKO_NOT_TRENDING,
    COINGECKO_TRENDING_RANKS,
    REQUEST_TIMEOUT,
    USER_AGENT,
)
from utils.logger import log_data_fetch, setup_logger

logger = setup_logger(__name__)
BASE_URL = "https://api.coingecko.com/api/v3"


def get_market_data(asset: str) -> Dict[str, Any]:
    """Fetch current market data for an asset."""
    coingecko_id = ASSET_MAP.get(asset, {}).get("coingecko")
    if not coingecko_id:
        return {"error": f"Asset {asset} not mapped to CoinGecko"}

    cache_key = f"market_data_{asset}"
    cached = cache.get(cache_key, ttl_minutes=15)
    if cached:
        return cached

    start_time = datetime.utcnow()
    try:
        url = f"{BASE_URL}/simple/price"
        params = {
            "ids":                  coingecko_id,
            "vs_currencies":        "usd",
            "include_market_cap":   "true",
            "include_24hr_vol":     "true",
            "include_24hr_change":  "true",
        }
        resp = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json().get(coingecko_id, {})

        result = {
            "current_price_usd":     float(data.get("usd", 0)),
            "market_cap_usd":        float(data.get("usd_market_cap", 0)),
            "volume_24h_usd":        float(data.get("usd_24h_vol", 0)),
            "price_change_24h_pct":  float(data.get("usd_24h_change", 0)),
            "error":                 None,
        }
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        log_data_fetch("CoinGecko Market", asset, True, duration_ms)
        cache.set(cache_key, result)
        return result

    except Exception as e:
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        log_data_fetch("CoinGecko Market", asset, False, duration_ms, str(e))
        return {
            "current_price_usd":    0.0,
            "market_cap_usd":       0.0,
            "volume_24h_usd":       0.0,
            "price_change_24h_pct": 0.0,
            "error":                str(e),
        }


def get_coingecko_trending(target_asset: str = "BTC") -> Dict[str, Any]:
    """Fetch CoinGecko's trending assets (top 7 by search volume)."""
    cache_key = "coingecko_trending"
    cached = cache.get(cache_key, ttl_minutes=60)
    if cached:
        return _attach_target_score(cached, target_asset)

    start_time = datetime.utcnow()
    try:
        url = f"{BASE_URL}/search/trending"
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        coins = resp.json().get("coins", [])

        rows = []
        for idx, coin_data in enumerate(coins[:7], start=1):
            item = coin_data.get("item", {})
            rows.append({
                "rank":   idx,
                "symbol": item.get("symbol", "").upper(),
                "name":   item.get("name", ""),
                "id":     item.get("id", ""),
            })
        df = pd.DataFrame(rows)

        result = {
            "raw":                       df,
            "trending_rank":             None,
            "narrative_intensity_score": float(COINGECKO_NOT_TRENDING),
            "data_freshness_minutes":    0,
            "error":                     None,
        }

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        log_data_fetch("CoinGecko Trending", "ALL", True, duration_ms)
        cache.set(cache_key, result)
        return _attach_target_score(result, target_asset)

    except Exception as e:
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        log_data_fetch("CoinGecko Trending", "ALL", False, duration_ms, str(e))
        return {
            "raw":                       pd.DataFrame(),
            "trending_rank":             None,
            "narrative_intensity_score": 0.0,
            "data_freshness_minutes":    0,
            "error":                     str(e),
        }


def _attach_target_score(result: Dict[str, Any], target_asset: str) -> Dict[str, Any]:
    """Compute narrative intensity for the target asset based on trending rank."""
    df = result.get("raw")
    if isinstance(df, pd.DataFrame) and not df.empty and "symbol" in df.columns:
        match = df[df["symbol"] == target_asset.upper()]
        if not match.empty:
            rank = int(match["rank"].iloc[0])
            result = dict(result)
            result["trending_rank"] = rank
            result["narrative_intensity_score"] = float(
                COINGECKO_TRENDING_RANKS.get(rank, 50)
            )
            return result
    result = dict(result)
    result["trending_rank"] = None
    result["narrative_intensity_score"] = float(COINGECKO_NOT_TRENDING)
    return result


def get_market_chart(asset: str, days: int = 30) -> Dict[str, Any]:
    """Fetch historical price chart for computing momentum."""
    coingecko_id = ASSET_MAP.get(asset, {}).get("coingecko")
    if not coingecko_id:
        return {"raw": pd.DataFrame(), "error": f"Asset {asset} not mapped"}

    cache_key = f"market_chart_{asset}_{days}d"
    cached = cache.get(cache_key, ttl_minutes=60)
    if cached:
        return cached

    start_time = datetime.utcnow()
    try:
        url = f"{BASE_URL}/coins/{coingecko_id}/market_chart"
        params = {
            "vs_currency": "usd",
            "days":        days,
            "interval":    "daily",
        }
        resp = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        rows = []
        for price_data, vol_data, mcap_data in zip(
            data.get("prices", []),
            data.get("total_volumes", []),
            data.get("market_caps", []),
        ):
            rows.append({
                "timestamp":      datetime.utcfromtimestamp(price_data[0] / 1000),
                "price_usd":      float(price_data[1]),
                "volume_usd":     float(vol_data[1]),
                "market_cap_usd": float(mcap_data[1]),
            })
        df = pd.DataFrame(rows)

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        log_data_fetch(f"CoinGecko Chart ({days}d)", asset, True, duration_ms)
        result = {"raw": df, "error": None}
        cache.set(cache_key, result)
        return result

    except Exception as e:
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        log_data_fetch(f"CoinGecko Chart ({days}d)", asset, False, duration_ms, str(e))
        return {"raw": pd.DataFrame(), "error": str(e)}
