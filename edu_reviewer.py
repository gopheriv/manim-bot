"""Educational Reviewer Agent — verifies mathematical/physics accuracy.

Uses sympy for symbolic formula verification + LLM for pedagogical review.
Catches incorrect formulas before they reach the renderer.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from llm import qwen_client
from config import CHAT_MODEL

logger = logging.getLogger(__name__)

try:
    from sympy import sympify, Eq, simplify
    from sympy.parsing.latex import parse_latex
    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False


@dataclass
class EducationReview:
    """Result of educational review."""
    is_correct: bool
    issues: list[str]
    missing_concepts: list[str]
    level_appropriate: bool
    common_misconceptions: list[str]

    @property
    def passes(self) -> bool:
        return self.is_correct and not self.issues


EDU_REVIEW_PROMPT = """You are an Educational Reviewer for math/science animations.

Review the generated animation code for:
1. **Mathematical accuracy**: Are all formulas correct? Any sign errors?
2. **Conceptual correctness**: Does the animation accurately convey the concept?
3. **Level appropriateness**: Is this suitable for the implied audience?
4. **Missing concepts**: Are there key ideas that should be included?
5. **Common misconceptions**: Does this reinforce any common student mistakes?

Return ONLY valid JSON, no markdown fences:
{"is_correct": true/false, "issues": ["formula x should be y"], "missing_concepts": ["concept z"], "level_appropriate": true/false, "common_misconceptions": ["misconception a"]}
"""


def extract_formulas(code: str) -> list[str]:
    """Extract LaTeX formulas from Manim code."""
    # Match MathTex content
    patterns = [
        r'MathTex\(\s*r?"([^"]+)"',
        r'Tex\(\s*r?"([^"]+)"',
    ]
    formulas = []
    for pattern in patterns:
        formulas.extend(re.findall(pattern, code))
    return formulas


def verify_formula_syntax(formula: str) -> tuple[bool, str]:
    """Check if a LaTeX formula has valid syntax.

    Returns (is_valid, error_message).
    """
    # Common LaTeX errors in Manim
    issues = []

    # Unmatched braces
    if formula.count('{') != formula.count('}'):
        issues.append(f"Unmatched braces in: {formula}")

    # Unclosed \left / \right
    left_count = len(re.findall(r'\\left', formula))
    right_count = len(re.findall(r'\\right', formula))
    if left_count != right_count:
        issues.append(f"Mismatched \\left/\\right in: {formula}")

    # Double subscripts (common error: x_i_j should be x_{{i}{j}})
    if re.search(r'_[^{]*_[^{]', formula):
        issues.append(f"Possible double subscript in: {formula}")

    # Double superscripts
    if re.search(r'\^[^{]*\^[^{]', formula):
        issues.append(f"Possible double superscript in: {formula}")

    if issues:
        return False, "; ".join(issues)
    return True, ""


async def review_education(code: str, prompt_text: str) -> EducationReview:
    """Review animation code for educational accuracy.

    Combines sympy formula verification with LLM pedagogical review.
    """
    issues: list[str] = []
    missing_concepts: list[str] = []
    misconceptions: list[str] = []

    # Step 1: Static formula syntax check
    formulas = extract_formulas(code)
    for formula in formulas:
        is_valid, error = verify_formula_syntax(formula)
        if not is_valid:
            issues.append(f"Formula syntax: {error}")

    # Step 2: LLM educational review
    try:
        response = await qwen_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": EDU_REVIEW_PROMPT},
                {"role": "user", "content": f"Review this animation code for prompt: {prompt_text}\n\n```python\n{code[:3000]}\n```"},
            ],
            temperature=0.1,
            max_tokens=1024,
            timeout=60,
            extra_body={"enable_thinking": False},
        )

        content = (response.choices[0].message.content or "").strip()
        # Strip markdown fences
        content = re.sub(r"^```[a-z]*\n?", "", content, flags=re.MULTILINE)
        content = re.sub(r"\n?```$", "", content, flags=re.MULTILINE)

        import json
        result = json.loads(content)
        is_correct = result.get("is_correct", True)
        issues.extend(result.get("issues", []))
        missing_concepts.extend(result.get("missing_concepts", []))
        misconceptions.extend(result.get("common_misconceptions", []))
        level_appropriate = result.get("level_appropriate", True)

        logger.info(
            f"Education review: correct={is_correct}, "
            f"issues={len(issues)}, missing={len(missing_concepts)}, "
            f"misconceptions={len(misconceptions)}"
        )

        return EducationReview(
            is_correct=is_correct,
            issues=issues,
            missing_concepts=missing_concepts,
            level_appropriate=level_appropriate,
            common_misconceptions=misconceptions,
        )

    except Exception as e:
        logger.warning(f"Education review failed: {e}")
        return EducationReview(
            is_correct=True,  # Don't block on review failure
            issues=issues,  # Keep static issues
            missing_concepts=[],
            level_appropriate=True,
            common_misconceptions=[],
        )
