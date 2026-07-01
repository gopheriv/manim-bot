# Render Gauntlet — 10 Hard-Topic ManimCE Scenes

A battery of curated, known-good ManimCE scenes that exercise the full static+render pipeline.
These are the **source of truth** for "good" — if the validator flags any of these, the validator is wrong.

## How to Run

### Fast Guard (pytest, no rendering)
```powershell
$env:PYTHONIOENCODING='utf-8'
python -m pytest tests/test_gauntlet.py -v
```
30 tests: safety + validate_layout + py_compile for all 10 scenes.

### Full Render Gauntlet
```powershell
$env:PYTHONIOENCODING='utf-8'
python scripts/render_gauntlet.py
```
Runs each scene through all 4 checks (safety, layout, compile, render) and prints a PASS/FAIL table.

## Scenes

| # | File | Scene Class | Device Type | What It Exercises |
|---|------|-------------|-------------|-------------------|
| 1 | `scene01_function_plot.py` | `GenScene(Scene)` | Axes.plot + get_axis_labels | Function plotting with labeled axes |
| 2 | `scene02_equation_morph.py` | `GenScene(Scene)` | TransformMatchingTex | Equation morph between `(a+b)²` and expanded form |
| 3 | `scene03_valuetracker_dot.py` | `GenScene(Scene)` | ValueTracker + always_redraw | Dot on curve with TracedPath, clear_updaters at end |
| 4 | `scene04_camera_pushin.py` | `GenScene(MovingCameraScene)` | self.camera.frame.save_state / animate / Restore | Camera push-in and release (2D camera) |
| 5 | `scene05_true_3d.py` | `GenScene(ThreeDScene)` | set_camera_orientation + Surface + ambient rotation | True 3D scene with paraboloid surface |
| 6 | `scene06_riemann_area.py` | `GenScene(Scene)` | get_riemann_rectangles + get_area | Riemann rectangles refining to smooth area |
| 7 | `scene07_grid_transform.py` | `GenScene(Scene)` | NumberPlane + ApplyMatrix + ghost copy | Grid shear transformation with ghost copy |
| 8 | `scene08_latex_heavy.py` | `GenScene(Scene)` | substrings_to_isolate + set_color_by_tex | Multi-color LaTeX derivation |
| 9 | `scene09_staggered_reveal.py` | `GenScene(Scene)` | LaggedStart over VGroup | Staggered dot + label reveal |
| 10 | `scene10_vectors.py` | `GenScene(Scene)` | Arrow(buff=0) + GrowArrow | Vectors on a number plane with labels |

## Results (2026-06-30)

| Scene | Safety | Layout | Compile | Render |
|-------|--------|--------|---------|--------|
| scene01_function_plot | PASS | PASS (0 issues) | PASS | 34 KB |
| scene02_equation_morph | PASS | PASS (0 issues) | PASS | 22 KB |
| scene03_valuetracker_dot | PASS | PASS (0 issues) | PASS | 43 KB |
| scene04_camera_pushin | PASS | PASS (0 issues) | PASS | 142 KB |
| scene05_true_3d | PASS | PASS (0 issues) | PASS | 104 KB |
| scene06_riemann_area | PASS | PASS (0 issues) | PASS | 86 KB |
| scene07_grid_transform | PASS | PASS (0 issues) | PASS | 128 KB |
| scene08_latex_heavy | PASS | PASS (0 issues) | PASS | 27 KB |
| scene09_staggered_reveal | PASS | PASS (0 issues) | PASS | 18 KB |
| scene10_vectors | PASS | PASS (0 issues) | PASS | 32 KB |

**10/10 PASS. 0 validator false positives. No changes needed.**

## Notes

- **Visual correctness**: "Rendered" means `.mp4` produced with no error. Visual correctness was not formally evaluated beyond "no crash".
- **Scene #4** exercises the camera-mismatch validator — it correctly uses `self.camera.frame` with `MovingCameraScene` and is NOT flagged.
- **Scene #5** exercises the 3D camera API — it correctly uses `self.set_camera_orientation()` with `ThreeDScene` and is NOT flagged.
- All scenes are based on patterns verified in `docs/MANIMCE_CHEATSHEET.md`.
