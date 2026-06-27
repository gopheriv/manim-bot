"""Judge of AI Court — MiniMax M3 code review before render.

Separate model (not the generator) reviews generated Manim code
with ACCEPT/REPAIR/REJECT verdicts. Catches bugs, anti-patterns,
and performance issues Qwen may miss (model blindness).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum

from openai import AsyncOpenAI

from config import (
    JUDGE_API_KEY,
    JUDGE_BASE_URL,
    JUDGE_MAX_ITERATIONS,
    JUDGE_MODEL,
    JUDGE_TIMEOUT,
)
from critic_agent import CriticReview, static_quality_check

logger = logging.getLogger(__name__)

# ── Judge client (MiniMax M3 or other non-Qwen model) ────────────────────────

judge_client = AsyncOpenAI(
    api_key=JUDGE_API_KEY,
    base_url=JUDGE_BASE_URL,
    timeout=JUDGE_TIMEOUT,
)


# ── Verdict enum ─────────────────────────────────────────────────────────────

class JudgeVerdict(str, Enum):
    ACCEPT = "ACCEPT"      # Code is good enough — send to render
    REPAIR = "REPAIR"      # Fixable issues — send back to generator
    REJECT = "REJECT"      # Fundamental problems — regenerate from scratch


# ── Review dataclass ─────────────────────────────────────────────────────────

@dataclass
class JudgeReview:
    """Result of Judge's code review."""
    verdict: JudgeVerdict
    score: float            # 0-10 overall quality
    critical_issues: list[str] = field(default_factory=list)   # Blocks render
    warnings: list[str] = field(default_factory=list)           # Non-blocking
    repair_instructions: list[str] = field(default_factory=list)  # For REPAIR
    regenerate_reason: str = ""      # For REJECT

    @property
    def is_acceptable(self) -> bool:
        """Can proceed to render (accept or max iterations reached)."""
        return self.verdict in (JudgeVerdict.ACCEPT,)


# ── System prompt ────────────────────────────────────────────────────────────

JUDGE_SYSTEM_PROMPT = """You are the Judge of AI Court — a strict code reviewer for Manim Community animations.

Your role: review generated Manim Python code BEFORE it gets rendered on a constrained machine (Intel i5-1155G7, 8GB RAM, Intel Iris Xe GPU).

You are NOT the code generator. You are the adversary — your job is to find real bugs, anti-patterns, and performance issues that the generator missed.

BE STRICT. It is better to flag 10 false positives than miss 1 real bug.

## Analysis categories (review all 8):

1. 🐛 Bugs — NameError, missing imports, syntax errors, broken method calls
2. 🏗 Structure — missing class GenScene(Scene), missing construct(self), wrong base class
3. 🎬 Animation logic — self.play with wrong objects, broken TrackedPath, wrong method names
4. 💥 Performance — Surface/ParametricSurface (KILLER on 8GB), >2 updaters, >15 self.play, 60fps, large particle counts (>25), always_redraw abuse
5. 📐 Layout — objects on top of each other, VGroup without arrange(), multiple .move_to(ORIGIN), no buff between elements
6. 📖 Readability — text without font_size (unreadable), terrible color choices, cluttered scene
7. 🎓 Education — mathematically incorrect formulas, misrepresented concepts
8. 🧹 Code quality — hardcoded magic numbers, duplicated code, dead code, unused variables

## Hardware constraints (i5-1155G7 / 8GB RAM):
- Surface/ParametricSurface = VERY HEAVY — flag as critical
- >2 always_redraw/add_updater = HEAVY — flag as warning
- >15 self.play calls = scene too long — flag as warning
- >25 background particles = heavy — flag as warning
- font_size not set on Text/MathTex = unreadable — flag as critical for readability
- VGroup without .arrange() = objects may overlap — flag as critical

## Verdicts:

✅ ACCEPT (score >= 7.0, no critical issues)
   — Code is safe to render. Minor warnings are OK.

🔧 REPAIR (score 4.0–6.9, or 1-3 critical but fixable issues)
   — Specific line-by-line fixes needed. Return exact repair instructions.

❌ REJECT (score < 4.0, or fundamental structural problems)
   — Code is beyond repair. Regenerate from scratch with different approach.

## Output format:
Return ONLY valid JSON, no markdown fences:
{
  "verdict": "ACCEPT" | "REPAIR" | "REJECT",
  "score": N.N,
  "critical_issues": ["issue1 with line reference", "issue2"],
  "warnings": ["warning1", "warning2"],
  "repair_instructions": ["Line N: do X instead of Y", "Line M: add Z"],
  "regenerate_reason": "why REJECT if applicable, empty otherwise"
}

Be specific. "Line N" references are highly valued. Vague complaints are ignored.
"""


# ── Judge function ───────────────────────────────────────────────────────────

async def judge_code(
    manim_code: str,
    original_prompt: str,
    critic_review: CriticReview | None = None,
    static_issues: list[str] | None = None,
    iteration: int = 1,
) -> JudgeReview:
    """Review Manim code with Judge of AI Court.

    Args:
        maniam_code: The generated Manim Python code.
        original_prompt: User's original animation request.
        critic_review: Optional existing critic review for context.
        static_issues: Optional list of static check issues.
        iteration: Current iteration number (1 or 2).

    Returns:
        JudgeReview with verdict and issues.
    """
    try:
        # Truncate very long code to stay within token limits
        code_snippet = manim_code[:6000] if len(manim_code) > 6000 else manim_code

        # Build context with critic and static issues
        context_parts = [f"Critique this Manim code for prompt: {original_prompt}"]

        if static_issues:
            context_parts.append(f"Static analysis found {len(static_issues)} issues:\n" + "\n".join(f"- {i}" for i in static_issues))

        if critic_review:
            context_parts.append(
                f"Critic Agent scored it {critic_review.overall:.1f}/10 with {len(critic_review.issues)} issues:\n"
                + "\n".join(f"- {i}" for i in critic_review.issues)
            )

        if iteration > 1:
            context_parts.append(f"This is iteration {iteration}/{JUDGE_MAX_ITERATIONS} — be extra strict.")

        context_parts.append(f"\n```python\n{code_snippet}\n```")

        user_message = "\n\n".join(context_parts)

        response = await judge_client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,  # Judge should be deterministic
            max_tokens=2048,
            timeout=JUDGE_TIMEOUT,
        )

        content = (response.choices[0].message.content or "").strip()
        # Strip markdown fences if present
        content = re.sub(r"^```[a-z]*\n?", "", content, flags=re.MULTILINE)
        content = re.sub(r"\n?```$", "", content, flags=re.MULTILINE)

        result = json.loads(content)

        verdict_str = result.get("verdict", "ACCEPT").upper()
        try:
            verdict = JudgeVerdict(verdict_str)
        except ValueError:
            logger.warning(f"Unknown verdict '{verdict_str}', defaulting to ACCEPT")
            verdict = JudgeVerdict.ACCEPT

        review = JudgeReview(
            verdict=verdict,
            score=float(result.get("score", 5.0)),
            critical_issues=result.get("critical_issues", []),
            warnings=result.get("warnings", []),
            repair_instructions=result.get("repair_instructions", []),
            regenerate_reason=result.get("regenerate_reason", ""),
        )

        logger.info(
            f"Judge verdict: {verdict.value}, score={review.score:.1f}, "
            f"critical={len(review.critical_issues)}, "
            f"warnings={len(review.warnings)}, "
            f"iteration={iteration}"
        )
        if review.critical_issues:
            logger.info(f"  Critical: {review.critical_issues[0]}")

        return review

    except Exception as e:
        logger.warning(f"Judge review failed (non-fatal, proceeding): {e}")
        # Return neutral review — don't block render on judge failure
        return JudgeReview(
            verdict=JudgeVerdict.ACCEPT,
            score=5.0,
            critical_issues=[],
            warnings=[],
            repair_instructions=[],
            regenerate_reason=f"Judge failed: {e}",
        )


# ── Repair code using Judge instructions ─────────────────────────────────────

async def repair_by_judge(
    manim_code: str,
    original_prompt: str,
    judge_review: JudgeReview,
    theme_instructions: str = "",
) -> str:
    """Ask the generator to fix code based on Judge's instructions.

    Uses the existing GPT coding client but with Judge's specific feedback.
    """
    # Late import to avoid circular dependency
    import importlib

    llm_mod = importlib.import_module("llm")
    gpt_coding_client = llm_mod.gpt_coding_client
    GPT_MODEL = llm_mod.GPT_MODEL
    strip_code_fences = llm_mod.strip_code_fences

    try:
        _build_extra_body = llm_mod._build_extra_body
    except AttributeError:
        _build_extra_body = lambda: {}  # noqa: E731

    repair_text = "\n".join(f"- {instruction}" for instruction in judge_review.repair_instructions)

    messages = [
        {
            "role": "system",
            "content": (
                f"Fix ONLY the issues identified by the Judge of AI Court. "
                f"Do NOT change the creative metaphor or animation concept. "
                f"Only fix:\n{repair_text}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Original request: {original_prompt}\n\n"
                f"Current code:\n```python\n{manim_code[:4000]}\n```\n\n"
                f"Judge found {len(judge_review.critical_issues)} critical issues:\n"
                + "\n".join(f"- {i}" for i in judge_review.critical_issues)
            ),
        },
    ]

    kwargs = {
        "model": GPT_MODEL,
        "messages": messages,
        "max_tokens": 8192,
        "timeout": 180,
    }
    extra = _build_extra_body()
    if extra:
        kwargs["extra_body"] = extra

    response = await gpt_coding_client.chat.completions.create(**kwargs)
    code = strip_code_fences(response.choices[0].message.content or "")
    logger.info(f"Code repaired by generator ({len(judge_review.repair_instructions)} fixes applied)")
    return code
