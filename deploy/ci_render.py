"""Self-contained CI render script for the GitHub Actions worker.

Reads the scene code + params from env, renders with Manim, and writes the
result to out/render.mp4. Has NO project dependencies so a minimal public
worker repo needs only this file + .github/workflows/render.yml.
"""

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

# Hard cap on the Manim render so a generated infinite loop can't pin a runner
# until the job-level (6 hour) timeout, burning runner minutes. Overridable via
# env for genuinely long legitimate renders.
RENDER_TIMEOUT_S = int(os.environ.get("CI_RENDER_TIMEOUT", "1200"))  # 20 min
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
