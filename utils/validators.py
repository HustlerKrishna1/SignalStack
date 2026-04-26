"""
Validate that data conforms to expected schemas.
"""

from typing import Any, Dict


def validate_data_source_result(result: Dict[str, Any]) -> bool:
    """Validate that a data source result has expected schema."""
    try:
        assert isinstance(result, dict), "Result must be dict"
        assert "scores" in result, "Missing 'scores'"
        assert isinstance(result["scores"], dict), "'scores' must be dict"
        for key, val in result["scores"].items():
            if val is not None:
                assert isinstance(val, (int, float)), f"{key} must be numeric"
                assert 0 <= val <= 100, f"{key} must be 0-100, got {val}"
        return True
    except AssertionError:
        return False


def validate_signal_object(signal: Dict[str, Any]) -> bool:
    """Validate that a signal object has all required fields."""
    required_fields = [
        "asset",
        "timestamp_utc",
        "flow_score",
        "confidence",
        "layers",
        "divergences",
        "risk_level",
        "data_quality",
    ]
    try:
        for field in required_fields:
            assert field in signal, f"Missing required field: {field}"
        assert 0 <= signal["flow_score"] <= 100
        assert 0 <= signal["confidence"] <= 1
        assert signal["risk_level"] in ["CALM", "ELEVATED", "EXTREME"]
        assert isinstance(signal["divergences"], list)
        assert isinstance(signal["layers"], dict)
        for layer in ("attention", "capital", "momentum"):
            assert layer in signal["layers"], f"Missing layer: {layer}"
        return True
    except AssertionError:
        return False
