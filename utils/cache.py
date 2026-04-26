"""
Simple file-based caching with TTL for respecting free API limits.
Survives Streamlit reruns (stored on disk).
"""

import json
import pickle
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pathlib import Path

import pandas as pd

CACHE_DIR = Path.home() / ".signalstack_cache"
CACHE_DIR.mkdir(exist_ok=True)


def _is_jsonable(value: Any) -> bool:
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False


def _contains_dataframe(value: Any) -> bool:
    if isinstance(value, pd.DataFrame):
        return True
    if isinstance(value, dict):
        return any(_contains_dataframe(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_dataframe(v) for v in value)
    return False


class CacheManager:
    """Manage cached data with TTL expiration. Auto-detects pickle vs JSON."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)

    def _safe_key(self, key: str) -> str:
        return key.replace(" ", "_").replace("/", "_").replace(":", "_").lower()

    def _json_path(self, key: str) -> Path:
        return self.cache_dir / f"{self._safe_key(key)}.json"

    def _pickle_path(self, key: str) -> Path:
        return self.cache_dir / f"{self._safe_key(key)}.pkl"

    def get(self, key: str, ttl_minutes: int = 60) -> Optional[Any]:
        """Retrieve cached data if exists and not expired."""
        for path, loader in [
            (self._pickle_path(key), self._load_pickle),
            (self._json_path(key),   self._load_json),
        ]:
            if not path.exists():
                continue
            try:
                cached_at, value = loader(path)
                if cached_at.tzinfo is None:
                    cached_at = cached_at.replace(tzinfo=timezone.utc)
                age_minutes = (datetime.now(timezone.utc) - cached_at).total_seconds() / 60
                if age_minutes > ttl_minutes:
                    path.unlink(missing_ok=True)
                    return None
                return value
            except Exception:
                path.unlink(missing_ok=True)
                continue
        return None

    @staticmethod
    def _load_pickle(path: Path):
        with open(path, "rb") as f:
            entry = pickle.load(f)
        return datetime.fromisoformat(entry["cached_at"]), entry["value"]

    @staticmethod
    def _load_json(path: Path):
        with open(path, "r", encoding="utf-8") as f:
            entry = json.load(f)
        return datetime.fromisoformat(entry["cached_at"]), entry["value"]

    def set(self, key: str, value: Any) -> None:
        """Store data in cache. Falls back to pickle if value contains DataFrames."""
        entry_meta = {"cached_at": datetime.now(timezone.utc).isoformat(), "value": value}
        try:
            if _contains_dataframe(value) or not _is_jsonable(value):
                with open(self._pickle_path(key), "wb") as f:
                    pickle.dump(entry_meta, f)
            else:
                with open(self._json_path(key), "w", encoding="utf-8") as f:
                    json.dump(entry_meta, f, default=str)
        except Exception as e:
            print(f"Cache write failed for {key}: {e}")

    def delete(self, key: str) -> None:
        self._json_path(key).unlink(missing_ok=True)
        self._pickle_path(key).unlink(missing_ok=True)

    def clear_all(self) -> None:
        for path in self.cache_dir.glob("*.json"):
            path.unlink()
        for path in self.cache_dir.glob("*.pkl"):
            path.unlink()

    def get_cache_info(self) -> Dict[str, Any]:
        files = list(self.cache_dir.glob("*"))
        return {
            "total_entries": len(files),
            "cache_dir":     str(self.cache_dir),
            "size_mb":       round(sum(p.stat().st_size for p in files) / (1024 ** 2), 4),
        }


cache = CacheManager()
