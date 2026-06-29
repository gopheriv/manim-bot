"""Small cross-cutting helpers shared across modules.

Kept dependency-free (stdlib only) so any module can import it without creating
import cycles.
"""

from __future__ import annotations

import json
import re
import sys

# ── Subprocess window suppression (Windows) ──────────────────────────────────
# On Windows, launching a console subprocess (ffmpeg, gh, py_compile, …) without
# this flag flashes a console window. It is a no-op everywhere else. Previously
# this magic number (0x08000000) was duplicated across renderer.py, voiceover.py,
# stt.py, visual_critic.py, watermark.py and *missing* from cloud_render.py.
CREATE_NO_WINDOW = 0x08000000


def subprocess_creation_flags() -> int:
    """creationflags value that hides the console window on Windows, 0 elsewhere."""
    return CREATE_NO_WINDOW if sys.platform == "win32" else 0


# ── LLM JSON parsing ─────────────────────────────────────────────────────────
_FENCE_OPEN_RE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\n?", re.MULTILINE)
_FENCE_CLOSE_RE = re.compile(r"\n?```\s*$", re.MULTILINE)


def strip_json_fences(raw: str) -> str:
    """Remove a leading ```lang fence and trailing ``` fence, if present."""
    text = _FENCE_OPEN_RE.sub("", (raw or "").strip())
    text = _FENCE_CLOSE_RE.sub("", text.strip())
    return text.strip()


def parse_llm_json(raw: str) -> dict | None:
    """Best-effort parse of a JSON object from an LLM response.

    Strips markdown fences, then tries a direct parse. If that fails it salvages
    the FIRST balanced ``{...}`` object in the text (robust to a model emitting
    multiple objects or prose around the JSON). Returns ``None`` when nothing
    parseable is found — callers must handle that rather than crashing.
    """
    if not raw:
        return None
    text = strip_json_fences(raw)
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        pass

    salvaged = _first_json_object(text)
    if salvaged is None:
        return None
    try:
        obj = json.loads(salvaged)
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def looks_truncated(code: str) -> bool:
    """Heuristic: does this generated code look CUT OFF mid-output?

    Truncation (hitting the model's token limit) is the dominant cause of Judge
    rejections, and the right response is to *complete* the code, not regenerate
    it from scratch. We detect it deterministically: code that fails to compile
    specifically because a construct was left open / ended unexpectedly (EOF,
    unclosed bracket, dangling block) is truncated rather than merely buggy.

    Returns False for empty code (a different failure) and for code that compiles
    (syntactically complete, even if it has logic bugs).
    """
    if not code or not code.strip():
        return False
    try:
        compile(code, "<generated>", "exec")
        return False  # compiles → syntactically complete
    except SyntaxError as e:
        msg = (e.msg or "").lower()
        truncation_markers = (
            "unexpected eof",
            "was never closed",
            "expected an indented block",
            "eol while scanning",
            "unterminated",
            "expected ':'",
            "incomplete input",
        )
        if any(m in msg for m in truncation_markers):
            return True
        # A SyntaxError on the LAST line is also a strong truncation signal — the
        # output was cut mid-statement (e.g. "self.play(Create(" with no close).
        last_line = code.rstrip().splitlines()[-1].strip() if code.strip() else ""
        return bool(last_line) and e.lineno is not None and e.lineno >= len(code.splitlines()) - 1
    except Exception:
        return False


def _first_json_object(text: str) -> str | None:
    """Return the first balanced {...} substring, respecting strings/escapes.

    A simple ``\\{.*\\}`` greedy regex grabs from the first ``{`` to the LAST
    ``}`` — wrong when the model emits multiple objects or trailing prose. This
    scans for brace balance instead so we recover exactly one object.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None
