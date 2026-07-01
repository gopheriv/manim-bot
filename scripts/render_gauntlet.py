"""Render Gauntlet Runner — runs 10 curated scenes through the full pipeline.

For each scene in tests/gauntlet/:
  a) code_safety.validate_code_safety → must be safe
  b) scene_validator.validate_layout → must return [] (zero issues)
  c) py_compile → must pass
  d) manim -ql <file> GenScene → must produce .mp4 with no error

Usage:
  powershell -Command "$env:PYTHONIOENCODING='utf-8'; python scripts/render_gauntlet.py"
"""
from __future__ import annotations

import sys
import tempfile
import subprocess
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from code_safety import validate_code_safety
from scene_validator import validate_layout


GAUNTLET_DIR = ROOT / "tests" / "gauntlet"
MEDIA_DIR = Path(tempfile.gettempdir()) / "gauntlet_media"


def check_safety(code: str) -> tuple[bool, list[str]]:
    """Run code_safety check."""
    return validate_code_safety(code)


def check_layout(code: str) -> list[str]:
    """Run scene_validator check."""
    return validate_layout(code)


def check_py_compile(filepath: Path) -> tuple[bool, str]:
    """Run py_compile check."""
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(filepath)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode == 0:
        return True, ""
    return False, result.stderr


def render_scene(filepath: Path, scene_name: str = "GenScene") -> tuple[bool, str]:
    """Render with manim -ql and check for .mp4 output."""
    scene_dir = filepath.parent
    result = subprocess.run(
        ["manim", "-ql", str(filepath), scene_name, "--media_dir", str(MEDIA_DIR)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300,  # 5 min timeout per scene
    )
    if result.returncode != 0:
        # Extract the error from stderr
        error_lines = (result.stderr or "")[-800:].strip()
        return False, f"manim exited {result.returncode}:\n{error_lines}"

    # Check for .mp4 output
    search_dir = MEDIA_DIR / "videos" / filepath.stem
    mp4s = list(search_dir.rglob(f"{scene_name}.mp4")) if search_dir.exists() else []
    if not mp4s:
        return False, "No .mp4 produced (manim exit 0 but no video)"

    size_kb = mp4s[0].stat().st_size / 1024
    return True, f"OK ({size_kb:.0f} KB)"


def run_gauntlet() -> list[dict]:
    """Run the full gauntlet and return results."""
    results = []

    # Find all scene files
    scene_files = sorted(GAUNTLET_DIR.glob("scene*.py"))
    if not scene_files:
        print(f"No scene files found in {GAUNTLET_DIR}")
        return results

    print(f"{'='*80}")
    print(f"RENDER GAUNTLET — {len(scene_files)} scenes")
    print(f"{'='*80}\n")

    for filepath in scene_files:
        name = filepath.stem
        code = filepath.read_text(encoding="utf-8")

        print(f"\n{'─'*60}")
        print(f"SCENE: {name}")

        result = {"name": name, "safety": "FAIL", "layout": "FAIL", "compile": "FAIL", "render": "FAIL"}

        # a) Safety check
        safe, safety_issues = check_safety(code)
        result["safety"] = "PASS" if safe else f"FAIL: {safety_issues[:100]}"
        if not safe:
            print(f"  ✗ Safety: {result['safety']}")
            result["status"] = "FAIL"
            results.append(result)
            continue

        print(f"  ✓ Safety: PASS")

        # b) Layout check
        layout_issues = check_layout(code)
        if layout_issues:
            result["layout"] = f"FAIL: {layout_issues[0][:100]}"
            print(f"  ✗ Layout: {result['layout']}")
            result["status"] = "FAIL"
            results.append(result)
            continue

        print(f"  ✓ Layout: PASS (0 issues)")
        result["layout"] = "PASS"

        # c) Py-compile check
        ok, err = check_py_compile(filepath)
        if not ok:
            result["compile"] = f"FAIL: {err[:100]}"
            print(f"  ✗ Compile: {result['compile']}")
            result["status"] = "FAIL"
            results.append(result)
            continue

        print(f"  ✓ Compile: PASS")
        result["compile"] = "PASS"

        # d) Render check
        try:
            ok, msg = render_scene(filepath)
        except subprocess.TimeoutExpired:
            ok, msg = False, "Render timed out (5 min)"

        if not ok:
            result["render"] = f"FAIL: {msg[:120]}"
            print(f"  ✗ Render: {result['render']}")
            result["status"] = "FAIL"
            results.append(result)
            continue

        print(f"  ✓ Render: {msg}")
        result["render"] = "PASS"
        result["status"] = "PASS"

        results.append(result)

    return results


def print_summary(results: list[dict]) -> None:
    """Print a summary table of all results."""
    print(f"\n{'='*80}")
    print(f"GAUNTLET SUMMARY")
    print(f"{'='*80}\n")

    # Table header
    print(f"{'Scene':<30} {'Safety':<8} {'Layout':<8} {'Compile':<10} {'Render':<10}")
    print(f"{'─'*80}")

    for r in results:
        print(
            f"{r['name']:<30} {r['safety']:<8} {r['layout']:<8} "
            f"{r['compile']:<10} {r['render']:<10}"
        )

    # Summary counts
    passed = sum(1 for r in results if r.get("status") == "PASS")
    failed = len(results) - passed
    print(f"{'─'*80}")
    print(f"TOTAL: {passed} PASS / {failed} FAIL / {len(results)} scenes")

    if failed > 0:
        print(f"\nFailures:")
        for r in results:
            if r.get("status") != "PASS":
                print(f"  - {r['name']}: ", end="")
                failures = []
                if r["safety"] != "PASS":
                    failures.append(f"safety={r['safety'][:60]}")
                if r["layout"] != "PASS":
                    failures.append(f"layout={r['layout'][:60]}")
                if r["compile"] != "PASS":
                    failures.append(f"compile={r['compile'][:60]}")
                if r["render"] != "PASS":
                    failures.append(f"render={r['render'][:60]}")
                print(" | ".join(failures))


if __name__ == "__main__":
    results = run_gauntlet()
    print_summary(results)

    # Exit with non-zero if any failures
    failed = sum(1 for r in results if r.get("status") != "PASS")
    sys.exit(1 if failed else 0)
