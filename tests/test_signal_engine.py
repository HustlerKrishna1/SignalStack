"""
Tests for signal engine orchestrator and flow scorer.
Pure-logic tests only — no network access required.
"""

from engine.flow_scorer import compute_flow_score, normalize_score


class TestFlowScorer:
    def test_compute_flow_score_returns_dict(self):
        result = compute_flow_score(50, 50, 50, 50, 50)
        assert isinstance(result, dict)
        for key in ("flow_score", "confidence", "component_breakdown",
                    "signal_strength", "timestamp_utc"):
            assert key in result

    def test_flow_score_bounds(self):
        result = compute_flow_score(0, 0, 0, 0, 0)
        assert result["flow_score"] == 0
        result = compute_flow_score(100, 100, 100, 100, 100)
        assert result["flow_score"] == 100

    def test_confidence_discount(self):
        full = compute_flow_score(80, 80, 80, 80, 80, confidence=1.0)
        half = compute_flow_score(80, 80, 80, 80, 80, confidence=0.5)
        assert half["flow_score"] < full["flow_score"]

    def test_signal_strength_thresholds(self):
        assert compute_flow_score(20, 20, 20, 20, 20)["signal_strength"] == "WEAK"
        assert compute_flow_score(50, 50, 50, 50, 50)["signal_strength"] == "MODERATE"
        assert compute_flow_score(85, 85, 85, 85, 85)["signal_strength"] == "STRONG"

    def test_normalize_score(self):
        assert normalize_score(50, 0, 100) == 50.0
        assert normalize_score(0, 0, 100) == 0.0
        assert normalize_score(100, 0, 100) == 100.0
        assert normalize_score(150, 0, 100) == 100.0
        assert normalize_score(-10, 0, 100) == 0.0

    def test_component_breakdown_present(self):
        result = compute_flow_score(60, 80, 70, 30, 90)
        breakdown = result["component_breakdown"]
        assert "attention" in breakdown
        assert "capital" in breakdown
        assert "momentum" in breakdown
        assert breakdown["attention"] == 70.0   # (60 + 80) / 2
        assert breakdown["capital"]   == 50.0   # (70 + 30) / 2
        assert breakdown["momentum"]  == 90.0
