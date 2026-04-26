"""
Keyword search engine: works for ANY term — celebrities, products, brands,
technologies, events. Combines Google Trends + Google News RSS.

This is the non-crypto counterpart to engine/signal_engine.py.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, List

import numpy as np

from data_sources.google_news import get_google_news_velocity
from data_sources.google_trends import (
    get_google_trends_comparison,
    get_google_trends_data,
    get_related_queries,
)
from utils.cache import cache
from utils.logger import setup_logger

logger = setup_logger(__name__)


def compute_keyword_signals(
    keyword: str,
    timeframe: str = "now 7-d",
    use_cache: bool = True,
    cache_ttl_minutes: int = 30,
    include_related: bool = True,
) -> Dict[str, Any]:
    """
    Compute attention signals for any keyword.

    Args:
        keyword: free-form search term, e.g., "AI", "Taylor Swift", "Tesla"
        timeframe: pytrends timeframe string
        use_cache: read from cache when fresh
        cache_ttl_minutes: cache TTL
        include_related: also fetch related rising queries

    Returns: unified signal payload (see schema in README).
    """
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("Keyword must not be empty")

    cache_key = f"keyword_signals_{keyword}_{timeframe}".replace(" ", "_")
    if use_cache:
        cached = cache.get(cache_key, ttl_minutes=cache_ttl_minutes)
        if cached:
            return cached

    sources_available: List[str] = []
    sources_failed: List[str] = []

    logger.info(f"Computing keyword signals for: {keyword!r} @ {timeframe}")

    # ---------- Parallel fetch: Trends + News + Related ----------
    with ThreadPoolExecutor(max_workers=3) as executor:
        f_trends  = executor.submit(get_google_trends_data, keyword, timeframe)
        f_news    = executor.submit(get_google_news_velocity, keyword)
        f_related = executor.submit(get_related_queries, keyword, timeframe) if include_related else None
        trends_resp = f_trends.result()
        news_resp   = f_news.result()
        related_resp = f_related.result() if f_related is not None else None

    # ---------- Google Trends ----------
    trends_score = float(trends_resp.get("trend_spike_score", 0.0))
    trends_velocity = float(trends_resp.get("trend_velocity", 0.0))
    trends_df = trends_resp.get("raw")
    if trends_resp.get("error"):
        sources_failed.append(f"Google Trends: {trends_resp['error']}")
    else:
        sources_available.append("Google Trends")

    if trends_df is not None and not trends_df.empty:
        current_value = float(trends_df["trend_value"].iloc[-1])
        peak_value = float(trends_df["trend_value"].max())
        average_value = float(trends_df["trend_value"].mean())
    else:
        current_value = peak_value = average_value = 0.0

    # ---------- Google News RSS ----------
    news_score = float(news_resp.get("news_velocity_score", 0.0))
    news_24h = int(news_resp.get("headlines_24h", 0))
    news_7d_avg = float(news_resp.get("headlines_7d_avg", 0.0))
    news_total = int(news_resp.get("headlines_total", 0))
    news_spike = bool(news_resp.get("news_spike_detected", False))
    news_df = news_resp.get("raw")
    top_sources = news_resp.get("top_sources", {}) or {}
    if news_resp.get("error"):
        sources_failed.append(f"Google News: {news_resp['error']}")
    else:
        sources_available.append("Google News")

    # ---------- Composite Attention Score ----------
    # Trends weighted heavier than news because it is a more universal signal.
    confidence = max(0.5, len(sources_available) / 2)
    raw_score = (trends_score * 0.6) + (news_score * 0.4)
    attention_score = float(np.clip(raw_score * confidence, 0, 100))

    if attention_score > 70:
        signal_strength = "STRONG"
    elif attention_score > 40:
        signal_strength = "MODERATE"
    else:
        signal_strength = "WEAK"

    if news_spike and trends_velocity > 0.3:
        narrative_state = "BREAKING / VIRAL"
    elif trends_velocity > 0.3 and news_24h > 0:
        narrative_state = "RISING ATTENTION"
    elif trends_velocity < -0.3:
        narrative_state = "FADING"
    else:
        narrative_state = "STABLE"

    # ---------- Related Queries (already fetched above) ----------
    related_top: List[Dict[str, Any]] = []
    related_rising: List[Dict[str, Any]] = []
    if include_related and related_resp is not None:
        if related_resp.get("error"):
            sources_failed.append(f"Related queries: {related_resp['error']}")
        else:
            sources_available.append("Related Queries")

        top_df = related_resp.get("top")
        rising_df = related_resp.get("rising")
        if top_df is not None and not top_df.empty:
            related_top = top_df.head(10).to_dict(orient="records")
        if rising_df is not None and not rising_df.empty:
            related_rising = rising_df.head(10).to_dict(orient="records")

    now_iso = datetime.now(timezone.utc).isoformat()
    result = {
        "keyword":          keyword,
        "timeframe":        timeframe,
        "timestamp_utc":    now_iso,

        "attention_score":  attention_score,
        "confidence":       float(confidence),
        "signal_strength":  signal_strength,
        "narrative_state":  narrative_state,

        "trends": {
            "raw":               trends_df,
            "trend_spike_score": trends_score,
            "trend_velocity":    trends_velocity,
            "current_value":     current_value,
            "peak_value":        peak_value,
            "average_value":     average_value,
            "error":             trends_resp.get("error"),
        },
        "news": {
            "raw":                 news_df,
            "headlines_24h":       news_24h,
            "headlines_7d_avg":    news_7d_avg,
            "headlines_total":     news_total,
            "news_velocity_score": news_score,
            "news_spike_detected": news_spike,
            "top_sources":         top_sources,
            "error":               news_resp.get("error"),
        },
        "related": {
            "top":    related_top,
            "rising": related_rising,
        },
        "data_quality": {
            "sources_available": sources_available,
            "sources_failed":    sources_failed,
            "last_updated":      now_iso,
        },
    }

    cache.set(cache_key, result)
    logger.info(
        f"Keyword signals: {keyword!r} | attention={attention_score:.1f} | "
        f"news_24h={news_24h} | state={narrative_state}"
    )
    return result


def compare_keywords(
    keywords: List[str],
    timeframe: str = "now 7-d",
    use_cache: bool = True,
    cache_ttl_minutes: int = 30,
) -> Dict[str, Any]:
    """
    Compare up to 5 keywords side-by-side via Google Trends multi-keyword query
    plus per-keyword news velocity.
    """
    keywords = [k.strip() for k in keywords if k and k.strip()][:5]
    if not keywords:
        raise ValueError("At least one keyword is required")

    cache_key = f"keyword_compare_{'_'.join(keywords)}_{timeframe}".replace(" ", "_")
    if use_cache:
        cached = cache.get(cache_key, ttl_minutes=cache_ttl_minutes)
        if cached:
            return cached

    logger.info(f"Comparing keywords: {keywords} @ {timeframe}")

    with ThreadPoolExecutor(max_workers=min(6, len(keywords) + 1)) as executor:
        f_trends = executor.submit(get_google_trends_comparison, keywords, timeframe)
        news_futures = {kw: executor.submit(get_google_news_velocity, kw) for kw in keywords}
        trends_resp = f_trends.result()
        news_results = {kw: f.result() for kw, f in news_futures.items()}

    trends_df = trends_resp.get("raw")
    summary = trends_resp.get("summary", {}) or {}
    winner = trends_resp.get("winner")

    per_keyword = {}
    for kw in keywords:
        news_resp = news_results[kw]
        per_keyword[kw] = {
            "trends":              summary.get(kw, {}),
            "news_velocity_score": float(news_resp.get("news_velocity_score", 0.0)),
            "headlines_24h":       int(news_resp.get("headlines_24h", 0)),
            "headlines_total":     int(news_resp.get("headlines_total", 0)),
            "news_error":          news_resp.get("error"),
        }

    now_iso = datetime.now(timezone.utc).isoformat()
    result = {
        "keywords":      keywords,
        "timeframe":     timeframe,
        "timestamp_utc": now_iso,
        "trends_raw":    trends_df,
        "summary":       summary,
        "winner":        winner,
        "per_keyword":   per_keyword,
        "trends_error":  trends_resp.get("error"),
    }

    cache.set(cache_key, result)
    return result
