"""
Unit tests for data source modules.

Network-touching tests are marked with `@pytest.mark.network` so they can be
skipped in CI with: pytest -m "not network".
"""

import pandas as pd
import pytest

from utils.mock_data import generate_mock_market_data


# ----------------------------------------------------------------------------
# Mock data generator
# ----------------------------------------------------------------------------
class TestMockData:
    def test_mock_data_has_required_fields(self):
        mock = generate_mock_market_data("BTC", days=30)
        required = [
            "asset", "timestamp_utc", "flow_score", "confidence",
            "layers", "divergences", "risk_level", "data_quality",
        ]
        for field in required:
            assert field in mock, f"Missing field: {field}"

    def test_flow_score_in_range(self):
        mock = generate_mock_market_data("ETH")
        assert 0 <= mock["flow_score"] <= 100

    def test_layers_structure(self):
        mock = generate_mock_market_data("SOL")
        for layer in ("attention", "capital", "momentum"):
            assert layer in mock["layers"]


# ----------------------------------------------------------------------------
# Live API tests (skip in CI)
# ----------------------------------------------------------------------------
@pytest.mark.network
class TestCoinGeckoClient:
    def test_get_market_data_returns_dict(self):
        from data_sources.coingecko_client import get_market_data
        result = get_market_data("BTC")
        assert isinstance(result, dict)
        assert "current_price_usd" in result

    def test_market_data_price_positive_when_no_error(self):
        from data_sources.coingecko_client import get_market_data
        result = get_market_data("BTC")
        if not result.get("error"):
            assert result["current_price_usd"] > 0

    def test_get_coingecko_trending_returns_dict(self):
        from data_sources.coingecko_client import get_coingecko_trending
        result = get_coingecko_trending()
        assert isinstance(result, dict)
        assert "raw" in result
        assert isinstance(result["raw"], pd.DataFrame)


@pytest.mark.network
class TestBinanceClient:
    def test_get_funding_rates_returns_dict(self):
        from data_sources.binance_client import get_funding_rates
        result = get_funding_rates("BTC")
        assert isinstance(result, dict)
        assert "current_funding_rate" in result

    def test_funding_rate_is_float(self):
        from data_sources.binance_client import get_funding_rates
        result = get_funding_rates("BTC")
        assert isinstance(result["current_funding_rate"], float)

    def test_get_klines_returns_dataframe(self):
        from data_sources.binance_client import get_klines
        result = get_klines("BTC", interval="1h", limit=24)
        assert isinstance(result, dict)
        assert "raw" in result
        assert isinstance(result["raw"], pd.DataFrame)


@pytest.mark.network
class TestGoogleTrends:
    def test_get_trends_returns_dict(self):
        from data_sources.google_trends import get_google_trends_data
        result = get_google_trends_data("Bitcoin", timeframe="now 7-d")
        assert isinstance(result, dict)
        assert "raw" in result

    def test_trend_spike_score_in_range(self):
        from data_sources.google_trends import get_google_trends_data
        result = get_google_trends_data("Bitcoin")
        if not result.get("error"):
            assert 0 <= result["trend_spike_score"] <= 100


# ----------------------------------------------------------------------------
# Pure-logic helpers
# ----------------------------------------------------------------------------
class TestEtfFlowParser:
    def test_parse_flow_value_basic(self):
        from data_sources.etf_flows_scraper import _parse_flow_value
        assert _parse_flow_value("123.4") == 123.4
        assert _parse_flow_value("$1,234.5") == 1234.5
        assert _parse_flow_value("(50.0)") == -50.0
        assert _parse_flow_value("-") == 0.0
        assert _parse_flow_value("") == 0.0
