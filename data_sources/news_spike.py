"""
News velocity via CryptoPanic API (free tier).
No auth required (DEMO token).
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import pandas as pd
import requests

from utils.cache import cache
from utils.config import NEWS_VELOCITY_MULTIPLIER, REQUEST_TIMEOUT, USER_AGENT
from utils.logger import log_data_fetch, setup_logger

logger = setup_logger(__name__)
CRYPTOPANIC_BASE_URL = "https://cryptopanic.com/api/v1"


def get_news_velocity(asset: str) -> Dict[str, Any]:
    """Fetch crypto news headlines mentioning asset, compute velocity."""
    cache_key = f"news_velocity_{asset}"
    cached = cache.get(cache_key, ttl_minutes=30)
    if cached:
        return cached

    start_time = datetime.utcnow()
    try:
        url = f"{CRYPTOPANIC_BASE_URL}/posts/"
        params = {
            "auth_token": "DEMO",
            "kind":       "news",
            "limit":      200,
        }
        resp = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])

        now_utc = datetime.now(timezone.utc)
        rows = []
        for item in results:
            try:
                title = item.get("title", "")
                if asset.upper() not in title.upper():
                    continue
                published_at_str = item.get("published_at", "")
                try:
                    published_at = datetime.fromisoformat(
                        published_at_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    published_at = now_utc

                rows.append({
                    "timestamp": published_at,
                    "headline":  title,
                    "source":    item.get("source", {}).get("title", "Unknown"),
                })
            except Exception:
                continue

        df = pd.DataFrame(rows)

        if df.empty:
            result = {
                "raw":                     df,
                "headlines_24h":           0,
                "headlines_7d_avg":        0.0,
                "news_velocity_score":     0.0,
                "news_spike_detected":     False,
                "data_freshness_minutes":  0,
                "error":                   None,
            }
            cache.set(cache_key, result)
            return result

        one_day_ago = now_utc - timedelta(days=1)
        seven_days_ago = now_utc - timedelta(days=7)

        headlines_24h = int((df["timestamp"] > one_day_ago).sum())
        headlines_last_7d = int((df["timestamp"] > seven_days_ago).sum())
        headlines_7d_avg = max(headlines_last_7d / 7, 0.1)

        velocity = headlines_24h / (headlines_7d_avg + 0.1)
        news_velocity_score = float(min(100.0, velocity * NEWS_VELOCITY_MULTIPLIER))
        news_spike_detected = headlines_24h > (headlines_7d_avg * 2)

        result = {
            "raw":                     df,
            "headlines_24h":           headlines_24h,
            "headlines_7d_avg":        float(headlines_7d_avg),
            "news_velocity_score":     news_velocity_score,
            "news_spike_detected":     bool(news_spike_detected),
            "data_freshness_minutes":  0,
            "error":                   None,
        }

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        log_data_fetch("CryptoPanic News", asset, True, duration_ms)
        cache.set(cache_key, result)
        return result

    except Exception as e:
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        log_data_fetch("CryptoPanic News", asset, False, duration_ms, str(e))
        return {
            "raw":                     pd.DataFrame(),
            "headlines_24h":           0,
            "headlines_7d_avg":        0.0,
            "news_velocity_score":     0.0,
            "news_spike_detected":     False,
            "data_freshness_minutes":  0,
            "error":                   str(e),
        }
