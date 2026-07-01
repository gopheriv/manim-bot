"""Render smoke test — proves EVERY template actually renders to an .mp4.

Usage:
  powershell -Command "$env:PYTHONIOENCODING='utf-8'; python scripts/render_smoke.py"

For every registered template:
  1. Build its default config (fill title if empty)
  2. Generate final scene code, assert no leftover {placeholders}
  3. Write to temp .py, run manim -ql with 120s timeout
  4. Record PASS (exit 0 + GenScene.mp4 > 1KB) or FAIL (last 15 lines stderr)

Print a per-template table and a final summary line.
"""
from __future__ import annotations

import logging
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# ── SKIP list (rare — only for genuinely-too-heavy templates)
# Add names here with a one-line comment saying why. Empty by default.
# NOTE: driven_oscillator / riemann_sum / eigenvalues were previously skipped with a
# bogus "Manim type-hint / Python 3.13+" reason — they were actually real template
# bugs (dropped \\frac backslash, opacity= on axes.plot, a 2D slice of a 3D vector)
# and are now FIXED and render. Keep this list empty unless a template is truly heavy.
SKIP_NAMES: set[str] = set()

# ── Setup ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from templates.registry import get_registry  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("render_smoke")

TIMEOUT = 120  # seconds per render


@dataclass
class Result:
    name: str
    status: str  # "PASS" | "FAIL" | "SKIP"
    detail: str = ""


def _build_code(template) -> str:
    """Generate final scene code for a template, fully substituted."""
    cfg = template.default_config()
    # Fill title if empty so {title} placeholders don't stay bare
    if not cfg.title:
        cfg.title = template.name
    code = template.generate_code(cfg)
    # Check for REAL unsubstituted template placeholders, NOT LaTeX braces.
    # Template placeholders are: {title}, {equation}, {description}, {duration},
    # {color1}/{color2}/{color3}, and {extra_param_name}. They appear in Python
    # code context (not inside \frac{}, \begin{}, etc.). A real leftover will
    # be a standalone {word} that is NOT preceded by a backslash or inside a
    # known LaTeX command.
    known_template_placeholders = {
        "title", "equation", "description", "duration",
        "color1", "color2", "color3",
    }
    # Find all {word} patterns that are NOT LaTeX (not preceded by \)
    candidates = re.findall(r"(?<!\\)\{([a-zA-Z_]\w*)\}", code)
    leftovers = [c for c in candidates if c in known_template_placeholders or
                 # extra_params placeholders like {key_name} — check if they look like
                 # extra_params (lowercase, underscore-separated, not LaTeX keywords)
                 (c.islower() and "_" not in c[:2] and c not in {
                     # Common LaTeX keywords that are NOT template placeholders
                     # Single letters (very common in math):
                     "h", "d", "dx", "dt", "n", "k", "a", "b", "c", "f", "x", "y",
                     "z", "r", "s", "t", "u", "v", "w", "m", "g", "i", "j", "l",
                     "e", "o", "p", "q", "E", "B", "F", "L", "P", "Q", "R", "S",
                     "T", "X", "Y", "Z", "W", "M", "G", "I", "J", "H", "K", "N",
                     # LaTeX commands:
                     "pmatrix", "array", "vec", "hat", "tilde", "bar", "dot", "ddot",
                     "left", "right", "frac", "sqrt", "sum", "prod", "int", "oint",
                     "iint", "iiint", "lim", "log", "ln", "sin", "cos", "tan",
                     "partial", "nabla", "infty", "forall", "exists", "subset",
                     "subseteq", "in", "notin", "cap", "cup", "oplus", "otimes",
                     "mathbb", "mathcal", "mathbf", "mathrm", "text", "ldots",
                     "cdots", "vdots", "ddots", "quad", "qquad", "approx", "equiv",
                     "leq", "geq", "neq", "ll", "gg", "pm", "mp", "times", "div",
                     "cdot", "circ", "bullet", "star", "dagger", "ddagger",
                     "langle", "rangle", "lvert", "rvert", "Vert", "vert",
                     "norm", "angle", "phi", "theta", "alpha", "beta", "gamma",
                     "delta", "epsilon", "omega", "sigma", "tau", "rho", "mu",
                     "pi", "lambda", "kappa", "xi", "psi", "zeta", "eta", "nu",
                     "chi", "upsilon", "Gamma", "Delta", "Theta", "Lambda", "Xi",
                     "Pi", "Sigma", "Upsilon", "Phi", "Psi", "Omega",
                     "Var", "Cov", "Res", "F_n", "d_o", "d_i", "GMm", "constant",
                     # Multi-char math:
                     "dt", "dx", "dy", "dz", "ds", "Res", "Var", "Cov",
                     # Math in \text{} commands (LaTeX text mode):
                     "proj", "operatorname", "limits", "nolimits", "limits",
                 })]
    if leftovers:
        raise ValueError(f"Unsubstituted placeholders in {template.name}: {leftovers[:5]}")
    return code


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
            stderr_tail = "\n".join((result.stderr or result.stdout or "").splitlines()[-15:])
            return False, stderr_tail

        # Check for .mp4 output
        video_dir = media_dir / "videos" / scene_name
        if video_dir.exists():
            mp4s = list(video_dir.rglob("GenScene.mp4"))
            mp4s = [p for p in mp4s if p.stat().st_size > 1024]
            if mp4s:
                return True, f"{mp4s[0].stat().st_size / 1024:.0f} KB"

        return False, "No .mp4 > 1KB produced"


def run_smoke() -> list[Result]:
    """Run render smoke on all templates."""
    reg = get_registry()
    templates = reg._templates
    logger.info(f"Render smoke test: {len(templates)} templates")
    logger.info(f"Timeout per render: {TIMEOUT}s")
    logger.info(f"Skip list: {SKIP_NAMES if SKIP_NAMES else '(empty)'}")
    logger.info("=" * 70)

    results: list[Result] = []
    passed = failed = skipped = 0

    for tmpl in templates:
        name = tmpl.name

        if name in SKIP_NAMES:
            results.append(Result(name, "SKIP", "skipped by config"))
            skipped += 1
            logger.info(f"[{skipped:>3}] {name}: SKIP")
            continue

        try:
            code = _build_code(tmpl)
        except Exception as e:
            results.append(Result(name, "FAIL", f"code generation error: {e}"))
            failed += 1
            logger.info(f"[{passed + failed + skipped:>3}] {name}: FAIL (code gen)")
            continue

        try:
            ok, detail = _render(code, f"smoke_{name.replace(' ', '_')}")
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
            logger.info(f"[{passed + failed + skipped:>3}] {name}: FAIL — {detail[:120]}")

    total = len(templates)
    logger.info("=" * 70)
    renderable = total - skipped
    logger.info(f"{passed}/{renderable} templates rendered OK"
                f" ({skipped} skipped, {failed} failed, {total} total)")
    return results


def _print_table(results: list[Result]) -> None:
    """Print a summary table of all results."""
    sep = "-" * 70
    print(f"\n{sep}")
    print("RENDER SMOKE SUMMARY")
    print(f"{sep}\n")
    print(f"{'Template':<35} {'Status':<8} {'Detail'}")
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
        print(f"{r.name:<35} {r.status:<8} {detail}")

    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    skipped = sum(1 for r in results if r.status == "SKIP")
    total = len(results)
    renderable = total - skipped
    print(sep)
    print(f"TOTAL: {passed}/{renderable} rendered OK"
          f" ({skipped} skipped, {failed} failed, {total} total)")

    if failed > 0:
        print("\nFailures:")
        for r in results:
            if r.status == "FAIL":
                print(f"  - {r.name}: {r.detail[:100]}")


if __name__ == "__main__":
    results = run_smoke()
    _print_table(results)

    failed = sum(1 for r in results if r.status == "FAIL")
    sys.exit(1 if failed else 0)
