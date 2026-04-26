"""
Google News RSS client.
Free, no auth, works for ANY keyword (not just crypto).
"""

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict
from urllib.parse import quote
from xml.etree import ElementTree as ET

import pandas as pd
import requests

from utils.cache import cache
from utils.config import REQUEST_TIMEOUT, USER_AGENT
from utils.logger import log_data_fetch, setup_logger

logger = setup_logger(__name__)


def _empty_news_response(error_msg: str) -> Dict[str, Any]:
    return {
        "raw":                     pd.DataFrame(columns=["timestamp", "headline", "source", "link"]),
        "headlines_24h":           0,
        "headlines_7d_avg":        0.0,
        "news_velocity_score":     0.0,
        "news_spike_detected":     False,
        "data_freshness_minutes":  0,
        "error":                   error_msg,
    }


def get_google_news_velocity(keyword: str, hl: str = "en-US", gl: str = "US") -> Dict[str, Any]:
    """
    Fetch Google News RSS for a keyword and compute velocity metrics.

    Works for ANY keyword: people, products, brands, technologies, events.
    """
    cache_key = f"google_news_{keyword}_{hl}_{gl}"
    cached = cache.get(cache_key, ttl_minutes=30)
    if cached:
        return cached

    start_time = datetime.utcnow()
    try:
        encoded = quote(keyword)
        url = (
            f"https://news.google.com/rss/search?q={encoded}"
            f"&hl={hl}&gl={gl}&ceid={gl}:{hl.split('-')[0]}"
        )

        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        items = root.findall(".//item")

        rows = []
        for item in items:
            try:
                title = (item.findtext("title") or "").strip()
                pub_date = (item.findtext("pubDate") or "").strip()
                link = (item.findtext("link") or "").strip()
                source_el = item.find("source")
                source = source_el.text.strip() if source_el is not None and source_el.text else "Unknown"

                try:
                    ts = parsedate_to_datetime(pub_date)
                except (TypeError, ValueError):
                    ts = datetime.now(timezone.utc)

                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)

                rows.append({
                    "timestamp": ts,
                    "headline":  title,
                    "source":    source,
                    "link":      link,
                })
            except Exception:
                continue

        df = pd.DataFrame(rows)

        if df.empty:
            result = _empty_news_response(None)
            cache.set(cache_key, result)
            return result

        df = df.sort_values("timestamp", ascending=False).reset_index(drop=True)

        now_utc = datetime.now(timezone.utc)
        one_day_ago = now_utc - timedelta(days=1)
        seven_days_ago = now_utc - timedelta(days=7)

        headlines_24h = int((df["timestamp"] > one_day_ago).sum())
        headlines_last_7d = int((df["timestamp"] > seven_days_ago).sum())
        headlines_7d_avg = max(headlines_last_7d / 7, 0.1)

        velocity = headlines_24h / (headlines_7d_avg + 0.1)
        news_velocity_score = float(min(100.0, velocity * 20))
        news_spike_detected = headlines_24h > (headlines_7d_avg * 2)

        result = {
            "raw":                     df,
            "headlines_24h":           headlines_24h,
            "headlines_7d_avg":        float(headlines_7d_avg),
            "headlines_total":         int(len(df)),
            "news_velocity_score":     news_velocity_score,
            "news_spike_detected":     bool(news_spike_detected),
            "top_sources":             df["source"].value_counts().head(5).to_dict(),
            "data_freshness_minutes":  0,
            "error":                   None,
        }

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        log_data_fetch("Google News RSS", keyword, True, duration_ms)
        cache.set(cache_key, result)
        return result

    except Exception as e:
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        log_data_fetch("Google News RSS", keyword, False, duration_ms, str(e))
        return _empty_news_response(str(e))
