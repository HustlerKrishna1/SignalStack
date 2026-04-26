"""
Scrape ETF flows from Farside Investors.
Free, stable, updates daily.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict

import pandas as pd
import requests
from bs4 import BeautifulSoup

from utils.cache import cache
from utils.config import ASSET_MAP, REQUEST_TIMEOUT, USER_AGENT
from utils.logger import log_data_fetch, setup_logger

logger = setup_logger(__name__)

_NUMERIC_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


def _parse_flow_value(text: str) -> float:
    """Convert a Farside cell to a float (in USD millions)."""
    if text is None:
        return 0.0
    cleaned = text.strip().replace(",", "").replace("$", "")
    if cleaned in ("", "-", "—"):
        return 0.0
    is_negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    match = _NUMERIC_PATTERN.search(cleaned)
    if not match:
        return 0.0
    val = float(match.group(0))
    return -val if is_negative else val


def _empty_etf_response(error_msg: str) -> Dict[str, Any]:
    return {
        "raw":                        pd.DataFrame(),
        "daily_net_flow_latest":      0.0,
        "etf_flow_5d_sum":            0.0,
        "etf_flow_20d_sum":           0.0,
        "etf_flow_direction_score":   50.0,
        "etf_flow_score_percentile":  50.0,
        "data_freshness_minutes":     0,
        "error":                      error_msg,
    }


def get_etf_flows(asset: str) -> Dict[str, Any]:
    """Scrape Farside Investors ETF flows table for BTC/ETH/SOL."""
    farside_key = ASSET_MAP.get(asset, {}).get("farside")
    if not farside_key:
        return _empty_etf_response(f"Asset {asset} not supported on Farside")

    cache_key = f"etf_flows_{asset}"
    cached = cache.get(cache_key, ttl_minutes=1440)
    if cached:
        return cached

    start_time = datetime.now(timezone.utc)
    try:
        url = f"https://farside.co.uk/{farside_key}/"
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.content, "html.parser")
        tables = soup.find_all("table")
        if not tables:
            raise ValueError("No tables found on Farside page")

        target_table = None
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) > 5:
                target_table = table
                break
        if target_table is None:
            target_table = tables[0]

        rows = []
        for tr in target_table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            date_text = tds[0].get_text(strip=True)
            try:
                date_obj = pd.to_datetime(date_text, errors="raise", dayfirst=True)
            except (ValueError, TypeError):
                continue

            flow_total_text = tds[-1].get_text(strip=True)
            flow_val = _parse_flow_value(flow_total_text) * 1_000_000

            rows.append({
                "date":             date_obj,
                "net_flow_usd":     flow_val,
            })

        if not rows:
            raise ValueError("No ETF data rows parsed from table")

        df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
        df["cumulative_flow_usd"] = df["net_flow_usd"].cumsum()

        daily_net_flow_latest = float(df["net_flow_usd"].iloc[-1])
        etf_flow_5d_sum = float(df["net_flow_usd"].tail(5).sum())
        etf_flow_20d_sum = float(df["net_flow_usd"].tail(20).sum())

        if etf_flow_5d_sum > 0 and etf_flow_20d_sum > 0:
            etf_flow_direction_score = 80.0
        elif etf_flow_5d_sum > 0 and etf_flow_20d_sum <= 0:
            etf_flow_direction_score = 60.0
        elif etf_flow_5d_sum <= 0 and etf_flow_20d_sum > 0:
            etf_flow_direction_score = 30.0
        else:
            etf_flow_direction_score = 10.0

        all_5d_sums = [
            float(df["net_flow_usd"].iloc[max(0, i - 4):i + 1].sum())
            for i in range(len(df))
        ]
        if all_5d_sums:
            count_lower = sum(1 for v in all_5d_sums if v < etf_flow_5d_sum)
            etf_flow_score_percentile = float((count_lower / len(all_5d_sums)) * 100)
        else:
            etf_flow_score_percentile = 50.0

        result = {
            "raw":                        df,
            "daily_net_flow_latest":      daily_net_flow_latest,
            "etf_flow_5d_sum":            etf_flow_5d_sum,
            "etf_flow_20d_sum":           etf_flow_20d_sum,
            "etf_flow_direction_score":   float(etf_flow_direction_score),
            "etf_flow_score_percentile":  etf_flow_score_percentile,
            "data_freshness_minutes":     0,
            "error":                      None,
        }

        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        log_data_fetch("Farside ETF Flows", asset, True, duration_ms)
        cache.set(cache_key, result)
        return result

    except Exception as e:
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        log_data_fetch("Farside ETF Flows", asset, False, duration_ms, str(e))

        stale_cached = cache.get(cache_key, ttl_minutes=999_999)
        if stale_cached:
            stale_cached = dict(stale_cached)
            stale_cached["error"] = f"Fresh fetch failed: {e}. Returning stale cache."
            return stale_cached

        return _empty_etf_response(str(e))
