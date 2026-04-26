"""
Orchestrator: Fetch all data, compute Flow Score, detect divergences.
Main entry point for signal computation.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict

import numpy as np

from data_sources.binance_client import (
    get_funding_rates,
    get_klines,
    get_open_interest_proxy,
)
from data_sources.coingecko_client import get_coingecko_trending, get_market_data
from data_sources.etf_flows_scraper import get_etf_flows
from data_sources.google_trends import get_google_trends_data
from data_sources.news_spike import get_news_velocity
from engine.divergence_detector import detect_divergences
from engine.flow_scorer import compute_flow_score
from utils.cache import cache
from utils.config import RISK_THRESHOLDS
from utils.logger import setup_logger

logger = setup_logger(__name__)


def compute_volume_momentum_score(asset: str) -> Dict[str, Any]:
    """Compute momentum from volume surge + price direction alignment."""
    klines_resp = get_klines(asset, interval="1h", limit=24)
    if klines_resp.get("error"):
        logger.warning(f"Could not fetch klines for {asset}: {klines_resp['error']}")
        return {"score": 50.0, "volatility_24h": 0.0, "error": klines_resp["error"]}

    df = klines_resp["raw"]
    if df.empty or len(df) < 5:
        return {"score": 50.0, "volatility_24h": 0.0, "error": "Insufficient klines"}

    avg_volume = float(df["volume"].mean())
    current_volume = float(df["volume"].iloc[-1])
    volume_ratio = current_volume / (avg_volume + 1e-6)

    price_change = float(
        (df["close"].iloc[-1] - df["close"].iloc[0]) / (df["close"].iloc[0] + 1e-9)
    )
    direction_component = 10 if price_change > 0 else -10

    returns = df["close"].pct_change().dropna()
    volatility = float(returns.std() * 100) if not returns.empty else 0.0
    volatility_component = min(10.0, volatility / 2)

    score = max(0, (volume_ratio - 1) * 10) + direction_component + volatility_component

    return {
        "score":          float(np.clip(score, 0, 100)),
        "volatility_24h": volatility,
        "error":          None,
    }


def compute_signals(
    asset: str,
    use_cache: bool = True,
    cache_ttl_minutes: int = 15,
) -> Dict[str, Any]:
    """Fetch all data sources, compute Flow Score and divergences."""
    cache_key = f"signals_{asset}"
    if use_cache:
        cached = cache.get(cache_key, ttl_minutes=cache_ttl_minutes)
        if cached:
            return cached

    sources_available = []
    sources_failed = []

    logger.info(f"Computing signals for {asset}...")

    # ==================== PARALLEL DATA FETCH ====================
    with ThreadPoolExecutor(max_workers=8) as executor:
        f_trends   = executor.submit(get_google_trends_data, asset)
        f_trending = executor.submit(get_coingecko_trending, asset)
        f_news     = executor.submit(get_news_velocity, asset)
        f_etf      = executor.submit(get_etf_flows, asset)
        f_funding  = executor.submit(get_funding_rates, asset)
        f_oi       = executor.submit(get_open_interest_proxy, asset)
        f_market   = executor.submit(get_market_data, asset)
        f_momentum = executor.submit(compute_volume_momentum_score, asset)
        trends_resp   = f_trends.result()
        trending_resp = f_trending.result()
        news_resp     = f_news.result()
        etf_resp      = f_etf.result()
        funding_resp  = f_funding.result()
        oi_resp       = f_oi.result()
        market_resp   = f_market.result()
        momentum_resp = f_momentum.result()

    # ==================== ATTENTION LAYER ====================
    google_trends_spike = float(trends_resp.get("trend_spike_score", 0.0))
    if trends_resp.get("error"):
        sources_failed.append(f"Google Trends: {trends_resp['error']}")
    else:
        sources_available.append("Google Trends")

    coingecko_trending_score = float(trending_resp.get("narrative_intensity_score", 0.0))
    coingecko_trending_rank = trending_resp.get("trending_rank")
    if trending_resp.get("error"):
        sources_failed.append(f"CoinGecko Trending: {trending_resp['error']}")
    else:
        sources_available.append("CoinGecko Trending")

    news_velocity_score = float(news_resp.get("news_velocity_score", 0.0))
    if news_resp.get("error"):
        sources_failed.append(f"News: {news_resp['error']}")
    else:
        sources_available.append("News Velocity")

    narrative_intensity = float(
        (google_trends_spike + coingecko_trending_score + news_velocity_score) / 3
    )

    # ==================== CAPITAL LAYER ====================
    etf_flow_direction_score = float(etf_resp.get("etf_flow_direction_score", 50.0))
    etf_flow_latest = float(etf_resp.get("daily_net_flow_latest", 0.0))
    if etf_resp.get("error"):
        sources_failed.append(f"ETF Flows: {etf_resp['error']}")
    else:
        sources_available.append("ETF Flows")

    funding_extremity_score = float(funding_resp.get("funding_extremity_score", 0.0))
    current_funding_rate = float(funding_resp.get("current_funding_rate", 0.0))
    if funding_resp.get("error"):
        sources_failed.append(f"Funding Rates: {funding_resp['error']}")
    else:
        sources_available.append("Funding Rates")

    open_interest_trend = oi_resp.get("oi_trend", "FLAT")

    # ==================== MOMENTUM LAYER ====================
    price_change_24h = float(market_resp.get("price_change_24h_pct", 0.0))
    if market_resp.get("error"):
        sources_failed.append(f"Market Data: {market_resp['error']}")
    else:
        sources_available.append("Market Data")

    volume_momentum_score = float(momentum_resp["score"])
    volatility_24h = float(momentum_resp.get("volatility_24h", 0.0))
    if momentum_resp.get("error"):
        sources_failed.append(f"Klines: {momentum_resp['error']}")
    else:
        sources_available.append("Klines")

    # ==================== COMPUTE FLOW SCORE ====================
    total_sources = 7
    confidence = max(0.5, len(sources_available) / total_sources)

    flow_score_result = compute_flow_score(
        google_trends_spike=google_trends_spike,
        coingecko_trending_score=coingecko_trending_score,
        etf_flow_direction_score=etf_flow_direction_score,
        funding_extremity_score=funding_extremity_score,
        volume_momentum_score=volume_momentum_score,
        confidence=confidence,
    )
    flow_score = flow_score_result["flow_score"]

    # ==================== DETECT DIVERGENCES ====================
    divergences = detect_divergences(
        flow_score=flow_score,
        google_trends=google_trends_spike,
        coingecko_trending=coingecko_trending_score,
        etf_flow_direction=etf_flow_direction_score,
        funding_extremity=funding_extremity_score,
        volume_momentum=volume_momentum_score,
        price_change_24h=price_change_24h,
    )

    # ==================== DETERMINE RISK LEVEL ====================
    if (flow_score > RISK_THRESHOLDS["EXTREME"]["flow_score_min"]
            and funding_extremity_score > RISK_THRESHOLDS["EXTREME"]["funding_extremity_min"]):
        risk_level = "EXTREME"
    elif (flow_score > RISK_THRESHOLDS["ELEVATED"]["flow_score_min"]
            or funding_extremity_score > RISK_THRESHOLDS["ELEVATED"]["funding_extremity_min"]):
        risk_level = "ELEVATED"
    else:
        risk_level = "CALM"

    # ==================== HISTORICAL DELTA ====================
    flow_score_delta_24h = _compute_24h_delta(asset, flow_score)

    # ==================== BUILD RESULT ====================
    now_iso = datetime.now(timezone.utc).isoformat()
    result = {
        "asset":                  asset,
        "timestamp_utc":          now_iso,
        "flow_score":             float(flow_score),
        "flow_score_percentile":  float(flow_score_result["flow_score_percentile"]),
        "flow_score_delta_24h":   float(flow_score_delta_24h),
        "confidence":             float(confidence),
        "signal_strength":        flow_score_result["signal_strength"],
        "component_breakdown":    flow_score_result["component_breakdown"],
        "layers": {
            "attention": {
                "google_trends_spike":      google_trends_spike,
                "coingecko_trending_rank":  coingecko_trending_rank,
                "coingecko_trending_score": coingecko_trending_score,
                "news_velocity_score":      news_velocity_score,
                "narrative_intensity":      narrative_intensity,
            },
            "capital": {
                "etf_flow_latest_usd":      etf_flow_latest,
                "etf_flow_5d_sum":          float(etf_resp.get("etf_flow_5d_sum", 0.0)),
                "etf_flow_direction_score": etf_flow_direction_score,
                "funding_rate_current":     current_funding_rate,
                "funding_rate_percentile":  float(funding_resp.get("funding_rate_30d_percentile", 0.0)),
                "funding_extremity_score":  funding_extremity_score,
                "funding_interpretation":   funding_resp.get("interpretation", "N/A"),
                "open_interest_trend":      open_interest_trend,
            },
            "momentum": {
                "volume_momentum_score": volume_momentum_score,
                "price_change_24h":      price_change_24h,
                "volatility_24h":        volatility_24h,
            },
        },
        "divergences": divergences,
        "risk_level":  risk_level,
        "data_quality": {
            "sources_available": sources_available,
            "sources_failed":    sources_failed,
            "last_updated": {
                "attention": now_iso,
                "capital":   now_iso,
                "momentum":  now_iso,
            },
        },
    }

    cache.set(cache_key, result)
    _store_history_snapshot(asset, flow_score)
    logger.info(f"Signals computed for {asset}: Flow Score = {flow_score:.1f}")
    return result


def _store_history_snapshot(asset: str, flow_score: float) -> None:
    """Append current flow score to a small rolling history (max 200 points)."""
    history_key = f"history_{asset}"
    history = cache.get(history_key, ttl_minutes=999_999) or []
    history.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "flow_score": float(flow_score),
    })
    history = history[-200:]
    cache.set(history_key, history)


def _compute_24h_delta(asset: str, current_score: float) -> float:
    """Look up the closest snapshot from ~24h ago and compute delta."""
    history = cache.get(f"history_{asset}", ttl_minutes=999_999) or []
    if not history:
        return 0.0

    now = datetime.now(timezone.utc)
    target_age_seconds = 24 * 3600
    best = None
    best_diff = float("inf")
    for entry in history:
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = (now - ts).total_seconds()
            diff = abs(age - target_age_seconds)
            if diff < best_diff:
                best_diff = diff
                best = entry
        except Exception:
            continue

    if best is None:
        return 0.0
    return float(current_score - best["flow_score"])
