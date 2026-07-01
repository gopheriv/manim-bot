"""Recipe smoke test — proves every visual metaphor recipe uses valid Manim CE APIs.

Usage:
  powershell -Command "$env:PYTHONIOENCODING='utf-8'; python scripts/recipe_smoke.py"

For every metaphor in visual_metaphors._REGISTRY:
  1. Wrap the recipe into a complete standalone scene (MovingCameraScene)
  2. Write to temp .py, run manim -ql with 120s timeout
  3. Record PASS (exit 0 + GenScene.mp4 > 1KB) or FAIL (full stderr)

Prints a per-recipe table and "X/Y recipes rendered OK".
"""
from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# ── Setup ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from visual_metaphors import _REGISTRY  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("recipe_smoke")

TIMEOUT = 120  # seconds per render


@dataclass
class Result:
    name: str
    status: str  # "PASS" | "FAIL"
    detail: str = ""


WRAPPER_TEMPLATE = """\
from manim import *
import numpy as np

class GenScene(MovingCameraScene):
    def construct(self):
{body}
        self.wait(0.5)
"""


def _build_scene(recipe: str) -> str:
    """Wrap a recipe body into a complete standalone scene."""
    body = "\n".join("        " + line for line in recipe.split("\n"))
    return WRAPPER_TEMPLATE.format(body=body)


def _render(code: str, scene_name: str) -> tuple[bool, str]:
    """Write code to temp .py and render with manim -ql."""
    with tempfile.TemporaryDirectory() as tmpdir:
        py_path = Path(tmpdir) / f"{scene_name}.py"
        py_path.write_text(code, encoding="utf-8")
        media_dir = Path(tmpdir) / "media"

        result = subprocess.run(
            ["manim", "-ql", str(py_path), "GenScene", "--media_dir", str(media_dir)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=TIMEOUT,
        )

        if result.returncode != 0:
            # Capture FULL stderr for anti-fabrication
            stderr = result.stderr or result.stdout or ""
            return False, stderr

        # Check for .mp4 output
        video_dir = media_dir / "videos" / scene_name
        if video_dir.exists():
            mp4s = list(video_dir.rglob("GenScene.mp4"))
            mp4s = [p for p in mp4s if p.stat().st_size > 1024]
            if mp4s:
                return True, f"{mp4s[0].stat().st_size / 1024:.0f} KB"

        return False, "No .mp4 > 1KB produced"


def run_smoke() -> list[Result]:
    """Run render smoke on all metaphor recipes."""
    logger.info(f"Recipe smoke test: {len(_REGISTRY)} recipes")
    logger.info(f"Timeout per render: {TIMEOUT}s")
    logger.info("=" * 70)

    results: list[Result] = []
    passed = failed = 0

    for metaphor in _REGISTRY:
        name = metaphor.name
        try:
            code = _build_scene(metaphor.recipe)
        except Exception as e:
            results.append(Result(name, "FAIL", f"scene build error: {e}"))
            failed += 1
            logger.info(f"[{passed + failed:>3}] {name}: FAIL (build error)")
            continue

        try:
            ok, detail = _render(code, f"recipe_{name}")
        except subprocess.TimeoutExpired:
            ok, detail = False, f"timed out after {TIMEOUT}s"
        except Exception as e:
            ok, detail = False, f"render error: {e}"

        status = "PASS" if ok else "FAIL"
        results.append(Result(name, status, detail))

        if ok:
            passed += 1
            logger.info(f"[{passed:>3}] {name}: PASS ({detail})")
        else:
            failed += 1
            # Show last 15 lines of stderr for anti-fabrication
            lines = (detail or "").splitlines()[-15:]
            logger.info(f"[{passed + failed:>3}] {name}: FAIL —")
            for line in lines:
                logger.info(f"    {line}")

    total = len(_REGISTRY)
    logger.info("=" * 70)
    logger.info(f"{passed}/{total} recipes rendered OK"
                f" ({failed} failed)")
    return results


def _print_table(results: list[Result]) -> None:
    """Print a summary table of all results."""
    sep = "-" * 70
    print(f"\n{sep}")
    print("RECIPE SMOKE SUMMARY")
    print(f"{sep}\n")
    print(f"{'Recipe':<30} {'Status':<8} {'Detail'}")
    print(sep)

    for r in sorted(results, key=lambda r: (r.status != "PASS", r.name)):
        detail = r.detail[:40] if r.detail and r.status == "PASS" else ""
        if r.status == "FAIL":
            lines = (r.detail or "").splitlines()
            error_line = ""
            for line in lines:
                if "Error" in line or "error:" in line.lower() or "Traceback" in line:
                    error_line = line.strip()[:60]
            detail = f"FAIL: {error_line}" if error_line else "FAIL (see log above)"
        print(f"{r.name:<30} {r.status:<8} {detail}")

    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    total = len(results)
    print(sep)
    print(f"TOTAL: {passed}/{total} recipes rendered OK ({failed} failed)")

    if failed > 0:
        print(f"\nFailures ({failed}):")
        for r in results:
            if r.status == "FAIL":
                lines = (r.detail or "").splitlines()[-5:]
                print(f"  - {r.name}:")
                for line in lines:
                    print(f"      {line}")


if __name__ == "__main__":
    results = run_smoke()
    _print_table(results)

    failed = sum(1 for r in results if r.status == "FAIL")
    sys.exit(1 if failed else 0)
