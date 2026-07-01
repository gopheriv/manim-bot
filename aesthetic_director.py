"""The Aesthetic Director — a calibrated, spatially-grounded visual-quality panel.

The single legacy ``visual_critic`` flags normal animation (mid-Write, morph
intermediates, growing arrows, traced paths, translucent fills) as defects — on the
gauntlet it flagged 8 scenes and 7 were false alarms (~12% precision). A judge that
wrong is worse than none.

This replaces it with a PANEL of specialised sub-critics, each reasoning explicitly
about the IMAGE FRAME (objects exiting the edges, quadrant balance, glyph size,
contrast) and each calibrated with the hard lesson from our labeled data: treat
partial/in-progress animation as NORMAL and flag ONLY a defect that PERSISTS in the
SETTLED (final) frame. A DIRECTOR then fuses the critiques into one ranked,
deduplicated, conflict-resolved fix plan.

Two layers, separated for testability:
  * the sub-critics make vision calls (impure, flaky) — each returns Findings;
  * ``fuse()`` and ``_parse_findings()`` are PURE and deterministic — unit-tested
    with mocked critic output, no vision API.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from common import parse_llm_json

logger = logging.getLogger("aesthetic_director")

_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}

# Lower number = surfaced first when severities tie (framing defects dominate).
_CATEGORY_PRIORITY = {"framing": 0, "readability": 1, "contrast": 2, "motion": 3}


# ── The calibration backbone (shared by every sub-critic) ─────────────────────
# This is the hard requirement learned from the labeled set: do NOT flag animation
# in progress; judge the settled frame.
_CALIBRATION = """You are reviewing FRAMES from a Manim math animation, given in time order.
The LAST frame is the SETTLED final state; earlier frames are MID-ANIMATION and are
SUPPOSED to look partial. Use the earlier frames only to tell "still transitioning"
from "actually broken".

NEVER flag these — they are NORMAL animation, not defects:
- a line/curve being drawn (mid-Write), an equation morphing (faint ghosted
  intermediates), an arrow growing, a dot tracing along a path, objects fading
  in/out, a translucent area fill (e.g. integral/Riemann shading), a camera mid-move;
- a curve, axis or arrow whose end naturally REACHES a frame corner or edge while
  staying fully visible (a full-frame parabola is GOOD composition, not "cut off");
- a lone dot or marker sitting at the end of a traced path;
- empty/background space around a small amount of content (that is not a defect).

Flag ONLY a defect that is STILL PRESENT in the SETTLED (final) frame and that a
careful human reviewer would unambiguously call broken. When unsure, do NOT flag —
a false alarm on normal animation is a serious error.

Return ONLY valid JSON, no markdown fences:
{"findings": [{"severity": "high|medium|low", "location": "top|bottom|left|right|top_right|top_left|bottom_right|bottom_left|center", "issue": "the settled-frame defect, concretely", "remedy": "a concrete code-level fix (positions, font_size, spacing, colours, fade-outs)"}]}
If the settled frame is clean in your specialty, return {"findings": []}.
"""

_FRAMING_RUBRIC = _CALIBRATION + """
YOUR SPECIALTY: FRAMING & COMPOSITION. In the SETTLED frame only, look for:
- OFF-FRAME CROP (high): a meaningful object (curve, equation, label, shape, axis
  arrow) is visibly CUT OFF by an image border — its stroke runs into the top/bottom/
  left/right edge and part of it is missing beyond the edge. (A shape that ends BEFORE
  the edge, fully visible, is fine. A curve whose line touches and crosses the border
  with content lost is OFF-FRAME.)
- PILE-UP / CLUTTER (high): two or more DISTINCT objects (e.g. a circle AND a square,
  or a shape AND a text label) sit concentric/overlapping at the SAME point with no
  separation, piling into one clump. Two solid filled shapes overlapping into a single
  muddy blended patch COUNTS as a pile-up (this is NOT the same as one intentional
  shaded region such as area under a curve). Flag it even if a label sits legibly on top.
- SEVERE IMBALANCE (medium): essentially all content jammed in one corner leaving the
  frame lopsided (NOT merely some empty space).
Name the edge/quadrant in "location".
"""

_READABILITY_RUBRIC = _CALIBRATION + """
YOUR SPECIALTY: TEXT READABILITY. In the SETTLED frame only, look for:
- TINY TEXT (high): text so small (glyph height only a tiny fraction of the frame
  height) that a viewer genuinely could not read it — especially body/explanatory text.
- TEXT OVERLAP (high): in the SETTLED (final) frame, two different text strings or
  equations occupy the SAME position so their glyphs overlap/double into a tangle you
  cannot read as ONE clean intended expression. IMPORTANT: an equation MORPH resolves to
  a single clean expression by the final frame — so if the FINAL frame STILL shows
  doubled/overlapping glyphs (e.g. two equations superimposed), that is a real overlap
  defect, NOT a morph in progress. Flag it.
- CROWDING (medium): text jammed against another object so it cannot be read.
Do NOT flag readable text merely because there is empty space around it. Do NOT flag a
single large readable equation.
"""

_CONTRAST_RUBRIC = _CALIBRATION + """
YOUR SPECIALTY: COLOUR CONTRAST & FILLS. In the SETTLED frame only, look for:
- LOW-CONTRAST TEXT (high): text whose colour is so close to the background that it is
  effectively invisible/unreadable.
- A translucent AREA FILL is NORMAL even if its blended colour looks muddy/olive/brown —
  but ONLY when it is a SINGLE intentional shaded region (e.g. area under a curve, a
  highlight band). TWO overlapping solid/filled shapes blending into a muddy patch is
  clutter, not a normal fill — leave that to the framing critic and do not excuse it.
Report only genuine readability-by-contrast problems.
"""

# (category, rubric). Motion is intentionally omitted by default — across our labeled
# set it added no recall and risked flagging normal in-progress frames; it can be added
# later behind the same interface.
_SUB_CRITICS: tuple[tuple[str, str], ...] = (
    ("framing", _FRAMING_RUBRIC),
    ("readability", _READABILITY_RUBRIC),
    ("contrast", _CONTRAST_RUBRIC),
)


@dataclass(frozen=True)
class Finding:
    category: str     # "framing" | "readability" | "contrast" | "motion"
    severity: str     # "high" | "medium" | "low"
    location: str     # normalized quadrant/edge
    issue: str        # the settled-frame defect
    remedy: str       # concrete code-level fix


@dataclass
class AestheticVerdict:
    findings: list[Finding] = field(default_factory=list)   # fused, ranked, deduped
    critics_run: int = 0
    critics_ok: int = 0
    raw_by_critic: dict = field(default_factory=dict)

    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "high")

    def has_high_severity(self) -> bool:
        return self.high_count() > 0

    def passed(self) -> bool:
        """A scene PASSES when no HIGH-severity settled-frame defect remains.

        Only HIGH severity flags — the precision lever. Medium/low are reported as
        polish, not gate failures, so normal animation never trips the gate.
        """
        return not self.has_high_severity()

    def fix_plan(self) -> str:
        """A concrete, ranked, de-duplicated remedy plan for the repair step."""
        if not self.findings:
            return ""
        lines = ["The Aesthetic Director found these settled-frame defects (fix in order):"]
        for i, f in enumerate(self.findings, 1):
            lines.append(f"{i}. [{f.severity}/{f.category}@{f.location}] {f.issue}\n   FIX: {f.remedy}")
        return "\n".join(lines)


# ── Parsing (pure) ─────────────────────────────────────────────────────────────

_VALID_LOC = {"top", "bottom", "left", "right", "center",
              "top_right", "top_left", "bottom_right", "bottom_left"}


def _norm_location(loc: object) -> str:
    s = str(loc or "center").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {"upper_right": "top_right", "upper_left": "top_left",
               "lower_right": "bottom_right", "lower_left": "bottom_left",
               "centre": "center", "middle": "center", "top_edge": "top",
               "bottom_edge": "bottom", "right_edge": "right", "left_edge": "left"}
    s = aliases.get(s, s)
    return s if s in _VALID_LOC else "center"


def _parse_findings(raw: str, category: str) -> list[Finding]:
    """Parse one sub-critic's JSON reply into validated Findings (pure)."""
    data = parse_llm_json(raw)
    if not isinstance(data, dict):
        return []
    out: list[Finding] = []
    for item in (data.get("findings") or []):
        if not isinstance(item, dict):
            continue
        sev = str(item.get("severity", "")).strip().lower()
        if sev not in _SEVERITY_RANK:
            continue
        issue = str(item.get("issue", "")).strip()
        if not issue:
            continue
        out.append(Finding(
            category=category,
            severity=sev,
            location=_norm_location(item.get("location")),
            issue=issue,
            remedy=str(item.get("remedy", "")).strip() or "adjust composition/spacing as needed",
        ))
    return out


# ── Fusion / the Director (pure) ───────────────────────────────────────────────

def fuse(findings_lists: list[list[Finding]], max_findings: int = 6) -> list[Finding]:
    """Fuse per-critic findings into one ranked, de-duplicated, conflict-resolved plan.

    DEDUP: findings about the same (category, location) collapse to ONE — the highest
    severity wins (a specific defect is never cancelled by a vaguer/lower one), and the
    winner keeps the most-severe issue/remedy text.
    CONFLICT RESOLUTION: a critic that reports nothing in its specialty does NOT cancel
    another critic's finding (we UNION findings — absence of evidence isn't evidence of
    cleanliness). Ties in severity break by category priority (framing first).
    RANK + CAP: sort by severity desc, then category priority, and keep the top
    ``max_findings`` so the repair step gets a focused, non-contradictory plan.
    """
    best: dict[tuple[str, str], Finding] = {}
    for lst in findings_lists:
        for f in lst:
            key = (f.category, f.location)
            cur = best.get(key)
            if cur is None or _SEVERITY_RANK[f.severity] > _SEVERITY_RANK[cur.severity]:
                best[key] = f
    ranked = sorted(
        best.values(),
        key=lambda f: (-_SEVERITY_RANK[f.severity], _CATEGORY_PRIORITY.get(f.category, 9)),
    )
    return ranked[:max_findings]


# ── Orchestration (impure shell — vision calls) ────────────────────────────────

async def _default_vision(frames: list[bytes], caption: str) -> str:
    """Lazy import so the pure logic imports without pulling the LLM stack."""
    from config import VISION_PROVIDER
    from llm import chat_with_images
    return await chat_with_images(frames, caption, provider=VISION_PROVIDER)


async def run_panel(frames: list[bytes], scene_hint: str = "", vision_fn=None) -> AestheticVerdict | None:
    """Run every sub-critic over the frames and fuse their findings.

    ``vision_fn(frames, caption) -> str`` is injectable so tests drive the whole panel
    with mocked replies (no vision API). Resilient: a sub-critic that errors or returns
    junk contributes no findings but does not sink the panel; only if EVERY critic fails
    do we return None (unmeasured) so the caller can fall back / skip.
    """
    vision_fn = vision_fn or _default_vision
    if not frames:
        return None

    async def _one(category: str, rubric: str):
        try:
            raw = await vision_fn(frames, rubric)
            # An empty/blank reply means the vision call FAILED (chat_with_images
            # returns "" on error). Treat that as "this critic could not judge"
            # (None), NOT as "this critic found nothing" (a clean vote) — otherwise a
            # silent vision failure would excuse a real defect (a recall hazard).
            if not raw or not str(raw).strip():
                logger.warning("Sub-critic %s returned empty — treated as failure, not clean", category)
                return category, "", None
            return category, raw, _parse_findings(raw, category)
        except Exception as e:  # noqa: BLE001
            logger.warning("Sub-critic %s failed (non-fatal): %s", category, e)
            return category, "", None

    results = await asyncio.gather(*[_one(c, r) for c, r in _SUB_CRITICS])

    raw_by_critic: dict = {}
    findings_lists: list[list[Finding]] = []
    ok = 0
    for category, raw, parsed in results:
        raw_by_critic[category] = raw
        if parsed is not None:
            ok += 1
            findings_lists.append(parsed)

    if ok == 0:
        logger.warning("Aesthetic Director: every sub-critic failed for %s", scene_hint or "?")
        return None

    verdict = AestheticVerdict(
        findings=fuse(findings_lists),
        critics_run=len(_SUB_CRITICS),
        critics_ok=ok,
        raw_by_critic=raw_by_critic,
    )
    logger.info("Aesthetic Director [%s]: %d findings (%d high), %d/%d critics ok",
                scene_hint or "?", len(verdict.findings), verdict.high_count(), ok, len(_SUB_CRITICS))
    return verdict


# ── Converging refinement loop (Phase 4) ───────────────────────────────────────

@dataclass
class RefinePass:
    index: int
    high: int          # high-severity findings this pass (-1 = couldn't judge)
    findings: int      # total findings this pass
    converged: bool     # no high-severity defect remained


@dataclass
class RefineResult:
    best_code: str
    best_verdict: AestheticVerdict | None
    passes: list[RefinePass] = field(default_factory=list)
    converged: bool = False
    best_video: object = None


async def refine_visual(initial_code, render_fn, panel_fn, repair_fn, max_passes: int = 3) -> RefineResult:
    """Render → judge with the panel → repair the HIGH-severity findings → re-render,
    until convergence (no high-severity defect) or ``max_passes`` repairs. Always keeps
    the BEST (fewest high-severity) render; bounded; graceful on any failure.

    All I/O is injected so the loop is unit-tested deterministically with mocks:
      render_fn(code)            -> (video, frames)  (frames=[] on failure)
      panel_fn(frames, hint)     -> AestheticVerdict | None
      repair_fn(code, fix_plan)  -> str               (new code; "" to give up)
    """
    code = initial_code
    best_code, best_verdict, best_video = initial_code, None, None
    best_score: int | None = None
    passes: list[RefinePass] = []

    for i in range(max_passes + 1):
        try:
            video, frames = await render_fn(code)
        except Exception as e:  # noqa: BLE001
            logger.warning("refine: render failed at pass %d: %s", i, e)
            video, frames = None, []

        verdict: AestheticVerdict | None = None
        if frames:
            try:
                verdict = await panel_fn(frames, f"refine-pass-{i}")
            except Exception as e:  # noqa: BLE001
                logger.warning("refine: panel failed at pass %d: %s", i, e)
                verdict = None

        high = verdict.high_count() if verdict else None
        # lower high = better; an unjudgeable pass must never be preferred over a judged one
        score = high if high is not None else 10 ** 6
        if video is not None and (best_score is None or score < best_score):
            best_score, best_code, best_verdict, best_video = score, code, verdict, video

        passes.append(RefinePass(
            index=i,
            high=high if high is not None else -1,
            findings=len(verdict.findings) if verdict else 0,
            converged=bool(verdict and not verdict.has_high_severity()),
        ))

        if verdict is None:                       # couldn't judge → stop, keep best so far
            break
        if not verdict.has_high_severity():        # converged
            break
        if i == max_passes:                        # hit the cap
            break

        try:
            new_code = await repair_fn(code, verdict.fix_plan())
        except Exception as e:  # noqa: BLE001
            logger.warning("refine: repair failed at pass %d: %s", i, e)
            new_code = ""
        if not new_code or new_code.strip() == code.strip():
            break                                  # repair gave up / no change → stop
        code = new_code

    converged = bool(best_verdict is not None and not best_verdict.has_high_severity())
    return RefineResult(best_code=best_code, best_verdict=best_verdict,
                        passes=passes, converged=converged, best_video=best_video)


# ── Drop-in adapter for the bot's existing visual-feedback loop ─────────────────

_SEVERITY_PENALTY = {"high": 3.0, "medium": 1.0, "low": 0.5}


def verdict_to_score(verdict: AestheticVerdict) -> float:
    """Map a panel verdict to a 0-10 score for the UI (10 = clean settled frame)."""
    penalty = sum(_SEVERITY_PENALTY.get(f.severity, 0.0) for f in verdict.findings)
    return max(0.0, 10.0 - penalty)


async def critique_render_panel(video_path, prompt: str = "", code: str = ""):
    """Panel equivalent of ``visual_critic.critique_render`` — extract keyframes, run
    the panel, and return a ``VisualVerdict`` the bot's existing loop already consumes.

    ``passed`` is True iff NO high-severity settled-frame defect remains; ``issues`` and
    ``regenerate_guidance`` carry the director's ranked fix plan. Returns None (skip) when
    frames can't be extracted or every sub-critic fails — fully non-fatal.
    """
    from visual_critic import VisualVerdict, extract_keyframes  # local: avoid import cycle
    frames = await extract_keyframes(video_path)
    if not frames:
        return None
    verdict = await run_panel(frames, scene_hint=(prompt or "")[:48])
    if verdict is None:
        return None
    issues = [f"[{f.severity}/{f.category}@{f.location}] {f.issue}" for f in verdict.findings]
    return VisualVerdict(
        passed=verdict.passed(),
        score=verdict_to_score(verdict),
        issues=issues,
        regenerate_guidance=verdict.fix_plan(),
    )
