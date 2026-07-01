# The Aesthetic Director — a calibrated, spatially-grounded visual-quality panel

## Why this exists

The bot can render hard topics without crashing, but the single legacy `visual_critic`
had **no trustworthy sense of whether a render looks good**. On the 10-scene visual
gauntlet it flagged 8 scenes and **7 were false alarms (~12% precision)**: it confuses
*normal animation* — a curve being drawn (mid-`Write`), an equation morphing through
faint intermediates, a growing arrow, a dot tracing a path, a translucent integral fill,
axis arrowheads — with real defects. Worse, it **missed the one genuine defect**
(`scene08`: a parabola whose arm exits the top frame edge), scoring it 10/10. A judge
that wrong is worse than none.

The Aesthetic Director replaces it with a **panel of specialized, spatially-grounded
sub-critics** plus a **fusing director**, calibrated against a labeled ground-truth set so
its precision is *measured*, not asserted.

## The calibration insight (the hard requirement)

Every sub-critic is instructed with the lesson learned from the labeled data:

> The frames are in time order. The **last frame is the SETTLED final state**; earlier
> frames are mid-animation and are *supposed* to look partial. Treat partial/in-progress
> states (mid-`Write`, morph intermediates, growing arrows, traced paths, translucent
> fills, a camera mid-move, a curve whose end naturally reaches a frame corner) as
> **NORMAL**. Flag **only** a defect that still persists in the settled frame and that a
> careful human would unambiguously call broken. When unsure, do not flag.

This single rule is what turns a false-alarm machine into a usable gate.

## Architecture

```
frames ──► [ Framing critic ]      ┐
       ──► [ Readability critic ]   ├─► findings ──► Director.fuse() ──► AestheticVerdict
       ──► [ Contrast critic ]      ┘   (dedup, rank, conflict-resolve)        │
                                                                                ▼
                                            passed?  (no HIGH-severity defect)  +  ranked fix plan
```

- **Sub-critics** (`aesthetic_director._SUB_CRITICS`) each make one vision call with a
  tight, frame-geometry rubric and the shared calibration block, and return strict-JSON
  `findings: [{severity, location, issue, remedy}]`. They run **in parallel** per scene.
  - *Framing* — off-frame crop (an object's stroke runs past an image edge with content
    lost), ORIGIN pile-ups, severe imbalance.
  - *Readability* — unreadably tiny text, overlapping/illegible text, crowding.
  - *Contrast* — text at near-background contrast (a translucent area fill is *not* a
    defect unless it makes content unreadable).
- **The Director** (`fuse`, pure/deterministic): collapses findings about the same
  `(category, location)` to the highest severity (a specific defect is never cancelled by a
  vaguer/"looks fine" one — we **union**, not intersect), ranks by severity then category
  priority (framing first), and caps to a focused, non-contradictory plan.
- **The gate**: a scene **passes** iff there is **no HIGH-severity** settled-frame defect.
  Medium/low findings are reported as polish, never trip the gate — this is the precision
  lever that keeps normal animation from flagging.

## The converging refinement loop

`refine_visual(code, render_fn, panel_fn, repair_fn, max_passes=3)`:

```
render → panel → if a HIGH-severity defect remains:
    repair the director's ranked fix plan (targeted LLM repair) → re-render → re-judge
repeat until no HIGH-severity defect (converged) or max_passes; always keep the BEST
(fewest high-severity) render. Bounded, never infinite, graceful on any failure.
```

All I/O is injected, so convergence/termination/best-keeping are unit-tested deterministically.

## Integration (opt-in, default OFF)

`AESTHETIC_DIRECTOR_ENABLED` (default `false`). When on, the panel judges the frames inside
the bot's **existing** visual-feedback loop (`critique_render_panel` returns the same
`VisualVerdict` shape the loop already consumes). Default off → the legacy critic runs
unchanged → the whole test suite is unaffected.

## How the claims were proven

- **Ground truth** (`tests/gauntlet/labels.json`): 15 scenes, every settled frame OPENED
  and labeled by a human-equivalent reviewer — never a model score. 6 defects (the real
  `scene08` off-frame + 5 authored true positives: off-frame, text overlap, sub-10pt text,
  near-background contrast, three objects stacked at ORIGIN) and 9 clean scenes (where the
  legacy critic produced its false alarms).
- **Measurement** (`scripts/eval_critic.py {baseline|panel}` → `scripts/compare_evals.py`):
  runs each judge over the labeled set with the real (flaky) qwen vision endpoint, with
  retries. A scene that never returns a parseable verdict is recorded as an ERROR and
  EXCLUDED from precision/recall — never guessed.
- **Determinism**: the dataset accounting (`aesthetic_metrics`), fusion, gate and loop are
  unit-tested with mocked verdicts (`tests/test_aesthetic_director.py`) — they run in CI
  with no vision API.

## Calibration result

<!-- METRICS_TABLE -->
_(precision/recall table filled in from the live runs — see "Results" below.)_

## How to run it

```bash
# 1. (re)render the authored defect scenes + extract frames    (deterministic)
PYTHONIOENCODING=utf-8 python scripts/visual_gauntlet.py        # the 10 gauntlet scenes
# broken scenes are under tests/gauntlet/broken*.py (frames already extracted)

# 2. measure each judge against the labeled set                 (needs vision)
PYTHONIOENCODING=utf-8 python scripts/eval_critic.py baseline
PYTHONIOENCODING=utf-8 python scripts/eval_critic.py panel
PYTHONIOENCODING=utf-8 python scripts/compare_evals.py

# 3. demonstrate the converging loop on a flawed scene          (needs vision + render)
PYTHONIOENCODING=utf-8 python scripts/refine_demo.py tests/gauntlet/broken01_offframe.py

# 4. deterministic logic tests (no vision)
PYTHONIOENCODING=utf-8 python -m pytest tests/test_aesthetic_director.py -q
```

## Results

<!-- RESULTS -->
_(filled in from the live runs.)_
