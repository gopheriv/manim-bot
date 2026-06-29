"""Storyboard / cinematography IR — the director's plan, generated BEFORE code.

The system used to ask one LLM call for one flat ``GenScene.construct()`` and
hope it was well directed. This module introduces an intermediate representation:
a structured, validatable **storyboard** of beats (shots) with purpose, timing,
objects, camera moves, transitions, a semantic palette, and per-beat narration.

Flow:  prompt → generate_storyboard (LLM, reasoning on) → parse_storyboard →
validate_storyboard (as a *composition*) → format_storyboard_for_codegen → the
generator implements it beat-by-beat. The model stays the animator; the IR gives
it the direction it previously lacked, and its timestamped beats are the
foundation for real narration↔visual sync.

Like ``scene_planner``, every step is non-fatal: a bad/blank storyboard simply
falls back to the lighter scene-layout plan and today's behavior.
"""

from __future__ import annotations

import logging
from typing import Any

from common import parse_llm_json

logger = logging.getLogger(__name__)


# ── Director system prompt ────────────────────────────────────────────────────

STORYBOARD_SYSTEM_PROMPT = """You are an award-winning motion-design DIRECTOR storyboarding a short mathematical/scientific explainer that will be animated in Manim Community Edition.

Design the FILM before any code exists. Think in beats (shots): what the viewer sees, in what order, with what timing, camera, and spoken line — so the final animation is intentionally directed, builds intuition step by step, and is visually beautiful.

Output ONLY valid JSON (no markdown fences) with EXACTLY this shape:
{
  "title": "short title",
  "concept": "the ONE idea the viewer should understand by the end",
  "key_points": ["ordered sub-ideas the film MUST cover: definition, intuition, derivation step(s), worked example, common misconception/edge case, recap"],
  "duration_target_s": 30,
  "palette": {"known": "#hex", "focus": "#hex", "result": "#hex", "transform": "#hex", "bg": "#hex"},
  "beats": [
    {
      "id": "b1",
      "name": "hook | build | develop | insight | resolution",
      "purpose": "WHY this beat exists — the question it answers or the curiosity it creates",
      "start_s": 0,
      "end_s": 4,
      "objects": ["named objects on screen this beat, e.g. axes, curve f(x), tangent line"],
      "action": "what ANIMATES, as verbs: 'draw axes, plot f(x) with Create, write the title'",
      "camera": "hold | push in on <target> | pan to follow <target> | pull back to reveal <scale> — name the target AND the reason",
      "transition_in": "how this beat enters from the previous (e.g. ReplacementTransform the equation, FadeTransform, GrowFromCenter)",
      "emphasis": "where the viewer's eye should land",
      "covers": ["which key_point(s) from the top-level list this beat realizes"],
      "narration": "1-3 sentences that actually TEACH this point, conversational"
    }
  ]
}

Rules:
- Beat count, duration, and key-point coverage: follow the DEPTH & COVERAGE block below. Clear educational arc: hook → define → build intuition → derive → worked example → address a misconception → recap — don't stop at the headline idea; the beats must collectively cover EVERY key point.
- Timings are contiguous and monotonic (each beat's start_s == previous end_s); total ≈ duration_target_s (see the DEPTH & COVERAGE block).
- Use color SEMANTICALLY and consistently: each concept keeps its palette role across beats.
- Every camera move must name a target and a reason; prefer "hold" unless a move serves the idea.
- Prefer MORPHING/transform between related forms over fade-and-replace.
- Each beat: a purpose, a concrete implementable action, and 1-3 narration sentences that teach the point.
- Reveal progressively — never dump everything in beat 1.
- Keep each beat implementable in Manim CE (real objects, real animations)."""


# Depth profiles — the length/coverage bands per depth (set by recommend_depth).
_DEPTH_PROFILES = {
    "compact":  {"beats": "4-6",  "duration": "25-40", "key_points": "3-4"},
    "standard": {"beats": "6-9",  "duration": "40-60", "key_points": "4-6"},
    "deep":     {"beats": "8-12", "duration": "60-90", "key_points": "6-9"},
}


def build_storyboard_prompt(
    lessons: list[str] | None = None,
    hard_constraints: list[str] | None = None,
    depth: str = "standard",
    metaphor_menu: str = "",
) -> str:
    """Build the director system prompt, optionally seeded with learned lessons.

    ``depth`` (``compact`` | ``standard`` | ``deep``, from ``recommend_depth``)
    selects the length/coverage bands — beat count, duration, and number of
    key points — so longer, denser films are requested for richer topics.
    ``metaphor_menu`` (from ``visual_metaphors.format_metaphors_for_director``)
    offers curated teaching metaphors for the director to pick a spine from.
    ``lessons`` are recurring Judge-rejection defects injected at the PLANNING
    stage (so the director designs around them, instead of them being buried in a
    code-gen footer). ``hard_constraints`` are lessons that have recurred enough
    times to become non-negotiable MUST rules — surfaced most prominently.
    """
    sections = [STORYBOARD_SYSTEM_PROMPT]

    profile = _DEPTH_PROFILES.get(depth, _DEPTH_PROFILES["standard"])
    sections.append(
        "## DEPTH & COVERAGE\n"
        f"- Beats: {profile['beats']} (use more for richer topics).\n"
        f"- duration_target_s: {profile['duration']} seconds.\n"
        f"- key_points: list {profile['key_points']} ordered sub-ideas the film MUST cover "
        "(definition → intuition → derivation step(s) → worked example → common misconception/edge case "
        "→ recap), and design the beats so they collectively realize EVERY one. "
        "Don't stop at the headline idea — teach the whole topic at this depth."
    )

    # Teaching-metaphor palette — a spine for the explainer (chosen by the director).
    if metaphor_menu:
        sections.append(metaphor_menu)

    if hard_constraints:
        rules = "\n".join(f"- {c}" for c in hard_constraints)
        sections.append(
            "## HARD CONSTRAINTS (these defects keep recurring — the plan MUST "
            "eliminate them; design every beat so they cannot happen):\n" + rules
        )
    if lessons:
        notes = "\n".join(f"- {lsn}" for lsn in lessons)
        sections.append(
            "## LESSONS FROM PRIOR REVIEWS (bake these into the direction):\n" + notes
        )
    return "\n\n".join(sections)


# ── Parsing ───────────────────────────────────────────────────────────────────

_REQUIRED_BEAT_FIELDS = {"name", "purpose", "action", "narration"}


def parse_storyboard(raw: str) -> dict[str, Any] | None:
    """Parse + structurally validate the LLM storyboard JSON. None if unusable."""
    if not raw:
        return None
    # Shared parser strips fences and salvages a single balanced JSON object
    # (brace-aware — no greedy "first { to last }" over-capture).
    sb = parse_llm_json(raw)
    if sb is None:
        logger.warning("Storyboard JSON parse failed")
        return None

    beats = sb.get("beats")
    if not isinstance(beats, list) or not beats:
        logger.warning("Storyboard has no beats")
        return None

    # Every beat needs the load-bearing fields, else the plan isn't usable.
    for i, beat in enumerate(beats):
        if not isinstance(beat, dict):
            logger.warning("Storyboard beat %d is not an object", i)
            return None
        missing = _REQUIRED_BEAT_FIELDS - set(beat.keys())
        if missing:
            logger.warning("Storyboard beat %d missing fields: %s", i, missing)
            return None

    # Coerce duration_target_s to a number: the LLM sometimes quotes it
    # ("30"), which would skip validation's isinstance check and raise a
    # TypeError in the downstream narration length budget (str > int).
    dt = sb.get("duration_target_s")
    if isinstance(dt, str):
        try:
            sb["duration_target_s"] = float(dt) if "." in dt else int(dt)
        except ValueError:
            sb.pop("duration_target_s", None)

    return sb


# ── Validation as a composition (non-fatal — surfaced, not blocking) ──────────

def validate_storyboard(sb: dict[str, Any]) -> list[str]:
    """Critique the storyboard as a *composition*. Returns human-readable issues.

    Non-fatal: issues are logged/surfaced to the generator, not a hard reject —
    a slightly-off plan still beats no plan.
    """
    issues: list[str] = []
    beats = sb.get("beats", [])

    if len(beats) < 3:
        issues.append(f"Only {len(beats)} beats — an explainer needs a hook→build→insight→resolution arc (more beats for a deeper topic).")
    if len(beats) > 14:
        issues.append(f"{len(beats)} beats is a lot even for a deep topic — consider merging closely-related beats.")

    # Coverage: a detailed explainer should enumerate the sub-ideas it teaches.
    key_points = sb.get("key_points")
    if not isinstance(key_points, list) or len(key_points) < 3:
        issues.append("Few/no key_points listed — a detailed explainer should name the ordered sub-ideas it covers (definition, intuition, example, recap…).")

    # Timeline coherence: monotonic, roughly contiguous, total near target.
    prev_end = None
    total = 0.0
    for i, b in enumerate(beats):
        try:
            s = float(b.get("start_s", 0)); e = float(b.get("end_s", 0))
        except (TypeError, ValueError):
            issues.append(f"Beat {i+1} ({b.get('name','?')}): non-numeric timing.")
            continue
        if e <= s:
            issues.append(f"Beat {i+1} ({b.get('name','?')}): end_s <= start_s.")
        if prev_end is not None:
            if s < prev_end - 1e-6:
                # Going backwards in time — a non-monotonic beat ordering.
                issues.append(f"Beat {i+1} ({b.get('name','?')}): starts at {s}s, BEFORE the previous beat ended at {prev_end}s — beats must run forward in time.")
            elif abs(s - prev_end) > 0.5:
                issues.append(f"Beat {i+1} ({b.get('name','?')}): starts at {s}s but previous ended at {prev_end}s — keep beats contiguous.")
        prev_end = e
        total = max(total, e)

    target = sb.get("duration_target_s")
    if isinstance(target, (int, float)) and target > 0 and total > 0:
        if not (target * 0.6 <= total <= target * 1.4):
            # `total` is the last beat's end time (the film's span), not a sum.
            issues.append(f"Beat timings span ~{total:.0f}s but target is {target}s — align them.")

    # Semantic palette present.
    palette = sb.get("palette")
    if not isinstance(palette, dict) or len(palette) < 3:
        issues.append("Palette should define at least 3 semantic roles (e.g. known/focus/result).")

    # Camera discipline: a move should name a reason (heuristic: not just 'push in').
    for i, b in enumerate(beats):
        cam = str(b.get("camera", "")).strip().lower()
        if cam and cam not in ("hold", "none", "static") and len(cam.split()) < 3:
            issues.append(f"Beat {i+1} ({b.get('name','?')}): camera move '{cam}' lacks a target/reason.")

    # Crowding: too many objects in a single beat reads as clutter.
    for i, b in enumerate(beats):
        objs = b.get("objects") or []
        if isinstance(objs, list) and len(objs) > 6:
            issues.append(f"Beat {i+1} ({b.get('name','?')}): {len(objs)} objects — risks a crowded frame, reveal progressively.")

    return issues


# ── Compile to a generator spec ───────────────────────────────────────────────

def _fmt_time(value: Any) -> str:
    """Format a beat timestamp, tolerating non-numeric LLM output ('?')."""
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return "?"


def format_storyboard_for_codegen(sb: dict[str, Any]) -> str:
    """Render the storyboard as a directive spec the code generator implements."""
    lines: list[str] = []
    lines.append("## STORYBOARD — implement EXACTLY, beat by beat (this is the director's plan)")
    if sb.get("concept"):
        lines.append(f"Concept (what the viewer must understand): {sb['concept']}")
    key_points = sb.get("key_points")
    if isinstance(key_points, list) and key_points:
        lines.append("COVER EVERY POINT (the beats must collectively teach all of these):")
        for kp in key_points:
            lines.append(f"  - {kp}")
    if sb.get("duration_target_s"):
        lines.append(f"Target duration: ~{sb['duration_target_s']}s — set run_time/wait so the beats hit these timings.")
    palette = sb.get("palette")
    if isinstance(palette, dict) and palette:
        pal = ", ".join(f"{k}={v}" for k, v in palette.items())
        lines.append(f"Semantic palette (keep each role's color consistent across beats): {pal}")
    lines.append("")
    for i, b in enumerate(sb.get("beats", []), 1):
        s, e = _fmt_time(b.get("start_s")), _fmt_time(b.get("end_s"))
        lines.append(f"BEAT {i} — {b.get('name','')} ({s}-{e}s)")
        lines.append(f"  purpose: {b.get('purpose','')}")
        objs = b.get("objects")
        if objs:
            lines.append(f"  objects: {', '.join(map(str, objs)) if isinstance(objs, list) else objs}")
        if b.get("action"):
            lines.append(f"  action: {b['action']}")
        if b.get("transition_in"):
            lines.append(f"  transition in: {b['transition_in']}")
        if b.get("camera"):
            lines.append(f"  camera: {b['camera']}")
        if b.get("emphasis"):
            lines.append(f"  emphasis: {b['emphasis']}")
        covers = b.get("covers")
        if covers:
            # Which top-level key_point(s) this beat realizes — forward the
            # director's coverage map so the generator teaches every sub-idea.
            lines.append(f"  covers: {', '.join(map(str, covers)) if isinstance(covers, list) else covers}")
        if b.get("narration"):
            lines.append(f"  narration: \"{b['narration']}\"")
        lines.append("")
    lines.append(
        "Implement EVERY beat in order. Honor the timings (run_time + self.wait), the camera "
        "moves (use MovingCameraScene), the transitions between beats, and the semantic colors. "
        "Morph/transform related objects between beats rather than fading and recreating them."
    )
    return "\n".join(lines)


def storyboard_narration(sb: dict[str, Any]) -> str:
    """Concatenate the per-beat narration lines in order (basis for the VO script).

    Returns "" when the storyboard carries no narration; logs a warning in that
    case so callers don't silently end up with an empty voiceover script.
    """
    if not isinstance(sb, dict):
        logger.warning("storyboard_narration called with a non-storyboard (%r)", type(sb).__name__)
        return ""
    lines = [str(b.get("narration", "")).strip() for b in sb.get("beats", [])]
    narration = " ".join(l for l in lines if l)
    if not narration:
        logger.warning("Storyboard has no narration on any beat — voiceover script will be empty")
    return narration
