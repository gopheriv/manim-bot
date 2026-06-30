"""Self-contained CI render script for the GitHub Actions worker.

Reads the scene code + params from env, renders with Manim, and writes the
result to out/render.mp4. Has NO project dependencies so a minimal public
worker repo needs only this file + .github/workflows/render.yml.
"""

import ast
import base64
import gzip
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
MEDIA = ROOT / "media"
OUT = ROOT / "out"

# ── Safety allowlist (mirror of code_safety.py in the main repo) ──────────────
# This worker EXECUTES the generated scene, so an injected `import os; os.system`
# would run with the runner's permissions/secrets. Kept inlined so the worker
# stays a single self-contained file. Keep in sync with code_safety.py.
_ALLOWED_IMPORT_ROOTS = {
    "manim", "numpy", "math", "cmath", "random", "statistics",
    "itertools", "functools", "operator", "fractions", "decimal",
    "typing", "dataclasses", "collections", "enum", "string", "json",
    "__future__",
}
_BANNED_NAMES = {
    "exec", "eval", "compile", "__import__", "open", "input",
    "breakpoint", "globals", "locals", "vars",
}
_BANNED_DUNDERS = {
    "__globals__", "__builtins__", "__subclasses__", "__bases__",
    "__mro__", "__code__", "__import__", "__loader__", "__spec__",
}


def _unsafe_reasons(code: str) -> list:
    """Return a list of safety violations (empty = safe). Syntax errors are not
    our concern here — the py_compile step below reports those."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    reasons = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in _ALLOWED_IMPORT_ROOTS:
                    reasons.append(f"disallowed import: {a.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0] if node.level == 0 else ""
            if root not in _ALLOWED_IMPORT_ROOTS:
                reasons.append(f"disallowed import: from {'.' * node.level}{node.module or ''}")
        elif isinstance(node, ast.Name) and node.id in _BANNED_NAMES:
            reasons.append(f"disallowed builtin: {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in _BANNED_DUNDERS:
            reasons.append(f"disallowed attribute: .{node.attr}")
    # de-dupe, preserve order
    seen = set()
    return [r for r in reasons if not (r in seen or seen.add(r))]

# Hard cap on the Manim render so a generated infinite loop can't pin a runner.
# Must stay <= the workflow's `timeout-minutes` (render.yml) or GitHub cancels the
# job first. Overridable via env for genuinely long legitimate renders.
RENDER_TIMEOUT_S = int(os.environ.get("CI_RENDER_TIMEOUT", "3600"))  # 60 min
COMPILE_TIMEOUT_S = 60


def fail(msg: str) -> "None":
    # Flush both streams so earlier render output isn't lost when we exit(1).
    sys.stdout.flush()
    sys.stderr.flush()
    print(f"::error::{msg}", flush=True)
    sys.stdout.flush()
    sys.exit(1)


def _tail(text: str, limit: int) -> str:
    """Last `limit` chars, trimmed forward to a line boundary so the snippet
    doesn't start mid-line (which is hard to read in the CI log)."""
    snippet = (text or "")[-limit:]
    nl = snippet.find("\n")
    if nl != -1 and len(text) > limit:
        snippet = snippet[nl + 1:]
    return snippet


def main() -> None:
    blob = os.environ.get("CODE_GZ", "")
    quality = os.environ.get("QUALITY", "-qh").strip() or "-qh"
    fps = os.environ.get("FPS", "60").strip() or "60"
    job_id = os.environ.get("JOB_ID", "job").strip()
    if not blob:
        fail("CODE_GZ env is empty")

    try:
        code = gzip.decompress(base64.b64decode(blob)).decode("utf-8")
    except Exception as e:  # noqa: BLE001
        fail(f"could not decode CODE_GZ: {e}")

    if "class GenScene" not in code or "def construct" not in code:
        fail("scene must define class GenScene with a construct method")

    # Safety gate (fail-closed) before we ever execute the scene.
    unsafe = _unsafe_reasons(code)
    if unsafe:
        fail("unsafe code rejected: " + "; ".join(unsafe[:10]))

    scene = ROOT / "scene.py"
    scene.write_text(code, encoding="utf-8")

    # Syntax check before the expensive render
    try:
        pc = subprocess.run([sys.executable, "-m", "py_compile", str(scene)],
                            capture_output=True, text=True, timeout=COMPILE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        fail(f"py_compile timed out after {COMPILE_TIMEOUT_S}s")
    if pc.returncode != 0:
        fail(f"python syntax error:\n{_tail(pc.stderr or pc.stdout, 1500)}")

    cmd = ["manim", quality, "--fps", fps, "--media_dir", str(MEDIA),
           str(scene), "GenScene"]
    print("Running:", " ".join(cmd), flush=True)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=RENDER_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        fail(f"manim render timed out after {RENDER_TIMEOUT_S}s "
             "(likely an infinite loop in the generated scene)")
    if r.returncode != 0:
        fail(f"manim render failed (exit {r.returncode}):\n{_tail(r.stderr or r.stdout, 2000)}")

    mp4s = sorted((MEDIA / "videos").rglob("GenScene.mp4"),
                  key=lambda p: p.stat().st_size, reverse=True)
    mp4s = [p for p in mp4s if p.stat().st_size > 1024]
    if not mp4s:
        fail("manim exited 0 but no GenScene.mp4 was produced")

    OUT.mkdir(parents=True, exist_ok=True)
    # copy (not copy2): on an ephemeral CI runner the source mtime/permissions
    # are irrelevant — only the bytes need to reach out/render.mp4.
    shutil.copy(mp4s[0], OUT / "render.mp4")
    size_kb = (OUT / "render.mp4").stat().st_size / 1024
    print(f"::notice::rendered job {job_id} -> out/render.mp4 ({size_kb:.0f} KB)", flush=True)


if __name__ == "__main__":
    main()
