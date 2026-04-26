"""
Google Trends client.

Primary backend: trendspy (actively maintained, works as of 2026).
Fallback backend: pytrends (older library, frequently rate-limited / 400).

Works for ANY keyword — crypto, brands, people, technologies, events.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# trendspy is the primary backend
try:
    from trendspy import Trends as _TrendspyTrends
    _HAS_TRENDSPY = True
except ImportError:
    _HAS_TRENDSPY = False

# pytrends is the fallback
try:
    from pytrends.request import TrendReq as _PyTrendReq
    _HAS_PYTRENDS = True
except ImportError:
    _HAS_PYTRENDS = False

from utils.cache import cache
from utils.config import GOOGLE_TRENDS_MOVING_AVG_WINDOW
from utils.logger import log_data_fetch, setup_logger

logger = setup_logger(__name__)

VALID_TIMEFRAMES = [
    "now 1-H",
    "now 4-H",
    "now 1-d",
    "now 7-d",
    "today 1-m",
    "today 3-m",
    "today 12-m",
    "today 5-y",
    "all",
]

_REFERER_HEADER = {"referer": "https://www.google.com/"}


# ----------------------------------------------------------------------------
# Backend implementations
# ----------------------------------------------------------------------------

def _trendspy_interest_over_time(keywords: List[str], timeframe: str) -> pd.DataFrame:
    """Use trendspy to fetch interest-over-time. Returns DataFrame indexed by time."""
    tr = _TrendspyTrends()
    df = tr.interest_over_time(keywords, timeframe=timeframe, headers=_REFERER_HEADER)
    if df is None or df.empty:
        raise ValueError("trendspy returned empty interest_over_time")
    if "isPartial" in df.columns:
        df = df.drop(columns=["isPartial"])
    return df


def _trendspy_related_queries(keyword: str, timeframe: str) -> Dict[str, pd.DataFrame]:
    """Use trendspy to fetch related queries. Returns {'top': df, 'rising': df}."""
    tr = _TrendspyTrends()
    rq = tr.related_queries(keyword, timeframe=timeframe, headers=_REFERER_HEADER)
    out = {"top": pd.DataFrame(), "rising": pd.DataFrame()}
    if isinstance(rq, dict):
        if isinstance(rq.get("top"), pd.DataFrame):
            out["top"] = rq["top"]
        if isinstance(rq.get("rising"), pd.DataFrame):
            out["rising"] = rq["rising"]
    return out


def _pytrends_interest_over_time(keywords: List[str], timeframe: str, retries: int = 2) -> pd.DataFrame:
    """Fallback: use pytrends. Often rate-limited but kept for redundancy."""
    pt = _PyTrendReq(hl="en-US", tz=360)
    last = None
    for attempt in range(retries):
        try:
            pt.build_payload(keywords, timeframe=timeframe)
            break
        except Exception as e:
            last = e
            time.sleep(1.5 ** attempt)
    else:
        raise last  # pragma: no cover

    df = pt.interest_over_time()
    if df is None or df.empty:
        raise ValueError("pytrends returned empty interest_over_time")
    if "isPartial" in df.columns:
        df = df.drop(columns=["isPartial"])
    return df


def _fetch_interest_over_time(keywords: List[str], timeframe: str) -> Dict[str, Any]:
    """Try trendspy then pytrends. Return df + which backend succeeded."""
    errors = []
    if _HAS_TRENDSPY:
        try:
            df = _trendspy_interest_over_time(keywords, timeframe)
            return {"df": df, "backend": "trendspy", "errors": []}
        except Exception as e:
            errors.append(f"trendspy: {e}")
            logger.warning(f"trendspy failed for {keywords}: {e}")

    if _HAS_PYTRENDS:
        try:
            df = _pytrends_interest_over_time(keywords, timeframe)
            return {"df": df, "backend": "pytrends", "errors": errors}
        except Exception as e:
            errors.append(f"pytrends: {e}")
            logger.warning(f"pytrends failed for {keywords}: {e}")

    raise RuntimeError(" | ".join(errors) or "No Google Trends backend available")


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------

def get_google_trends_data(
    keyword: str,
    timeframe: str = "now 7-d",
    retries: int = 3,
) -> Dict[str, Any]:
    """Fetch single-keyword Google Trends interest-over-time."""
    cache_key = f"google_trends_{keyword}_{timeframe}".replace(" ", "_")
    cached = cache.get(cache_key, ttl_minutes=1440)
    if cached:
        return cached

    start_time = datetime.now(timezone.utc)
    try:
        fetch = _fetch_interest_over_time([keyword], timeframe)
        df_raw = fetch["df"]
        backend = fetch["backend"]

        if keyword not in df_raw.columns:
            col = df_raw.columns[0]
        else:
            col = keyword

        df = pd.DataFrame({
            "date":        df_raw.index,
            "trend_value": df_raw[col].astype(float).values,
        }).reset_index(drop=True)

        if len(df) < 3:
            raise ValueError(f"Insufficient data points ({len(df)}) for {keyword}")

        current_value = float(df["trend_value"].iloc[-1])
        ma_window = min(len(df), GOOGLE_TRENDS_MOVING_AVG_WINDOW)
        moving_avg = float(df["trend_value"].tail(ma_window).mean())
        trend_spike_score = float(min(100.0, max(0.0, (current_value / (moving_avg + 1e-6)) * 50)))

        oldest = float(df["trend_value"].iloc[0])
        latest = float(df["trend_value"].iloc[-1])
        trend_velocity = float(np.clip((latest - oldest) / (abs(oldest) + 1e-6), -1, 1))

        result = {
            "raw":                     df,
            "trend_spike_score":       trend_spike_score,
            "trend_velocity":          trend_velocity,
            "backend":                 backend,
            "data_freshness_minutes":  0,
            "error":                   None,
        }

        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        log_data_fetch(f"Google Trends [{backend}]", keyword, True, duration_ms)
        cache.set(cache_key, result)
        return result

    except Exception as e:
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        log_data_fetch("Google Trends", keyword, False, duration_ms, str(e))
        return {
            "raw":                     pd.DataFrame(),
            "trend_spike_score":       0.0,
            "trend_velocity":          0.0,
            "backend":                 None,
            "data_freshness_minutes":  0,
            "error":                   str(e),
        }


def get_google_trends_comparison(
    keywords: List[str],
    timeframe: str = "now 7-d",
    retries: int = 3,
) -> Dict[str, Any]:
    """Fetch multi-keyword Google Trends comparison (up to 5 keywords)."""
    if not keywords:
        return {"raw": pd.DataFrame(), "summary": {}, "winner": None,
                "backend": None, "error": "No keywords provided"}

    keywords = [k.strip() for k in keywords if k and k.strip()][:5]
    cache_key = f"trends_compare_{'_'.join(keywords)}_{timeframe}".replace(" ", "_")
    cached = cache.get(cache_key, ttl_minutes=1440)
    if cached:
        return cached

    start_time = datetime.now(timezone.utc)
    try:
        fetch = _fetch_interest_over_time(keywords, timeframe)
        df_raw = fetch["df"]
        backend = fetch["backend"]

        df = df_raw.copy()
        df["date"] = df.index
        df = df.reset_index(drop=True)

        summary = {}
        winner: Optional[str] = None
        max_current = -1.0
        for kw in keywords:
            if kw not in df.columns:
                continue
            series = df[kw].astype(float)
            current = float(series.iloc[-1])
            avg = float(series.mean())
            peak = float(series.max())
            ma_window = min(len(series), GOOGLE_TRENDS_MOVING_AVG_WINDOW)
            ma = float(series.tail(ma_window).mean())
            spike = float(min(100.0, max(0.0, (current / (ma + 1e-6)) * 50)))
            summary[kw] = {
                "current": current, "avg": avg, "peak": peak, "spike_score": spike,
            }
            if current > max_current:
                max_current = current
                winner = kw

        result = {
            "raw":     df,
            "summary": summary,
            "winner":  winner,
            "backend": backend,
            "error":   None,
        }

        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        log_data_fetch(f"Google Trends compare [{backend}]", ",".join(keywords), True, duration_ms)
        cache.set(cache_key, result)
        return result

    except Exception as e:
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        log_data_fetch("Google Trends compare", ",".join(keywords), False, duration_ms, str(e))
        return {
            "raw":     pd.DataFrame(),
            "summary": {},
            "winner":  None,
            "backend": None,
            "error":   str(e),
        }


def get_related_queries(keyword: str, timeframe: str = "today 12-m") -> Dict[str, Any]:
    """Fetch top + rising related queries for a keyword."""
    cache_key = f"related_{keyword}_{timeframe}".replace(" ", "_")
    cached = cache.get(cache_key, ttl_minutes=1440)
    if cached:
        return cached

    errors = []
    if _HAS_TRENDSPY:
        try:
            data = _trendspy_related_queries(keyword, timeframe)
            result = {
                "top":    data["top"],
                "rising": data["rising"],
                "backend": "trendspy",
                "error":   None,
            }
            cache.set(cache_key, result)
            return result
        except Exception as e:
            errors.append(f"trendspy: {e}")

    if _HAS_PYTRENDS:
        try:
            pt = _PyTrendReq(hl="en-US", tz=360)
            pt.build_payload([keyword], timeframe=timeframe)
            related = pt.related_queries() or {}
            kw_data = related.get(keyword, {}) or {}
            result = {
                "top":    kw_data.get("top") if isinstance(kw_data.get("top"), pd.DataFrame) else pd.DataFrame(),
                "rising": kw_data.get("rising") if isinstance(kw_data.get("rising"), pd.DataFrame) else pd.DataFrame(),
                "backend": "pytrends",
                "error":   None,
            }
            cache.set(cache_key, result)
            return result
        except Exception as e:
            errors.append(f"pytrends: {e}")

    return {
        "top":     pd.DataFrame(),
        "rising":  pd.DataFrame(),
        "backend": None,
        "error":   " | ".join(errors) or "No backend available",
    }
