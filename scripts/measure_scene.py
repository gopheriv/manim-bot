"""Measure the Aesthetic Director panel on ONE scene, patiently.

For scenes the batch eval times out on (a slow/flaky endpoint), run the panel in
isolation with a generous per-call timeout and more retries.

    PYTHONIOENCODING=utf-8 python scripts/measure_scene.py scene08_latex_heavy
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aesthetic_director import run_panel  # noqa: E402

FRAMES = ROOT / "tests" / "gauntlet" / "frames"
TIMEOUT = 180
RETRIES = 6


async def _patient_vision(frames, caption):
    from config import VISION_PROVIDER
    from llm import chat_with_images
    return await asyncio.wait_for(chat_with_images(frames, caption, provider=VISION_PROVIDER), timeout=TIMEOUT)


async def main(scene: str):
    frames = [p.read_bytes() for p in sorted((FRAMES / scene).glob("frame_*.jpg"))]
    print(f"Measuring panel on {scene} ({len(frames)} frames)…")
    verdict = None
    for attempt in range(1, RETRIES + 1):
        try:
            verdict = await run_panel(frames, scene_hint=scene, vision_fn=_patient_vision)
            if verdict is not None:
                break
        except Exception as e:  # noqa: BLE001
            print(f"  attempt {attempt}: {type(e).__name__}: {e}")
        await asyncio.sleep(2 * attempt)
    if verdict is None:
        print("RESULT: UNMEASURED (panel returned None after retries)")
        return
    flagged = verdict.has_high_severity()
    print(f"RESULT: {'FLAG' if flagged else 'pass'} | high={verdict.high_count()} "
          f"findings={len(verdict.findings)} critics_ok={verdict.critics_ok}/{verdict.critics_run}")
    for f in verdict.findings:
        print(f"  - [{f.severity}/{f.category}@{f.location}] {f.issue[:90]}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "scene08_latex_heavy"))
