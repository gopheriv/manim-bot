"""Phase 4 demo — run the converging refinement loop on a deliberately-flawed scene.

Renders the scene, judges it with the Aesthetic Director panel, repairs the HIGH-severity
findings with the LLM, re-renders, and repeats until convergence (no high-severity defect)
or a hard cap. Saves the keyframe SEQUENCE (pass_0 = flawed ... pass_N = converged) so a
human can OPEN them and see the composition fix itself.

    PYTHONIOENCODING=utf-8 python scripts/refine_demo.py tests/gauntlet/broken01_offframe.py
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aesthetic_director import refine_visual, run_panel  # noqa: E402
from visual_critic import extract_keyframes  # noqa: E402
from llm import repair_targeted, strip_code_fences  # noqa: E402

DEMO_DIR = ROOT / "tests" / "gauntlet" / "refine_demo"
MEDIA = Path(tempfile.gettempdir()) / "refine_demo_media"
_pass_counter = {"i": 0}


async def _render_and_frames(code: str):
    """Write code, render with manim -ql, extract 5 keyframes; also persist them per pass."""
    i = _pass_counter["i"]
    _pass_counter["i"] += 1
    scene_file = MEDIA / f"scene_pass_{i}.py"
    scene_file.parent.mkdir(parents=True, exist_ok=True)
    scene_file.write_text(code, encoding="utf-8")
    r = subprocess.run(
        ["manim", "-ql", str(scene_file), "GenScene", "--media_dir", str(MEDIA)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    if r.returncode != 0:
        print(f"  pass {i}: RENDER FAIL: {(r.stderr or r.stdout)[-200:]}")
        return None, []
    mp4s = [p for p in (MEDIA / "videos" / scene_file.stem).rglob("GenScene.mp4") if p.stat().st_size > 1024]
    if not mp4s:
        return None, []
    frames = await extract_keyframes(mp4s[0], n=5)
    out = DEMO_DIR / f"pass_{i}"
    out.mkdir(parents=True, exist_ok=True)
    for j, data in enumerate(frames):
        (out / f"frame_{j+1:02d}.jpg").write_bytes(data)
    return mp4s[0], frames


async def _panel(frames, hint):
    return await run_panel(frames, scene_hint=hint)


def _make_repair(prompt: str):
    async def repair(code: str, fix_plan: str) -> str:
        improved = await repair_targeted(
            code, [fix_plan], prompt,
            focus="visual composition, framing, readability — keep everything ON-FRAME and readable",
        )
        return strip_code_fences(improved or "")
    return repair


async def main(scene_path: Path):
    code = scene_path.read_text(encoding="utf-8")
    prompt = scene_path.stem
    if DEMO_DIR.exists():
        import shutil
        shutil.rmtree(DEMO_DIR, ignore_errors=True)
    print(f"Refining {scene_path.name} (prompt='{prompt}')\n")
    result = await refine_visual(code, _render_and_frames, _panel, _make_repair(prompt), max_passes=3)
    print("\n=== CONVERGENCE TRACE ===")
    for p in result.passes:
        tag = "CONVERGED" if p.converged else f"{p.high} high-severity"
        print(f"  pass {p.index}: {p.findings} findings, {tag}")
    print(f"\nConverged: {result.converged}")
    if result.best_verdict:
        print(f"Best pass high-severity count: {result.best_verdict.high_count()}")
        print("\nBest-pass fix plan (if any remaining):")
        print(result.best_verdict.fix_plan() or "  (clean)")
    (DEMO_DIR / "best_code.py").write_text(result.best_code, encoding="utf-8")
    print(f"\nFrames + best code saved under {DEMO_DIR}/")


if __name__ == "__main__":
    scene = Path(sys.argv[1]) if len(sys.argv) > 1 else (ROOT / "tests/gauntlet/broken01_offframe.py")
    asyncio.run(main(scene))
