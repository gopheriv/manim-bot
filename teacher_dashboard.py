"""Teacher Dashboard — analytics for educators tracking animation usage."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

TEACHER_DATA_PATH = Path(__file__).parent / "data" / "teacher_analytics.json"
TEACHER_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load() -> dict:
    if not TEACHER_DATA_PATH.exists():
        return {"classes": {}, "assignments": []}
    try:
        return json.loads(TEACHER_DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"classes": {}, "assignments": []}


def _save(data: dict) -> None:
    TEACHER_DATA_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def register_teacher(chat_id: int, name: str = "") -> dict:
    """Register a teacher account."""
    data = _load()
    cid = str(chat_id)

    if cid in data["classes"]:
        return data["classes"][cid]

    data["classes"][cid] = {
        "chat_id": chat_id,
        "name": name or f"Teacher {chat_id}",
        "registered_at": datetime.now().isoformat(),
        "students": [],
        "total_assignments": 0,
        "total_views": 0,
    }
    _save(data)
    return data["classes"][cid]


def add_student(teacher_id: int, student_id: int) -> bool:
    """Add a student to a teacher's class."""
    data = _load()
    tid = str(teacher_id)

    if tid not in data["classes"]:
        return False

    if student_id not in data["classes"][tid]["students"]:
        data["classes"][tid]["students"].append(student_id)
        _save(data)
    return True


def track_student_view(teacher_id: int, animation_prompt: str) -> None:
    """Track when a student views an animation."""
    data = _load()
    tid = str(teacher_id)

    if tid not in data["classes"]:
        return

    data["classes"][tid]["total_views"] += 1
    _save(data)


def get_teacher_dashboard(chat_id: int) -> dict:
    """Get dashboard data for a teacher."""
    data = _load()
    cid = str(chat_id)

    if cid not in data["classes"]:
        return None

    teacher = data["classes"][cid]
    return {
        "name": teacher["name"],
        "students": len(teacher["students"]),
        "total_assignments": teacher["total_assignments"],
        "total_views": teacher["total_views"],
        "registered_at": teacher["registered_at"][:10],
    }


def get_engagement_stats(chat_id: int) -> dict:
    """Get engagement stats for a teacher's class."""
    data = _load()
    cid = str(chat_id)

    if cid not in data["classes"]:
        return {"students": 0, "views": 0, "engagement_rate": 0}

    teacher = data["classes"][cid]
    students = len(teacher["students"])
    views = teacher["total_views"]

    return {
        "students": students,
        "total_views": views,
        "avg_views_per_student": round(views / students, 1) if students > 0 else 0,
        "engagement_rate": min(100, views * 10) if students > 0 else 0,  # Simplified metric
    }
