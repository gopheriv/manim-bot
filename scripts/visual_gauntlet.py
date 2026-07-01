"""Visual Gauntlet — render + extract keyframes + vision critic for all 10 scenes.

For each gauntlet scene:
  1. Render it to .mp4 via manim -ql
  2. Extract keyframes as PNGs under tests/gauntlet/frames/sceneNN/
  3. Run vision critic (if configured) or skip gracefully
  4. Print per-scene table: render OK?, #frames saved, critic verdict, issues

Usage:
  powershell -Command "$env:PYTHONIOENCODING='utf-8'; python scripts/visual_gauntlet.py"
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import subprocess
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from visual_critic import extract_keyframes, critique_render


GAUNTLET_DIR = ROOT / "tests" / "gauntlet"
FRAMES_DIR = ROOT / "tests" / "gauntlet" / "frames"
MEDIA_DIR = Path(tempfile.gettempdir()) / "visual_gauntlet_media"


def render_scene(filepath: Path) -> tuple[bool, Path | None, str]:
    """Render with manim -ql. Returns (success, mp4_path, error_msg)."""
    result = subprocess.run(
        ["manim", "-ql", str(filepath), "GenScene", "--media_dir", str(MEDIA_DIR)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300,
    )
    if result.returncode != 0:
        error = (result.stderr or result.stdout or "Unknown error")[-500:].strip()
        return False, None, f"manim exit {result.returncode}: {error[:150]}"

    # Find .mp4
    search = MEDIA_DIR / "videos" / filepath.stem
    mp4s = list(search.rglob("GenScene.mp4")) if search.exists() else []
    mp4s = [p for p in mp4s if p.stat().st_size > 1024]
    if not mp4s:
        return False, None, "No .mp4 produced"

    return True, mp4s[0], ""


def save_keyframes(frames: list[bytes], scene_dir: Path) -> list[Path]:
    """Save JPEG frames to PNG files and return paths."""
    scene_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, data in enumerate(frames):
        path = scene_dir / f"frame_{i+1:02d}.jpg"
        path.write_bytes(data)
        paths.append(path)
    return paths


def _check_vision_configured() -> bool:
    """Check if vision critic is configured (has an API endpoint)."""
    try:
        from config import VISION_PROVIDER
        # If there's a provider, it's configured
        return bool(VISION_PROVIDER)
    except Exception:
        return False


async def run_visual_gauntlet() -> list[dict]:
    """Run the full visual gauntlet."""
    results = []
    scene_files = sorted(GAUNTLET_DIR.glob("scene*.py"))

    vision_configured = _check_vision_configured()

    print(f"{'='*90}")
    print(f"VISUAL GAUNTLET — {len(scene_files)} scenes")
    print(f"Vision critic: {'configured' if vision_configured else 'NOT configured (skipping critic)'}")
    print(f"{'='*90}\n")

    for filepath in scene_files:
        name = filepath.stem
        print(f"\n{'─'*70}")
        print(f"SCENE: {name}")

        result = {"name": name, "render": "FAIL", "frames_saved": 0,
                  "critic": "SKIP", "score": "", "issues": []}

        # 1. Render
        ok, mp4, err = await asyncio.to_thread(render_scene, filepath)
        if not ok:
            result["render"] = f"FAIL: {err[:100]}"
            print(f"  ✗ Render: {err[:150]}")
            result["status"] = "FAIL"
            results.append(result)
            continue

        size_kb = mp4.stat().st_size / 1024
        print(f"  ✓ Render: OK ({size_kb:.0f} KB)")
        result["render"] = f"OK ({size_kb:.0f} KB)"

        # 2. Extract keyframes
        scene_dir = FRAMES_DIR / name
        try:
            frames = await extract_keyframes(mp4, n=5)
        except Exception as e:
            print(f"  ✗ Keyframe extraction failed: {e}")
            frames = []

        if frames:
            paths = save_keyframes(frames, scene_dir)
            result["frames_saved"] = len(paths)
            print(f"  ✓ Frames: {len(paths)} saved to {scene_dir.name}/")
        else:
            print(f"  ✗ No frames extracted")

        # 3. Vision critic (if configured)
        if vision_configured and frames:
            code = filepath.read_text(encoding="utf-8")
            try:
                verdict = await critique_render(mp4, prompt=name, code=code)
                if verdict:
                    result["critic"] = "PASS" if verdict.passed else "FAIL"
                    result["score"] = f"{verdict.score:.1f}"
                    result["issues"] = verdict.issues
                    if verdict.passed:
                        print(f"  ✓ Critic: PASS (score {verdict.score:.1f})")
                    else:
                        print(f"  ✗ Critic: FAIL (score {verdict.score:.1f})")
                        for issue in verdict.issues[:3]:
                            print(f"    - {issue[:120]}")
                else:
                    result["critic"] = "SKIP (no verdict)"
                    print(f"  - Critic: returned no verdict (skipped)")
            except Exception as e:
                result["critic"] = f"SKIP (error: {type(e).__name__})"
                print(f"  - Critic: error — {type(e).__name__}: {e}")
        elif not vision_configured:
            result["critic"] = "SKIP (no API configured)"
            print(f"  - Critic: SKIPPED (no vision API configured)")

        result["status"] = "PASS" if ok else "FAIL"
        results.append(result)

    return results


def print_summary(results: list[dict]) -> None:
    """Print the visual gauntlet summary table."""
    print(f"\n{'='*90}")
    print(f"VISUAL GAUNTLET SUMMARY")
    print(f"{'='*90}\n")

    header = f"{'Scene':<30} {'Render':<14} {'Frames':<8} {'Critic':<12} {'Score':<7}"
    print(header)
    print(f"{'─'*90}")

    for r in results:
        critic = r["critic"]
        if r["issues"]:
            critic += f" ({len(r['issues'])} issues)"
        print(
            f"{r['name']:<30} {r['render']:<14} {r['frames_saved']:<8} "
            f"{critic:<22} {r['score']:<7}"
        )

    passed = sum(1 for r in results if r.get("status") == "PASS")
    print(f"{'─'*90}")
    print(f"TOTAL: {passed} PASS / {len(results) - passed} FAIL / {len(results)} scenes")


if __name__ == "__main__":
    results = asyncio.run(run_visual_gauntlet())
    print_summary(results)
