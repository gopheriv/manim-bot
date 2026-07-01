"""Visual regression baseline — perceptual hashing for every template.

Proves templates still LOOK right (not just "no crash"). Uses a deterministic
average-hash (ahash) on the settled frame of each template's render.

Two modes:
  "record" → render all templates, extract the settled frame, write hashes to
             tests/gallery/baseline_hashes.json
  "check"  → recompute hashes and compare to the baseline; print templates whose
             hamming distance exceeds TOLERANCE (8 bits). Exit 1 if any changed.

Usage:
  python scripts/visual_baseline.py record
  python scripts/visual_baseline.py check
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image

# ── Setup ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from templates.registry import get_registry  # noqa: E402

TIMEOUT = 120  # seconds per render
TOLERANCE = 8  # bits of hamming distance before flagging
BASELINE_PATH = PROJECT_ROOT / "tests" / "gallery" / "baseline_hashes.json"

WRAPPER_TEMPLATE = """\
from manim import *
import numpy as np

class GenScene(Scene):
    def construct(self):
{body}
        self.wait(0.5)
"""


# ── Pure perceptual-hash functions (exact algorithm as specified) ─────────────

def ahash(image_path: str) -> str:
    """Average-hash of an image → 16 hex chars (64 bits).

    Algorithm (exact):
      1. Convert to grayscale, resize to 8×8
      2. Compute mean of all 64 pixel values
      3. Bit = 1 if pixel >= mean, else 0
      4. Return as 16-char hex string
    """
    img = Image.open(image_path).convert("L").resize((8, 8))
    px = list(img.getdata())  # 64 grayscale values
    avg = sum(px) / 64
    bits = "".join("1" if p >= avg else "0" for p in px)
    return f"{int(bits, 2):016x}"


def hamming(h1: str, h2: str) -> int:
    """Hamming distance between two 16-char hex hashes (number of differing bits)."""
    return bin(int(h1, 16) ^ int(h2, 16)).count("1")


def is_degenerate(h: str) -> bool:
    """True if the hash is all-0 or all-1 (essentially uniform / blank frame)."""
    return h == "0" * 16 or h == "f" * 16


# ── Render + frame extraction ────────────────────────────────────────────────

def _build_scene(code: str) -> str:
    """Wrap scene code into a complete standalone scene.

    If the code already contains 'class GenScene', use it as-is (for class-based
    templates that return complete code). Otherwise wrap it in the standard
    MovingCameraScene wrapper (for JSON templates that are just construct bodies).
    """
    if "class GenScene" in code:
        return code
    body = "\n".join("        " + line for line in code.split("\n"))
    return WRAPPER_TEMPLATE.format(body=body)


def _render_and_grab_frame(scene_code: str, scene_name: str) -> Optional[str]:
    """Render the scene and extract the last frame as a JPEG path.

    Returns the path to the extracted JPEG, or None on failure.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        py_path = Path(tmpdir) / f"{scene_name}.py"
        py_path.write_text(scene_code, encoding="utf-8")
        media_dir = Path(tmpdir) / "media"

        result = subprocess.run(
            ["manim", "-ql", str(py_path), "GenScene", "--media_dir", str(media_dir)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=TIMEOUT,
        )
        if result.returncode != 0:
            return None

        # Find the .mp4
        video_dir = media_dir / "videos" / scene_name
        if not video_dir.exists():
            return None
        mp4s = list(video_dir.rglob("GenScene.mp4"))
        mp4s = [p for p in mp4s if p.stat().st_size > 1024]
        if not mp4s:
            return None

        mp4_path = mp4s[0]

        # Extract the last frame (settled frame) using ffmpeg
        frame_path = Path(tmpdir) / "settled.jpg"
        try:
            proc = subprocess.run(
                [
                    "ffmpeg", "-nostdin", "-sseof", "-0.5", "-i", str(mp4_path),
                    "-frames:v", "1", "-f", "image2", "-vcodec", "mjpeg",
                    str(frame_path),
                ],
                capture_output=True, timeout=30,
            )
        except FileNotFoundError:
            # ffmpeg not on PATH; try imageio-ffmpeg
            try:
                import imageio_ffmpeg
                ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                proc = subprocess.run(
                    [
                        ffmpeg_exe, "-nostdin", "-sseof", "-0.5", "-i", str(mp4_path),
                        "-frames:v", "1", "-f", "image2", "-vcodec", "mjpeg",
                        str(frame_path),
                    ],
                    capture_output=True, timeout=30,
                )
            except Exception:
                return None

        if proc.returncode != 0 or not frame_path.exists():
            # Fallback: grab frame at 90% of duration
            import imageio_ffmpeg
            try:
                ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                proc = subprocess.run(
                    [
                        ffmpeg_exe, "-nostdin", "-ss", "5", "-i", str(mp4_path),
                        "-frames:v", "1", "-f", "image2", "-vcodec", "mjpeg",
                        str(frame_path),
                    ],
                    capture_output=True, timeout=30,
                )
            except Exception:
                return None
            if proc.returncode != 0 or not frame_path.exists():
                return None

        # Copy to a permanent location for inspection
        save_dir = PROJECT_ROOT / "tests" / "gallery" / "frames"
        save_dir.mkdir(parents=True, exist_ok=True)
        permanent_path = save_dir / f"{scene_name}_settled.jpg"
        import shutil
        shutil.copy2(frame_path, permanent_path)

        return str(permanent_path)


# ── Main modes ───────────────────────────────────────────────────────────────

def record() -> dict[str, str]:
    """Render all templates, extract settled frames, record hashes."""
    reg = get_registry()
    hashes: dict[str, str] = {}
    degenerate: list[str] = []
    failed: list[str] = []

    print(f"Recording baseline for {len(reg._templates)} templates...")
    for i, tmpl in enumerate(reg._templates, 1):
        name = tmpl.name
        cfg = tmpl.default_config()
        if not cfg.title:
            cfg.title = name
        code = tmpl.generate_code(cfg)
        wrapped = _build_scene(code)

        frame_path = _render_and_grab_frame(wrapped, f"baseline_{name.replace(' ', '_')}")
        if frame_path is None:
            print(f"  [{i}/{len(reg._templates)}] {name}: FAILED (render or frame extraction)")
            failed.append(name)
            continue

        h = ahash(frame_path)
        hashes[name] = h
        status = "DEGENERATE (likely blank)" if is_degenerate(h) else "OK"
        if is_degenerate(h):
            degenerate.append(name)
        print(f"  [{i}/{len(reg._templates)}] {name}: {h} [{status}]")

    # Write baseline
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(
        json.dumps(hashes, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"\nBaseline written to {BASELINE_PATH}")
    print(f"  {len(hashes)} templates recorded")
    if degenerate:
        print(f"  ! {len(degenerate)} degenerate/blank: {', '.join(degenerate)}")
    if failed:
        print(f"  X {len(failed)} failed to render: {', '.join(failed)}")
    return hashes


def check() -> int:
    """Compare current hashes to the baseline. Return number of changes."""
    if not BASELINE_PATH.exists():
        print(f"No baseline found at {BASELINE_PATH}. Run 'record' first.")
        return -1

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    reg = get_registry()

    changed = []
    missing = []
    unchanged = 0

    print(f"Checking {len(reg._templates)} templates against baseline...")
    for i, tmpl in enumerate(reg._templates, 1):
        name = tmpl.name
        if name not in baseline:
            missing.append(name)
            print(f"  [{i}/{len(reg._templates)}] {name}: MISSING from baseline")
            continue

        cfg = tmpl.default_config()
        if not cfg.title:
            cfg.title = name
        code = tmpl.generate_code(cfg)
        wrapped = _build_scene(code)

        frame_path = _render_and_grab_frame(wrapped, f"check_{name.replace(' ', '_')}")
        if frame_path is None:
            print(f"  [{i}/{len(reg._templates)}] {name}: FAILED (render or frame extraction)")
            changed.append((name, "FAILED", -1))
            continue

        h = ahash(frame_path)
        h_baseline = baseline[name]
        d = hamming(h, h_baseline)

        if d > TOLERANCE:
            changed.append((name, h, d))
            print(f"  [{i}/{len(reg._templates)}] {name}: CHANGED (d={d})")
        else:
            unchanged += 1
            print(f"  [{i}/{len(reg._templates)}] {name}: unchanged (d={d})")

    total = len(reg._templates)
    print(f"\nResult: {unchanged}/{total} unchanged, {len(changed)} changed, {len(missing)} missing")
    return len(changed) + len(missing)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "record"
    if mode == "record":
        record()
    elif mode == "check":
        n_changes = check()
        sys.exit(1 if n_changes > 0 else 0)
    else:
        print(f"Unknown mode: {mode}. Use 'record' or 'check'.")
        sys.exit(1)
