"""
Simple structured logging for debugging and monitoring.
"""

import logging
from typing import Optional

from utils.config import LOG_LEVEL, LOG_FORMAT


def setup_logger(name: str) -> logging.Logger:
    """Set up a logger for a module."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(LOG_LEVEL)
    return logger


def log_data_fetch(
    source: str,
    asset: str,
    success: bool,
    duration_ms: float,
    error_msg: Optional[str] = None,
) -> None:
    """Log a data fetch event in structured format."""
    logger = setup_logger("signalstack.data")
    status = "SUCCESS" if success else "FAILED"
    msg = f"{status}: {source} / {asset} ({duration_ms:.0f}ms)"
    if error_msg:
        msg += f" - {error_msg}"
    logger.log(logging.INFO if success else logging.WARNING, msg)
