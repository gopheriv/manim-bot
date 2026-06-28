"""End-to-end smoke test for the cloud render farm.

Dispatches a trivial GenScene to the GitHub Actions worker, waits for it, and
reports the downloaded mp4. Run from the repo root:

    python deploy/smoke_cloud.py

Exit code 0 = a real mp4 came back; non-zero = something is still broken
(the printed cloud_render_last_error tells you what).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow `python deploy/smoke_cloud.py` from anywhere: cloud_render.py and
# config.py live at the repo root (this file's parent's parent).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cloud_render as cr  # noqa: E402
from config import CLOUD_RENDER_REPO  # noqa: E402

SCENE = (
    "from manim import *\n"
    "class GenScene(Scene):\n"
    "    def construct(self):\n"
    "        self.play(Write(Text('AetherLab cloud OK')))\n"
    "        self.wait(0.5)\n"
)


async def _run() -> int:
    if not CLOUD_RENDER_REPO:
        print("FAIL: CLOUD_RENDER_REPO is empty (check .env)")
        return 2
    print(f">> Dispatching smoke render to {CLOUD_RENDER_REPO} (-ql for speed)...")
    out = await cr.cloud_render(SCENE, quality="-ql", fps=30, dest_dir=Path("tmp/cloud_smoke"))
    if out and out.exists() and out.stat().st_size > 1024:
        print(f"PASS: rendered {out} ({out.stat().st_size/1024:.0f} KB)")
        return 0
    print(f"FAIL: no mp4 returned. last_error: {cr.cloud_render_last_error or '(none)'}")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_run()))
