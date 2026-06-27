"""Error Pattern Learner — remembers LLM failures and adapts prompts.

Tracks patterns in code generation errors to proactively avoid them
in future prompts, reducing repeat failures.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

ERROR_LOG_FILE = Path(__file__).parent / "data" / "error_patterns.json"
ERROR_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Pattern expiry: 7 days
PATTERN_TTL_DAYS = 7


def _load() -> list[dict]:
    """Load error patterns from disk."""
    if not ERROR_LOG_FILE.exists():
        return []
    try:
        return json.loads(ERROR_LOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(data: list[dict]) -> None:
    """Save error patterns to disk."""
    # Prune expired entries
    cutoff = datetime.now() - timedelta(days=PATTERN_TTL_DAYS)
    data = [p for p in data if datetime.fromisoformat(p["timestamp"]) > cutoff]
    ERROR_LOG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def log_error(prompt: str, error_message: str, code: str = "") -> None:
    """Log a render error for pattern learning.

    Categorizes errors and extracts patterns to avoid in future prompts.
    """
    category = _categorize_error(error_message)

    data = _load()
    data.append({
        "prompt_snippet": prompt[:100],
        "error": error_message[:500],
        "category": category,
        "code_snippet": code[:500] if code else "",
        "timestamp": datetime.now().isoformat(),
    })
    _save(data)
    logger.info(f"Error logged: {category}")


def _categorize_error(error: str) -> str:
    """Categorize an error message into a known pattern."""
    error_lower = error.lower()

    patterns = {
        "numpy_compat": [r"np\.math", r"np\.float\b", r"np\.int\b", r"np\.bool\b"],
        "missing_import": [r"importerror", r"module.*not found", r"nameerror.*not defined"],
        "syntax_error": [r"syntaxerror", r"invalid syntax", r"unexpected indent"],
        "attribute_error": [r"attributeerror", r"has no attribute"],
        "type_error": [r"typeerror", r"cannot.*unpack"],
        "manim_api": [r"unexpected keyword", r"missing.*positional", r"got multiple values"],
        "render_timeout": [r"timed out", r"timeout"],
        "memory_error": [r"memory", r"oom", r"out of memory"],
        "name_error": [r"nameerror"],
        "value_error": [r"valueerror"],
    }

    for category, regexes in patterns.items():
        for rx in regexes:
            if re.search(rx, error_lower):
                return category

    return "unknown"


def get_adaptive_prompt_modifiers(constrained: bool = True) -> str:
    """Generate prompt modifiers based on recent error patterns.

    Returns a string of instructions to add to the system prompt to avoid
    common errors observed in the last 7 days.

    Args:
        constrained: when False (capable render tier), the "keep the scene
            lightweight" memory-pressure modifier is omitted so it doesn't
            suppress ambition on hardware that can handle heavy scenes.
    """
    data = _load()
    if not data:
        return ""

    # Prune expired entries before counting
    cutoff = datetime.now() - timedelta(days=PATTERN_TTL_DAYS)
    data = [p for p in data if datetime.fromisoformat(p["timestamp"]) > cutoff]
    if not data:
        return ""

    # Count error categories
    counter = Counter(p["category"] for p in data)

    # Only add modifiers for errors that happened 2+ times
    modifiers: list[str] = []

    if counter.get("numpy_compat", 0) >= 2:
        modifiers.append(
            "CRITICAL: Use math.* not np.math.* — numpy 2.x removed np.math, np.float, np.int, np.bool"
        )
    if counter.get("missing_import", 0) >= 2:
        modifiers.append(
            "CRITICAL: Import ALL modules you use — no implicit imports. Check: from manim import *"
        )
    if counter.get("attribute_error", 0) >= 2:
        modifiers.append(
            "CRITICAL: Only use documented Manim APIs. Check method names carefully."
        )
    if counter.get("manim_api", 0) >= 2:
        modifiers.append(
            "CRITICAL: Check Manim API signatures carefully. Common errors: wrong color param name, wrong font_size position."
        )
    if counter.get("syntax_error", 0) >= 2:
        modifiers.append(
            "CRITICAL: Check Python syntax before output — matching quotes, parentheses, colons."
        )
    if constrained and counter.get("memory_error", 0) >= 1:
        modifiers.append(
            "CRITICAL: Keep scene lightweight — max 3 updaters, no Surface rendering, max 10 self.play calls, no glow effects."
        )

    if modifiers:
        return "\n\n## RECENT ERROR PATTERNS TO AVOID\n" + "\n".join(
            f"- {m}" for m in modifiers
        )
    return ""


def get_error_stats() -> dict:
    """Get error statistics for the last 7 days."""
    data = _load()
    cutoff = datetime.now() - timedelta(days=PATTERN_TTL_DAYS)
    recent = [p for p in data if datetime.fromisoformat(p["timestamp"]) > cutoff]

    return {
        "total_errors": len(recent),
        "by_category": dict(Counter(p["category"] for p in recent)),
        "top_prompts": Counter(p["prompt_snippet"][:50] for p in recent).most_common(5),
    }


def clear_old_patterns() -> int:
    """Manually clear expired patterns. Returns count removed."""
    data = _load()
    before = len(data)
    _save(data)  # _save auto-prunes
    return before - len(_load())
