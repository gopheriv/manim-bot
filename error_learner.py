"""Error Pattern Learner — remembers LLM failures and adapts prompts.

Tracks patterns in code generation errors to proactively avoid them
in future prompts, reducing repeat failures.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

ERROR_LOG_FILE = Path(__file__).parent / "data" / "error_patterns.json"
ERROR_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Pattern expiry, in days. All "recent errors" windows derive from this constant
# so they never drift out of sync with the documentation.
PATTERN_TTL_DAYS = 7

# ── Judge rejection memory ────────────────────────────────────────────────────
# A durable record of the exact defects the Judge rejected (with the reason and
# the offending code), so the generator is warned and never repeats the SAME
# mistake twice. Lessons live longer than render-error patterns — they are
# specific, reusable corrections rather than transient noise.
JUDGE_REJECTION_FILE = Path(__file__).parent / "data" / "judge_rejections.json"
JUDGE_REJECTION_TTL_DAYS = 30
# Strip a leading "Line 12:" / "line 7 -" so the same defect on different lines
# collapses to ONE lesson (the line number is render-specific, the lesson isn't).
_LINE_REF_RE = re.compile(r"^\s*line\s+\d+\s*[:\-–]\s*", re.IGNORECASE)


def _load() -> list[dict]:
    """Load error patterns from disk."""
    if not ERROR_LOG_FILE.exists():
        return []
    try:
        data = json.loads(ERROR_LOG_FILE.read_text(encoding="utf-8"))
        # One-time migration: backfill signatures and re-categorize old entries
        data = _migrate_legacy_entries(data)
        return data
    except Exception:
        return []


def _migrate_legacy_entries(data: list[dict]) -> list[dict]:
    """Backfill missing signatures and re-categorize old entries.
    
    Entries logged before the dedup system was added lack a 'signature' field.
    This migration computes signatures and re-categorizes them, then deduplicates
    entries with the same signature. Runs once; after migration all entries have
    signatures.
    """
    if not data:
        return data
    
    # Check if any entries need migration
    needs_migration = any("signature" not in entry for entry in data)
    if not needs_migration:
        return data
    
    logger.info("Migrating %d legacy error entries (backfilling signatures)", len(data))
    
    # Backfill signatures and re-categorize
    for entry in data:
        if "signature" not in entry:
            error_msg = entry.get("error", "")
            category = _categorize_error(error_msg)
            entry["signature"] = _error_signature(category, error_msg)
            entry["category"] = category
    
    # Deduplicate by signature (merge counts)
    merged: dict[str, dict] = {}
    for entry in data:
        sig = entry.get("signature")
        if sig in merged:
            # Merge: add counts, keep newer timestamp
            merged[sig]["count"] = merged[sig].get("count", 1) + entry.get("count", 1)
            if entry.get("timestamp", "") > merged[sig].get("timestamp", ""):
                merged[sig]["timestamp"] = entry["timestamp"]
                merged[sig]["prompt_snippet"] = entry.get("prompt_snippet", "")[:100]
                merged[sig]["code_snippet"] = entry.get("code_snippet", "")[:500]
        else:
            merged[sig] = entry.copy()
    
    result = list(merged.values())
    logger.info("Migration complete: %d entries → %d unique signatures", len(data), len(result))
    return result


def _is_fresh(ts_str: str, cutoff: datetime, *, context: str = "error pattern") -> bool:
    """True if an ISO timestamp parses and is newer than cutoff.

    Malformed timestamps are dropped (return False) WITH a diagnostic, rather
    than crashing the caller or disappearing silently.
    """
    try:
        return datetime.fromisoformat(ts_str) > cutoff
    except (ValueError, TypeError):
        logger.warning("Dropping %s with unparseable timestamp: %r", context, ts_str)
        return False


def _save(data: list[dict]) -> None:
    """Save error patterns to disk (auto-prunes entries older than the TTL)."""
    cutoff = datetime.now() - timedelta(days=PATTERN_TTL_DAYS)
    data = [p for p in data if _is_fresh(p.get("timestamp", ""), cutoff)]
    ERROR_LOG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _error_signature(category: str, error_message: str) -> str:
    """Stable signature so the SAME error in a tight loop dedupes to one entry."""
    norm = re.sub(r"\d+", "#", (error_message or "").lower())[:200]
    return hashlib.md5(f"{category}|{norm}".encode("utf-8")).hexdigest()[:12]


def log_error(prompt: str, error_message: str, code: str = "") -> None:
    """Log a render error for pattern learning.

    Categorizes errors and extracts patterns to avoid in future prompts. Repeats
    of the SAME error (e.g. a retry loop hammering the same failure) bump a count
    on the existing entry instead of inflating the log with identical rows.
    """
    category = _categorize_error(error_message)
    sig = _error_signature(category, error_message)
    now = datetime.now().isoformat()

    data = _load()
    for entry in data:
        if entry.get("signature") == sig:
            entry["count"] = entry.get("count", 1) + 1
            entry["timestamp"] = now  # refresh recency
            _save(data)
            logger.info("Error re-logged (×%d): %s", entry["count"], category)
            return

    data.append({
        "signature": sig,
        "prompt_snippet": prompt[:100],
        "error": error_message[:500],
        "category": category,
        "code_snippet": code[:500] if code else "",
        "count": 1,
        "timestamp": now,
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
        "memory_error": [r"memory", r"oom", r"out of memory", r"\bram\b", r"\bkilled\b"],
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
    common errors observed within the last PATTERN_TTL_DAYS days.

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
    data = [p for p in data if _is_fresh(p.get("timestamp", ""), cutoff)]
    if not data:
        return ""

    # Count error OCCURRENCES (weight by each entry's dedup count, so a single
    # entry seen 5× still trips the 2+ threshold).
    counter: Counter = Counter()
    for p in data:
        counter[p["category"]] += p.get("count", 1)

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
    """Get error statistics for the last PATTERN_TTL_DAYS days."""
    data = _load()
    cutoff = datetime.now() - timedelta(days=PATTERN_TTL_DAYS)
    recent = [p for p in data if _is_fresh(p.get("timestamp", ""), cutoff)]

    by_category: Counter = Counter()
    for p in recent:
        by_category[p["category"]] += p.get("count", 1)

    return {
        "total_errors": sum(p.get("count", 1) for p in recent),
        "distinct_errors": len(recent),
        "by_category": dict(by_category),
        "top_prompts": Counter(p["prompt_snippet"][:50] for p in recent).most_common(5),
    }


def clear_old_patterns() -> int:
    """Manually clear expired patterns. Returns count removed."""
    data = _load()
    before = len(data)
    _save(data)  # _save auto-prunes
    return before - len(_load())


# ── Judge rejection memory ────────────────────────────────────────────────────

def _clean_reason(reason: str) -> str:
    """Normalize a Judge reason into a reusable lesson (drop the line number)."""
    r = (reason or "").strip()
    r = _LINE_REF_RE.sub("", r)
    r = re.sub(r"\s+", " ", r).strip()
    return r[:240]


def _reason_signature(reason: str) -> str:
    """Stable signature for a lesson, so the SAME mistake dedupes across renders."""
    return hashlib.md5(_clean_reason(reason).lower().encode("utf-8")).hexdigest()[:12]


def _load_rejections() -> list[dict]:
    if not JUDGE_REJECTION_FILE.exists():
        return []
    try:
        return json.loads(JUDGE_REJECTION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_rejections(data: list[dict]) -> None:
    cutoff = datetime.now() - timedelta(days=JUDGE_REJECTION_TTL_DAYS)
    kept, dropped = [], 0
    for d in data:
        if _is_fresh(d.get("last_seen", ""), cutoff, context="judge rejection"):
            kept.append(d)
        else:
            dropped += 1
    if dropped:
        logger.info("Pruned %d expired/malformed judge-rejection lesson(s)", dropped)
    JUDGE_REJECTION_FILE.write_text(
        json.dumps(kept, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def log_judge_rejection(reasons: list[str], code: str = "", verdict: str = "") -> int:
    """Record the defects the Judge rejected (reason + offending code).

    Each distinct reason becomes a deduped "lesson" keyed by a line-number-agnostic
    signature: a repeat of the same mistake just bumps its count + last_seen.
    Returns the number of NEW distinct lessons recorded.
    """
    cleaned: list[tuple[str, str]] = []
    seen_sigs: set[str] = set()
    for r in reasons or []:
        lesson = _clean_reason(r)
        if len(lesson) < 6:
            continue  # skip empty/noise reasons
        sig = _reason_signature(r)
        if sig in seen_sigs:
            continue  # dedupe within this single rejection
        seen_sigs.add(sig)
        cleaned.append((sig, lesson))
    if not cleaned:
        return 0

    data = _load_rejections()
    index = {d["signature"]: d for d in data if "signature" in d}
    now = datetime.now().isoformat()
    new_count = 0
    for sig, lesson in cleaned:
        rec = index.get(sig)
        if rec:
            rec["count"] = rec.get("count", 1) + 1
            rec["last_seen"] = now
            if verdict:
                rec["verdict"] = verdict
        else:
            rec = {
                "signature": sig,
                "lesson": lesson,
                "verdict": verdict,
                "code_snippet": (code or "")[:300],
                "count": 1,
                "first_seen": now,
                "last_seen": now,
            }
            data.append(rec)
            index[sig] = rec
            new_count += 1
    _save_rejections(data)
    logger.info("Judge rejection logged: %d reason(s), %d new lesson(s)", len(cleaned), new_count)
    return new_count


def get_judge_avoidance_modifiers(limit: int = 10) -> str:
    """Prompt block listing past Judge-rejected defects so they are NOT repeated.

    Surfaced after the first occurrence (so the same mistake never happens twice),
    ranked by RECENCY first (a lesson seen today outranks an old high-count one),
    then by how often it has been rejected. Bounded by `limit`.
    """
    data = _load_rejections()
    cutoff = datetime.now() - timedelta(days=JUDGE_REJECTION_TTL_DAYS)
    fresh = [
        d for d in data
        if d.get("lesson") and _is_fresh(d.get("last_seen", ""), cutoff, context="judge rejection")
    ]
    if not fresh:
        return ""
    # Recency primary, frequency secondary.
    fresh.sort(key=lambda d: (d.get("last_seen", ""), d.get("count", 1)), reverse=True)
    lessons = [d["lesson"] for d in fresh[:limit]]
    return (
        "\n\n## MISTAKES THE JUDGE HAS REJECTED BEFORE — DO NOT REPEAT\n"
        "These exact defects were caught in prior reviews. Avoid every one:\n"
        + "\n".join(f"- {lsn}" for lsn in lessons)
    )


def _fresh_lessons() -> list[dict]:
    """All non-expired rejection lessons (records with a 'lesson' field)."""
    cutoff = datetime.now() - timedelta(days=JUDGE_REJECTION_TTL_DAYS)
    return [
        d for d in _load_rejections()
        if d.get("lesson") and _is_fresh(d.get("last_seen", ""), cutoff, context="judge rejection")
    ]


def get_top_judge_lessons(limit: int = 3) -> list[str]:
    """The most RECURRING rejection lessons (ranked by count, then recency).

    Used to seed the storyboard/planning prompt with the few defects that keep
    coming back, so they are designed out at planning time rather than buried in
    a code-gen footer the generator skims past.
    """
    fresh = _fresh_lessons()
    fresh.sort(key=lambda d: (d.get("count", 1), d.get("last_seen", "")), reverse=True)
    return [d["lesson"] for d in fresh[:limit]]


def get_recurring_lesson_constraints(min_count: int = 3, limit: int = 5) -> list[str]:
    """Lessons seen at least ``min_count`` times — promoted to HARD constraints.

    When the same mistake survives ``min_count`` rejections, soft guidance has
    demonstrably failed; the caller should regenerate the plan with these as
    explicit MUST-NOT rules to break the loop.
    """
    fresh = [d for d in _fresh_lessons() if d.get("count", 1) >= min_count]
    fresh.sort(key=lambda d: (d.get("count", 1), d.get("last_seen", "")), reverse=True)
    return [d["lesson"] for d in fresh[:limit]]


def get_judge_rejection_stats() -> dict:
    """Stats on the rejection memory (for /stats and diagnostics)."""
    data = _load_rejections()
    cutoff = datetime.now() - timedelta(days=JUDGE_REJECTION_TTL_DAYS)
    recent = [
        d for d in data
        if _is_fresh(d.get("last_seen", ""), cutoff, context="judge rejection")
    ]
    return {
        "distinct_lessons": len(recent),
        "total_rejections": sum(d.get("count", 1) for d in recent),
        "top": sorted(
            ((d.get("count", 1), d.get("lesson", "")) for d in recent), reverse=True
        )[:5],
    }
