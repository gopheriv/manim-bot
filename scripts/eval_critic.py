"""Evaluate a visual-defect judge against the Phase-0 labeled set.

Loads tests/gauntlet/labels.json, runs a judge over each scene's keyframes (with
retries for the flaky vision endpoint), and prints a precision/recall report.

    PYTHONIOENCODING=utf-8 python scripts/eval_critic.py baseline
    PYTHONIOENCODING=utf-8 python scripts/eval_critic.py panel

A scene that never returns a parseable verdict after retries is recorded as an ERROR
(excluded from precision/recall) — never guessed.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aesthetic_metrics import EvalRow, format_report  # noqa: E402
from common import parse_llm_json  # noqa: E402
from config import VISION_PROVIDER  # noqa: E402
from llm import chat_with_images  # noqa: E402
from visual_critic import VISUAL_CRITIC_PROMPT  # noqa: E402

LABELS = ROOT / "tests" / "gauntlet" / "labels.json"
FRAMES = ROOT / "tests" / "gauntlet" / "frames"
RETRIES = 4


def load_labels() -> list[dict]:
    return json.loads(LABELS.read_text(encoding="utf-8"))["scenes"]


def load_frames(scene: str) -> list[bytes]:
    d = FRAMES / scene
    return [p.read_bytes() for p in sorted(d.glob("frame_*.jpg"))]


async def _baseline_judge(frames: list[bytes], scene: str) -> tuple[bool | None, str]:
    """The CURRENT visual_critic rubric: one call, one rubric. flagged = not passed."""
    caption = (
        f"{VISUAL_CRITIC_PROMPT}\n\nThe animation frames are in chronological order. "
        "Return the JSON verdict."
    )
    raw = await chat_with_images(frames, caption, provider=VISION_PROVIDER)
    data = parse_llm_json(raw)
    if not data:
        return None, "unparseable/empty"
    try:
        score = float(data.get("score", 5))
    except (TypeError, ValueError):
        score = 5.0
    issues = [str(i) for i in (data.get("issues") or [])]
    passed = bool(data.get("pass", score >= 7 and not issues))
    return (not passed), f"score={score:.0f} issues={len(issues)}: {('; '.join(issues))[:50]}"


async def _panel_judge(frames: list[bytes], scene: str) -> tuple[bool | None, str]:
    from aesthetic_director import run_panel  # local import: panel built in Phase 2
    verdict = await run_panel(frames, scene_hint=scene)
    if verdict is None:
        return None, "panel returned None"
    flagged = verdict.has_high_severity()
    top = verdict.findings[0].issue if verdict.findings else "clean"
    return flagged, f"high={verdict.high_count()} top={top[:48]}"


JUDGES = {"baseline": _baseline_judge, "panel": _panel_judge}


async def run(judge_name: str) -> list[EvalRow]:
    judge = JUDGES[judge_name]
    rows: list[EvalRow] = []
    for entry in load_labels():
        scene = entry["scene"]
        frames = load_frames(scene)
        flagged: bool | None = None
        detail = ""
        for attempt in range(1, RETRIES + 1):
            try:
                # Hard cap per attempt so one flaky scene can't hang the whole run.
                flagged, detail = await asyncio.wait_for(judge(frames, scene), timeout=90)
                if flagged is not None:
                    break
            except (Exception, asyncio.TimeoutError) as e:  # noqa: BLE001
                detail = f"{type(e).__name__}: {e}"
            await asyncio.sleep(1.5 * attempt)
        rows.append(EvalRow(scene=scene, label=entry["label"], flagged=flagged, detail=detail))
        mark = "ERR " if flagged is None else ("FLAG" if flagged else "pass")
        print(f"  [{mark}] {scene} ({entry['label']}) — {detail[:70]}", flush=True)
    return rows


def _save_rows(which: str, rows: list[EvalRow]) -> Path:
    out = ROOT / "tests" / "gauntlet" / f"eval_{which}.json"
    out.write_text(json.dumps(
        [{"scene": r.scene, "label": r.label, "flagged": r.flagged, "detail": r.detail} for r in rows],
        indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    print(f"Vision provider: {VISION_PROVIDER} | judge: {which}\n")
    rows = asyncio.run(run(which))
    report = format_report(f"{which} critic vs labeled set", rows)
    print("\n" + report)
    out = _save_rows(which, rows)
    (ROOT / "tests" / "gauntlet" / f"report_{which}.txt").write_text(report, encoding="utf-8")
    print(f"\nSaved rows -> {out}")
