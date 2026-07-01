"""Tests for error_learner.py: render error categorization, migration, and learning loop."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import error_learner


# ── Categorization fix (#1: RAM kills → memory_error) ─────────────────────────

def test_categorize_ram_kill_as_memory_error():
    """RAM kills should be categorized as memory_error, not unknown."""
    error = "Render killed: system RAM hit 92% (0.6 GB free). Simplify the scene."
    assert error_learner._categorize_error(error) == "memory_error"


def test_categorize_ram_kill_lowercase():
    """RAM detection should be case-insensitive."""
    error = "render killed: system ram hit 92% (0.6 gb free)"
    assert error_learner._categorize_error(error) == "memory_error"


def test_categorize_memory_still_works():
    """Existing 'memory' keyword should still match."""
    error = "MemoryError: unable to allocate 2.5 GiB"
    assert error_learner._categorize_error(error) == "memory_error"


def test_categorize_oom_still_works():
    """Existing 'oom' keyword should still match."""
    error = "OOM killer invoked, process terminated"
    assert error_learner._categorize_error(error) == "memory_error"


# ── Migration logic (#2: backfill signatures, dedup) ──────────────────────────

def test_migrate_legacy_entries_adds_signatures():
    """Legacy entries without signatures should get them after migration."""
    legacy_data = [
        {"error": "Render killed: system RAM hit 92%", "count": 1, "timestamp": "2024-01-01T00:00:00"},
        {"error": "SyntaxError: invalid syntax", "count": 1, "timestamp": "2024-01-01T00:00:00"},
    ]
    migrated = error_learner._migrate_legacy_entries(legacy_data)
    assert all("signature" in entry for entry in migrated)
    assert all("category" in entry for entry in migrated)


def test_migrate_legacy_entries_deduplicates():
    """Duplicate errors should be merged during migration."""
    legacy_data = [
        {"error": "Render killed: system RAM hit 92%", "count": 1, "timestamp": "2024-01-01T00:00:00"},
        {"error": "Render killed: system RAM hit 92%", "count": 1, "timestamp": "2024-01-02T00:00:00"},
        {"error": "Render killed: system RAM hit 92%", "count": 1, "timestamp": "2024-01-03T00:00:00"},
    ]
    migrated = error_learner._migrate_legacy_entries(legacy_data)
    # All three should merge into one entry with count=3
    assert len(migrated) == 1
    assert migrated[0]["count"] == 3
    # Should keep the newest timestamp
    assert migrated[0]["timestamp"] == "2024-01-03T00:00:00"


def test_migrate_legacy_entries_recategorizes():
    """Migration should re-categorize using current logic (RAM → memory_error)."""
    legacy_data = [
        {"error": "Render killed: system RAM hit 92%", "count": 5, "timestamp": "2024-01-01T00:00:00"},
    ]
    migrated = error_learner._migrate_legacy_entries(legacy_data)
    assert migrated[0]["category"] == "memory_error"


def test_migrate_no_op_when_all_have_signatures():
    """Migration should be a no-op if all entries already have signatures."""
    data = [
        {"signature": "abc123", "category": "memory_error", "error": "RAM hit 92%", "count": 1},
    ]
    migrated = error_learner._migrate_legacy_entries(data)
    assert migrated == data  # No changes


def test_migrate_empty_list():
    """Migration should handle empty list gracefully."""
    assert error_learner._migrate_legacy_entries([]) == []


# ── End-to-end write-then-read test (the whole point) ─────────────────────────

def test_log_ram_kill_then_read_modifier(tmp_path, monkeypatch):
    """Log a RAM kill → verify it's categorized → verify modifier appears.
    
    This is the write-then-read test that proves the learning loop is closed.
    """
    # Use a temporary file for error patterns
    error_file = tmp_path / "error_patterns.json"
    monkeypatch.setattr(error_learner, "ERROR_LOG_FILE", error_file)
    
    # Step 1: Log two RAM kills (need count >= 2 to trigger modifier)
    error_msg = "Render killed: system RAM hit 92% (0.6 GB free). Simplify the scene."
    error_learner.log_error("animate sphere", error_msg, code="from manim import *")
    error_learner.log_error("animate cube", error_msg, code="from manim import *")
    
    # Step 2: Read the data back
    data = error_learner._load()
    assert len(data) == 1  # Should be deduplicated
    assert data[0]["count"] == 2
    assert data[0]["category"] == "memory_error"
    
    # Step 3: Verify the modifier is generated
    modifiers = error_learner.get_adaptive_prompt_modifiers(constrained=True)
    assert "lightweight" in modifiers.lower()
    assert "updater" in modifiers.lower() or "surface" in modifiers.lower()


def test_log_different_errors_separate_categories(tmp_path, monkeypatch):
    """Different error types should be categorized separately."""
    error_file = tmp_path / "error_patterns.json"
    monkeypatch.setattr(error_learner, "ERROR_LOG_FILE", error_file)
    
    # Log a RAM kill and a syntax error
    error_learner.log_error("prompt1", "Render killed: system RAM hit 92%", code="")
    error_learner.log_error("prompt2", "SyntaxError: invalid syntax at line 42", code="")
    
    data = error_learner._load()
    categories = {entry["category"] for entry in data}
    assert "memory_error" in categories
    assert "syntax_error" in categories


# ── Backward compatibility (empty store → no regression) ──────────────────────

def test_empty_store_no_modifiers(tmp_path, monkeypatch):
    """Empty error store should produce no modifiers (backward compat)."""
    error_file = tmp_path / "error_patterns.json"
    monkeypatch.setattr(error_learner, "ERROR_LOG_FILE", error_file)
    
    modifiers = error_learner.get_adaptive_prompt_modifiers(constrained=True)
    assert modifiers == ""


def test_single_memory_error_triggers_modifier_on_constrained(tmp_path, monkeypatch):
    """A single memory error SHOULD trigger the modifier on constrained tier (threshold is 1)."""
    error_file = tmp_path / "error_patterns.json"
    monkeypatch.setattr(error_learner, "ERROR_LOG_FILE", error_file)

    error_learner.log_error("prompt", "Render killed: system RAM hit 92%", code="")

    # memory_error has threshold >= 1 (not 2) — even one RAM kill triggers it
    modifiers = error_learner.get_adaptive_prompt_modifiers(constrained=True)
    assert "lightweight" in modifiers.lower()


def test_single_memory_error_no_modifier_on_capable(tmp_path, monkeypatch):
    """A single memory error should NOT trigger the modifier on capable tier."""
    error_file = tmp_path / "error_patterns.json"
    monkeypatch.setattr(error_learner, "ERROR_LOG_FILE", error_file)

    error_learner.log_error("prompt", "Render killed: system RAM hit 92%", code="")

    # On capable tier (constrained=False), memory modifier is suppressed
    modifiers = error_learner.get_adaptive_prompt_modifiers(constrained=False)
    assert modifiers == ""


def test_single_non_memory_error_below_threshold(tmp_path, monkeypatch):
    """A single non-memory error (count=1) should not trigger modifiers (threshold is 2)."""
    error_file = tmp_path / "error_patterns.json"
    monkeypatch.setattr(error_learner, "ERROR_LOG_FILE", error_file)

    error_learner.log_error("prompt", "SyntaxError: invalid syntax at line 42", code="")

    modifiers = error_learner.get_adaptive_prompt_modifiers(constrained=True)
    assert modifiers == ""  # Below threshold of 2


# ── Dedup and cap tests ───────────────────────────────────────────────────────

def test_dedup_same_error(tmp_path, monkeypatch):
    """Logging the same error multiple times should increment count, not add entries."""
    error_file = tmp_path / "error_patterns.json"
    monkeypatch.setattr(error_learner, "ERROR_LOG_FILE", error_file)
    
    error_msg = "Render killed: system RAM hit 92%"
    for _ in range(5):
        error_learner.log_error("prompt", error_msg, code="")
    
    data = error_learner._load()
    assert len(data) == 1
    assert data[0]["count"] == 5


def test_dedup_with_number_normalization(tmp_path, monkeypatch):
    """Errors differing only in numbers should be deduped (numbers → # in signature)."""
    error_file = tmp_path / "error_patterns.json"
    monkeypatch.setattr(error_learner, "ERROR_LOG_FILE", error_file)
    
    # These differ in RAM percentage and GB free, but should dedup
    error_learner.log_error("p1", "Render killed: system RAM hit 92% (0.6 GB free)", code="")
    error_learner.log_error("p2", "Render killed: system RAM hit 95% (0.3 GB free)", code="")
    error_learner.log_error("p3", "Render killed: system RAM hit 88% (1.2 GB free)", code="")
    
    data = error_learner._load()
    assert len(data) == 1
    assert data[0]["count"] == 3
