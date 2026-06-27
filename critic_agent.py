"""Critic Agent — pre-render quality scoring of generated Manim code.

Scores code on 6 dimensions BEFORE sending to renderer, catching
bad code early and saving render time/cost.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from llm import qwen_client
from config import CHAT_MODEL

logger = logging.getLogger(__name__)

CRITIC_SYSTEM_PROMPT = """You are a Manim Code Critic. Your job is to score generated code on 6 dimensions BEFORE it gets rendered.

Scoring rubric (0-10 each):

1. **Visual clarity**: Are objects well-spaced? No overlap? Font sizes readable?
   - 0: Everything stacked on top of each other
   - 5: Most objects spaced, some overlap
   - 10: Clean layout, every object visible

2. **Animation flow**: Smooth transitions? Logical sequence? No jarring jumps?
   - 0: Objects appear randomly, no flow
   - 5: Some logical order but transitions abrupt
   - 10: Clear story arc: intro → development → insight

3. **Educational value**: Does it clearly convey the concept? Formulas correct?
   - 0: Mathematically wrong or irrelevant
   - 5: Concept shown but unclear
   - 10: Concept crystal clear, step-by-step

4. **Code quality**: Clean Manim patterns? No anti-patterns?
   - 0: Broken imports, missing methods, syntax errors
   - 5: Works but messy (hardcoded values, no reuse)
   - 10: Clean structure, reusable patterns, proper imports

5. **Performance**: Within hardware budget? No heavy operations?
   - 0: Surface rendering, 10+ updaters, 500+ frames
   - 5: Some heavy elements (1-2 updaters, moderate frames)
   - 10: Lightweight, <5 self.play, no updaters

6. **Aesthetic**: Colors, style, polish? Visually appealing?
   - 0: Default colors everywhere, no style
   - 5: Some color choices, basic style
   - 10: Cohesive palette, polished, professional

Return ONLY valid JSON, no markdown fences:
{"scores": {"visual_clarity": N, "animation_flow": N, "educational_value": N, "code_quality": N, "performance": N, "aesthetic": N}, "overall": N, "issues": ["issue1", "issue2"], "suggestions": ["suggestion1"]}

The overall score is a weighted average: visual_clarity*0.2 + animation_flow*0.15 + educational_value*0.25 + code_quality*0.1 + performance*0.1 + aesthetic*0.2
"""


@dataclass
class CriticReview:
    """Result of code criticism."""
    scores: dict[str, float]
    overall: float
    issues: list[str]
    suggestions: list[str]

    @property
    def passes(self) -> bool:
        """Code passes minimum quality threshold (overall >= 5.0)."""
        return self.overall >= 5.0

    @property
    def needs_repair(self) -> bool:
        """Code needs repair (overall < 7.0)."""
        return self.overall < 7.0


async def critique_code(manim_code: str, original_prompt: str) -> CriticReview:
    """Score Manim code on 6 dimensions and return critique.

    Args:
        manim_code: The generated Manim Python code.
        original_prompt: User's original animation request.

    Returns:
        CriticReview with scores, issues, and suggestions.
    """
    try:
        # Truncate very long code to stay within token limits
        code_snippet = manim_code[:4000] if len(manim_code) > 4000 else manim_code

        response = await qwen_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
                {"role": "user", "content": f"Critique this Manim code for prompt: {original_prompt}\n\n```python\n{code_snippet}\n```"},
            ],
            temperature=0.2,
            max_tokens=1024,
            timeout=30,
            extra_body={"enable_thinking": False},
        )

        content = (response.choices[0].message.content or "").strip()
        # Strip markdown fences if present
        content = re.sub(r"^```[a-z]*\n?", "", content, flags=re.MULTILINE)
        content = re.sub(r"\n?```$", "", content, flags=re.MULTILINE)

        result = json.loads(content)
        scores = result.get("scores", {})
        overall = result.get("overall", 0.0)
        issues = result.get("issues", [])
        suggestions = result.get("suggestions", [])

        review = CriticReview(
            scores=scores,
            overall=overall,
            issues=issues,
            suggestions=suggestions,
        )

        logger.info(
            f"Critic review: overall={overall:.1f}, "
            f"passes={review.passes}, "
            f"issues={len(issues)}, "
            f"suggestions={len(suggestions)}"
        )
        return review

    except Exception as e:
        logger.warning(f"Critique failed: {e}")
        # Return neutral review — don't block render on critic failure
        return CriticReview(
            scores={
                "visual_clarity": 5.0,
                "animation_flow": 5.0,
                "educational_value": 5.0,
                "code_quality": 5.0,
                "performance": 5.0,
                "aesthetic": 5.0,
            },
            overall=5.0,
            issues=[],
            suggestions=[],
        )


# ── Lightweight static checks (no LLM needed) ──────────────────────────────

def static_quality_check(code: str) -> dict[str, bool | int | list[str]]:
    """Fast static checks that catch obvious issues without LLM cost."""
    issues: list[str] = []

    # Structure checks
    if "class GenScene" not in code:
        issues.append("Missing GenScene class")
    if "def construct" not in code:
        issues.append("Missing construct method")
    if "self.play" not in code:
        issues.append("No animations — scene will be static")
    if "self.wait" not in code and "self.play" in code:
        issues.append("No self.wait — animations may be too fast to see")

    # Common anti-patterns
    if code.count(".move_to(ORIGIN)") > 2:
        issues.append(f"Multiple ORIGIN placements ({code.count('.move_to(ORIGIN)')})")
    if "font_size" not in code and ("Text(" in code or "MathTex(" in code):
        issues.append("Text/MathTex without font_size — may be unreadable")
    if ".arrange(" not in code and "VGroup(" in code:
        issues.append("VGroup without arrange — objects may overlap")

    # Heavy operation detection
    updater_count = len(re.findall(r"always_redraw|add_updater", code))
    if updater_count > 3:
        issues.append(f"Too many updaters ({updater_count}) — may be slow")

    surface_count = len(re.findall(r"Surface|ParametricSurface", code))
    if surface_count > 0:
        issues.append(f"Surface rendering ({surface_count}) — very heavy on 8GB RAM")

    play_count = len(re.findall(r"self\.play\b", code))
    if play_count > 15:
        issues.append(f"Too many self.play calls ({play_count}) — scene too long")

    return {
        "issues": issues,
        "updater_count": updater_count,
        "surface_count": surface_count,
        "play_count": play_count,
        "has_structure": "class GenScene" in code and "def construct" in code,
        "has_animations": "self.play" in code,
    }
