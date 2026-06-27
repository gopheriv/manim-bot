"""Per-animation feedback tracking — 👍/👎 inline buttons."""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

FEEDBACK_FILE = Path(__file__).parent / "data" / "feedback.json"
FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load() -> list[dict]:
    if not FEEDBACK_FILE.exists():
        return []
    try:
        return json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(data: list[dict]) -> None:
    FEEDBACK_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def log_feedback(chat_id: int, prompt: str, task_id: str, rating: str) -> None:
    """Log a 👍 or 👎 for a specific animation."""
    data = _load()
    data.append({
        "chat_id": chat_id,
        "prompt": prompt,
        "task_id": task_id,
        "rating": rating,
        "timestamp": datetime.now().isoformat(),
    })
    _save(data)
    logger.info(f"Feedback: {rating} from chat_id={chat_id} for '{prompt[:50]}'")


def get_feedback_stats() -> dict:
    """Get aggregate feedback stats."""
    data = _load()
    thumbs_up = sum(1 for d in data if d["rating"] == "thumbs_up")
    thumbs_down = sum(1 for d in data if d["rating"] == "thumbs_down")
    total = thumbs_up + thumbs_down
    return {
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "total": total,
        "positive_rate": round(thumbs_up / total * 100, 1) if total > 0 else 0,
    }
