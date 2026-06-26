"""
Error analytics and statistics tracking — persisted to disk as JSON.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("analytics")

_ANALYTICS_FILE = Path(__file__).parent / "data" / "analytics.json"


def _load_analytics() -> dict:
    """Load analytics from disk."""
    try:
        return json.loads(_ANALYTICS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_analytics(data: dict):
    """Persist analytics to disk."""
    try:
        _ANALYTICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _ANALYTICS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to save analytics: {e}")


class ErrorAnalytics:
    """Track and analyze errors for debugging and improvement."""

    def __init__(self):
        persisted = _load_analytics()

        # Restore errors from disk
        self._errors: dict[str, list[str]] = defaultdict(list)  # error_type -> list of ISO timestamps
        saved_errors = persisted.get("errors", {})
        for error_type, timestamps in saved_errors.items():
            # Keep only timestamps from last 7 days (cleanup on load)
            cutoff = (datetime.now() - timedelta(hours=168)).isoformat()
            self._errors[error_type] = [t for t in timestamps if t > cutoff]

        # Restore render stats
        self._render_stats = {
            "total": persisted.get("render_stats", {}).get("total", 0),
            "success": persisted.get("render_stats", {}).get("success", 0),
            "failed": persisted.get("render_stats", {}).get("failed", 0),
            "cancelled": persisted.get("render_stats", {}).get("cancelled", 0),
            "avg_render_time": persisted.get("render_stats", {}).get("avg_render_time", 0.0),
            "total_render_time": persisted.get("render_stats", {}).get("total_render_time", 0.0),
        }

        # Restore user stats
        self._user_stats: dict[int, dict] = defaultdict(
            lambda: {"renders": 0, "success": 0, "failed": 0}
        )
        saved_users = persisted.get("user_stats", {})
        for chat_id_str, stats in saved_users.items():
            self._user_stats[int(chat_id_str)] = stats

        self._dirty = False  # track if save is needed

    def _mark_dirty(self):
        """Mark analytics as needing a save."""
        self._dirty = True

    def flush(self):
        """Persist analytics to disk if changed."""
        if self._dirty:
            data = {
                "errors": dict(self._errors),
                "render_stats": self._render_stats,
                "user_stats": {str(k): v for k, v in self._user_stats.items()},
            }
            _save_analytics(data)
            self._dirty = False
    
    def log_error(self, error_type: str, details: Optional[str] = None):
        """Log an error occurrence."""
        self._errors[error_type].append(datetime.now().isoformat())
        self._mark_dirty()
        logger.warning(f"Error logged: {error_type}" + (f" - {details}" if details else ""))

    def log_render_success(self, chat_id: int, render_time: float):
        """Log successful render."""
        self._render_stats["total"] += 1
        self._render_stats["success"] += 1
        self._render_stats["total_render_time"] += render_time
        self._render_stats["avg_render_time"] = (
            self._render_stats["total_render_time"] / self._render_stats["success"]
        )

        self._user_stats[chat_id]["renders"] += 1
        self._user_stats[chat_id]["success"] += 1
        self._mark_dirty()

    def log_render_failure(self, chat_id: int, error_type: str):
        """Log failed render."""
        self._render_stats["total"] += 1
        self._render_stats["failed"] += 1
        self._user_stats[chat_id]["renders"] += 1
        self._user_stats[chat_id]["failed"] += 1
        self.log_error(f"render_{error_type}")

    def log_render_cancelled(self, chat_id: int):
        """Log cancelled render."""
        self._render_stats["total"] += 1
        self._render_stats["cancelled"] += 1
        self._mark_dirty()
    
    def get_error_counts(self, hours: int = 24) -> dict[str, int]:
        """Get error counts within time window."""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        counts = {}
        for error_type, timestamps in self._errors.items():
            recent = [t for t in timestamps if t > cutoff]
            if recent:
                counts[error_type] = len(recent)
        return counts
    
    def get_render_stats(self) -> dict:
        """Get overall render statistics."""
        success_rate = (
            (self._render_stats["success"] / self._render_stats["total"] * 100)
            if self._render_stats["total"] > 0 else 0
        )
        
        return {
            **self._render_stats,
            "success_rate": success_rate,
        }
    
    def get_user_stats(self, chat_id: int) -> dict:
        """Get statistics for specific user."""
        return self._user_stats.get(chat_id, {"renders": 0, "success": 0, "failed": 0})
    
    def get_top_errors(self, hours: int = 24, limit: int = 10) -> list[tuple[str, int]]:
        """Get most common errors within time window."""
        counts = self.get_error_counts(hours)
        sorted_errors = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_errors[:limit]
    
    def cleanup_old_data(self, hours: int = 168):  # 7 days
        """Remove old error records."""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        changed = False
        for error_type in list(self._errors.keys()):
            before = len(self._errors[error_type])
            self._errors[error_type] = [
                t for t in self._errors[error_type] if t > cutoff
            ]
            if len(self._errors[error_type]) != before:
                changed = True
            if not self._errors[error_type]:
                del self._errors[error_type]
        if changed:
            self._mark_dirty()


# Global analytics instance
analytics = ErrorAnalytics()
