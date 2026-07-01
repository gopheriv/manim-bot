"""Pedagogical storyboard directive — the 5-stage arc for complex topics.

When a topic is complex (Fourier transform, eigenvectors, gradient descent, …)
the storyboard director must do more than plan shots — it must TEACH. This module
encodes the principles from docs/RESEARCH_MANIM.md section B as a concrete
directive injected into the director's system prompt.

Also provides ``validate_pedagogical_storyboard()`` — a cheap plan-level check
that verifies a complex-topic storyboard carries the structural hallmarks of a
well-taught explainer (misconception, spine metaphor, ordered arc stages).

Non-fatal: a failing check triggers ONE retry, not a crash.
"""
from __future__ import annotations

# ── The 5 stages every pedagogical storyboard must follow ────────────────────

STAGES = ("hook", "intuition", "formalize", "generalize", "payoff")

# ── Pedagogical directive ─────────────────────────────────────────────────────

PEDAGOGY_DIRECTIVE = """## PEDAGOGY — teach like 3Blue1Brown, not like a textbook

You are directing an EXPLAINER, not just an animation. The viewer must LEARN by the
end — not just see pretty math. Follow this structure strictly:

### 1. THE 5-STAGE ARC (every beat must belong to exactly one stage, in this order)
  - **hook** — Start with a concrete, tangible question the viewer already has intuition
    about. "What happens if…?", "Why does…?", a specific number, a physical object. The
    viewer should feel curious, not confused.
  - **intuition** — Let the viewer "feel" the concept through a manipulable visual BEFORE
    any notation appears. Build it with motion, color, and interaction. The viewer should
    nod along, thinking "oh, I see what's happening."
  - **formalize** — ONLY now introduce notation, symbols, and the formal definition. The
    viewer already knows what it MEANS — the notation just names it. NEVER show the formula
    before the intuition.
  - **generalize** — Show the specific case was one instance of a broader principle. The
    viewer realizes the idea applies everywhere, not just to the example.
  - **payoff** — The "aha" moment: an unexpected connection, a surprise, or a satisfying
    resolution that ties the whole lesson together. End on wonder, not a dry summary.

Each beat's "stage" field MUST be one of: hook, intuition, formalize, generalize, payoff.

### 2. PREEMPT ONE MISCONCEPTION
Name (in the "misconception" field) the SINGLE most common place learners get stuck on this
topic. Then design at least one beat that DIRECTLY defuses it — show why the naive intuition
is wrong, and what the correct mental model is. Don't just mention it; VISUALIZE the trap
and the escape.

### 3. ONE SPINE METAPHOR
Pick ONE visual through-line (record it in "spine_metaphor") and carry it across ALL beats.
Don't switch metaphors mid-lesson — the viewer must track one consistent visual language
from hook to payoff. The metaphor menu (if provided) offers candidates.

### 4. ONE CONCEPT = ONE COLOR
Bind each key concept to a color and keep it CONSISTENT across every beat, equation, graph,
and label. x is always BLUE; the function is always YELLOW; the result is always GREEN.
Record the binding in the "palette" field and use tex_to_color_map / set_color_by_tex.

### 5. PACING
  - One beat = one idea. Never cram two concepts into one beat.
  - After each significant reveal, add an explicit pause (set "pause_after" on that beat,
    typically 0.5–1.5 seconds) so the viewer absorbs before the next idea.
  - The beat BEFORE the payoff stage should have a beat of silence (pause_after ≥ 1.0) —
    this is the breath before the "aha."
  - NEVER show the formula in the hook or intuition stages — notation belongs in
    formalize and later."""


# ── Plan-level check ─────────────────────────────────────────────────────────

_REQUIRED_STAGES = frozenset({"hook", "intuition", "payoff"})


def validate_pedagogical_storyboard(sb: dict) -> list[str]:
    """Cheap structural check: does a pedagogical storyboard have the hallmarks?

    Returns a list of human-readable issues. Empty = passes. Non-fatal — the caller
    decides whether to retry or accept as-is.

    Checks:
      - misconception field is non-empty
      - spine_metaphor field is non-empty
      - beat stages include at least hook + intuition + payoff in that order
      - no notation (formalize) appears before an intuition beat
    """
    issues: list[str] = []

    misconception = str(sb.get("misconception") or "").strip()
    if not misconception:
        issues.append("Missing 'misconception' — a pedagogical storyboard must name "
                       "the common learner trap and defuse it.")

    spine = str(sb.get("spine_metaphor") or "").strip()
    if not spine:
        issues.append("Missing 'spine_metaphor' — pick ONE visual through-line and "
                       "carry it across all beats.")

    beats = sb.get("beats") or []
    stages_found: list[str] = []
    for b in beats:
        stage = str(b.get("stage") or "").strip().lower()
        if stage in STAGES:
            stages_found.append(stage)

    missing_stages = _REQUIRED_STAGES - set(stages_found)
    if missing_stages:
        issues.append(f"Missing required stages: {', '.join(sorted(missing_stages))}. "
                       f"Found: {stages_found or 'none'}.")

    # Intuition must come before formalize
    intuition_idx = None
    formalize_idx = None
    for i, s in enumerate(stages_found):
        if s == "intuition" and intuition_idx is None:
            intuition_idx = i
        if s == "formalize" and formalize_idx is None:
            formalize_idx = i
    if intuition_idx is not None and formalize_idx is not None:
        if formalize_idx < intuition_idx:
            issues.append("formalize appears BEFORE intuition — NEVER show the formula "
                           "before the viewer has built intuition.")

    return issues
