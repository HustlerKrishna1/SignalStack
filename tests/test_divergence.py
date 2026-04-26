"""
Tests for divergence pattern detection.
"""

from engine.divergence_detector import detect_divergences


def _names(signals):
    return {s["pattern_name"] for s in signals}


class TestDivergenceDetector:
    def test_smart_money_accumulation_triggered(self):
        signals = detect_divergences(
            flow_score=50,
            google_trends=20,         # low retail attention
            coingecko_trending=20,
            etf_flow_direction=80,    # high ETF inflow
            funding_extremity=40,
            volume_momentum=50,
            price_change_24h=1.0,
        )
        assert "smart_money_accumulation" in _names(signals)
        smart = next(s for s in signals if s["pattern_name"] == "smart_money_accumulation")
        assert smart["bias"] == "BULLISH"

    def test_hype_without_conviction_triggered(self):
        signals = detect_divergences(
            flow_score=50,
            google_trends=80,         # high retail
            coingecko_trending=80,
            etf_flow_direction=20,    # low ETF
            funding_extremity=40,
            volume_momentum=50,
            price_change_24h=1.0,
        )
        assert "hype_without_conviction" in _names(signals)
        hype = next(s for s in signals if s["pattern_name"] == "hype_without_conviction")
        assert hype["bias"] == "BEARISH"

    def test_trapped_longs_triggered(self):
        signals = detect_divergences(
            flow_score=60,
            google_trends=50,
            coingecko_trending=50,
            etf_flow_direction=50,
            funding_extremity=95,     # extreme funding
            volume_momentum=50,
            price_change_24h=1.0,     # flat price
        )
        assert "trapped_longs" in _names(signals)

    def test_momentum_breakout_triggered(self):
        signals = detect_divergences(
            flow_score=80,
            google_trends=70,
            coingecko_trending=70,
            etf_flow_direction=70,
            funding_extremity=50,     # not too extreme
            volume_momentum=70,
            price_change_24h=2.0,
        )
        assert "momentum_breakout" in _names(signals)
        mom = next(s for s in signals if s["pattern_name"] == "momentum_breakout")
        assert mom["bias"] == "BULLISH"

    def test_conflicting_signals_triggered(self):
        signals = detect_divergences(
            flow_score=50,
            google_trends=10,
            coingecko_trending=10,
            etf_flow_direction=80,    # large gap vs attention (10)
            funding_extremity=50,
            volume_momentum=50,
            price_change_24h=0.0,
        )
        assert "conflicting_signals" in _names(signals)

    def test_no_signals_when_neutral(self):
        signals = detect_divergences(
            flow_score=50,
            google_trends=50,
            coingecko_trending=50,
            etf_flow_direction=50,
            funding_extremity=50,
            volume_momentum=50,
            price_change_24h=1.0,
        )
        assert signals == []

    def test_signals_have_required_fields(self):
        signals = detect_divergences(
            flow_score=80, google_trends=70, coingecko_trending=70,
            etf_flow_direction=70, funding_extremity=50, volume_momentum=70,
            price_change_24h=2.0,
        )
        for s in signals:
            for field in ("pattern_name", "bias", "confidence",
                          "explanation", "suggested_action", "inputs_used"):
                assert field in s
            assert s["bias"] in ("BULLISH", "BEARISH", "NEUTRAL")
            assert 0 <= s["confidence"] <= 1
