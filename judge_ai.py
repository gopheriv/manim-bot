"""Judge of AI Court — a STRONG, separate model that reviews generated Manim
code for *correctness only*, just before render.

Design (deliberately narrow):

  * It reviews ONLY what a second capable model can uniquely catch and that
    would make the render WRONG or BROKEN — runtime-breaking API misuse,
    undefined names, and mathematical/conceptual errors.
  * It does NOT grade layout, spacing, fonts, color, aesthetics, structure, or
    performance/heaviness. Those are handled deterministically elsewhere
    (`critic_agent.static_quality_check`, the renderer's scene-weight, the render
    tier, and the frame-based `visual_critic`). Flagging them here is a false
    positive and is explicitly forbidden in the prompt.
  * It is **fail-closed**: a transport failure does NOT become a silent ACCEPT.
    We retry once, and on total failure return an honest UNREVIEWED verdict so
    the caller can proceed-but-label rather than pretend the code passed review.
  * It is **tier-aware**: the active render tier governs heaviness, so the Judge
    never rejects a legitimately cinematic scene on a capable box.
  * It runs on the **strongest available model** (Claude when configured).
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
    JUDGE_PROVIDER,
    JUDGE_TIMEOUT,
    CLAUDE_API_KEY,
    QWEN_API_KEY,
)
from critic_agent import CriticReview

logger = logging.getLogger(__name__)

# ── OpenAI-compatible judge client (fallback path) ───────────────────────────

judge_client = AsyncOpenAI(
    api_key=JUDGE_API_KEY or "unset",
    base_url=JUDGE_BASE_URL or None,
    timeout=JUDGE_TIMEOUT,
)


def _get_qwen_extra_body() -> dict:
    """Return enable_thinking only when the judge endpoint is DashScope (Qwen)."""
    if "dashscope" in (JUDGE_BASE_URL or "").lower():
        return {"enable_thinking": False}
    return {}


# ── Verdict enum ─────────────────────────────────────────────────────────────

class JudgeVerdict(str, Enum):
    ACCEPT = "ACCEPT"          # No correctness defects — safe to render.
    REPAIR = "REPAIR"          # Fixable correctness defects — apply line fixes.
    REJECT = "REJECT"          # Cannot represent the concept correctly — regenerate.
    UNREVIEWED = "UNREVIEWED"  # Judge could not run — render but DO NOT claim it passed.


# ── Review dataclass ─────────────────────────────────────────────────────────

@dataclass
class JudgeReview:
    """Result of the Judge's correctness review."""
    verdict: JudgeVerdict
    score: float                                              # 0-10 correctness
    critical_issues: list[str] = field(default_factory=list)  # block render
    warnings: list[str] = field(default_factory=list)         # kept for caller compat
    repair_instructions: list[str] = field(default_factory=list)
    regenerate_reason: str = ""

    @property
    def is_acceptable(self) -> bool:
        """True only when the Judge actively approved. UNREVIEWED is NOT a pass."""
        return self.verdict == JudgeVerdict.ACCEPT

    @property
    def was_reviewed(self) -> bool:
        return self.verdict != JudgeVerdict.UNREVIEWED


# ── System prompt (correctness only) ─────────────────────────────────────────

def _build_system_prompt(tier_name: str, allow_heavy: bool) -> str:
    return f"""You are the Judge of AI Court — a strict CORRECTNESS reviewer for Manim Community (manim CE) Python code that is about to be rendered.

You are NOT the code generator and NOT a style critic. Other systems already handle layout, spacing, font sizes, color, aesthetics, code structure, AND performance/hardware budget. Commenting on any of those is a FALSE POSITIVE — do not do it.

Review ONLY for defects a careful second reader can catch that would make the render WRONG or BROKEN:

1. Runtime-breaking API misuse — calling Manim methods/classes that do not exist in manim CE, wrong or invalid keyword arguments, wrong argument order/types, removed numpy APIs (np.float, np.int, np.bool, np.math), or animating/Transforming mobjects that were never added or are incompatible.
2. Undefined names / use-before-assignment that a direct read of the code reveals.
3. Mathematical or conceptual errors — incorrect formulas, sign errors, wrong/mislabeled axes, or a visualization that misrepresents the concept the prompt asked for.

OUT OF SCOPE (never flag these): performance, Surface/ParametricSurface, ThreeDScene, number of updaters/self.play calls, fps, font_size, overlap/spacing, palette/contrast, magic numbers, dead code, or missing class scaffolding. The current render tier "{tier_name}" governs scene heaviness; heavy operations are {'ALLOWED' if allow_heavy else 'handled automatically by the renderer'} and must NOT be flagged here.

Verdicts:
- ACCEPT (score >= 7.0): no correctness defects. Style and heaviness are irrelevant to you.
- REPAIR (score 4.0-6.9): specific, fixable correctness defects. Give exact "Line N: do X instead of Y" instructions.
- REJECT (score < 4.0): the code cannot represent the requested concept correctly even with line-level fixes.

Return ONLY valid JSON, no markdown fences:
{{"verdict": "ACCEPT" | "REPAIR" | "REJECT", "score": N.N, "critical_issues": ["defect with line reference"], "repair_instructions": ["Line N: ..."], "regenerate_reason": "why REJECT, else empty"}}

Be specific; "Line N" references are valued. If you are unsure whether something is a real defect, do not flag it."""


# ── Model routing — strongest available judge ────────────────────────────────

def _resolve_provider() -> str | None:
    """Return 'claude', 'qwen', 'openai', or None (no judge configured)."""
    if JUDGE_PROVIDER == "claude":
        return "claude" if CLAUDE_API_KEY else None
    if JUDGE_PROVIDER == "qwen":
        return "qwen" if QWEN_API_KEY else None
    if JUDGE_PROVIDER == "openai":
        return "openai" if (JUDGE_BASE_URL and JUDGE_API_KEY) else None
    # auto: prefer the strongest model when available
    if CLAUDE_API_KEY:
        return "claude"
    if QWEN_API_KEY:
        return "qwen"
    if JUDGE_BASE_URL and JUDGE_API_KEY:
        return "openai"
    return None


async def _judge_complete(system_prompt: str, user_message: str) -> str:
    """Run one judge completion on the strongest configured model.

    Raises on failure (so the caller can fail-closed) — does NOT swallow errors
    into a passing-looking string.
    """
    provider = _resolve_provider()
    if provider == "claude":
        # Lazy import to reuse the already-constructed Anthropic client.
        from llm import claude_client
        from config import CLAUDE_MODEL
        response = await claude_client.messages.create(
            model=CLAUDE_MODEL,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            temperature=0.1,
            max_tokens=2048,
        )
        return (response.content[0].text or "").strip()

    if provider == "qwen":
        from llm import qwen_client
        qwen_extra = _get_qwen_extra_body()
        response = await qwen_client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=2048,
            timeout=JUDGE_TIMEOUT,
            **({"extra_body": qwen_extra} if qwen_extra else {}),
        )
        return (response.choices[0].message.content or "").strip()

    if provider == "openai":
        response = await judge_client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=2048,
            timeout=JUDGE_TIMEOUT,
        )
        if isinstance(response, str):
            return response.strip()
        if hasattr(response, "choices"):
            return (response.choices[0].message.content or "").strip()
        return (response.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()

    raise RuntimeError("No judge model configured (set CLAUDE_API_KEY or JUDGE_BASE_URL/JUDGE_API_KEY)")


def _parse_review(content: str) -> JudgeReview:
    """Parse the judge JSON. Unknown/garbled verdict → conservative REPAIR."""
    content = re.sub(r"^```[a-z]*\n?", "", content, flags=re.MULTILINE)
    content = re.sub(r"\n?```$", "", content, flags=re.MULTILINE)
    result = json.loads(content)

    verdict_str = str(result.get("verdict", "")).upper()
    try:
        verdict = JudgeVerdict(verdict_str)
        if verdict == JudgeVerdict.UNREVIEWED:  # never accept this from the model
            raise ValueError("model returned UNREVIEWED")
    except ValueError:
        # A gate that can't read the verdict must not wave the code through.
        logger.warning("Judge returned unknown verdict %r — treating as REPAIR", verdict_str)
        verdict = JudgeVerdict.REPAIR

    return JudgeReview(
        verdict=verdict,
        score=float(result.get("score", 5.0)),
        critical_issues=list(result.get("critical_issues", [])),
        warnings=list(result.get("warnings", [])),
        repair_instructions=list(result.get("repair_instructions", [])),
        regenerate_reason=str(result.get("regenerate_reason", "")),
    )


# ── Judge function ───────────────────────────────────────────────────────────

async def judge_code(
    manim_code: str,
    original_prompt: str,
    critic_review: CriticReview | None = None,
    static_issues: list[str] | None = None,
    iteration: int = 1,
    tier=None,
) -> JudgeReview:
    """Review Manim code for CORRECTNESS with the strongest configured model.

    Fail-closed: on total failure returns UNREVIEWED (not a fake ACCEPT).
    Tier-aware: heaviness is the render tier's job, not the Judge's.
    """
    # Resolve the active render tier for tier-aware heaviness handling.
    if tier is None:
        try:
            from render_tier import get_tier
            tier = get_tier()
        except Exception:
            tier = None
    tier_name = getattr(tier, "name", "constrained")
    allow_heavy = bool(getattr(tier, "allow_surface", False) or getattr(tier, "allow_3d", False))

    system_prompt = _build_system_prompt(tier_name, allow_heavy)

    code_snippet = manim_code[:6000]
    context_parts = [f"Review this Manim code for correctness. Animation request: {original_prompt}"]
    # Only forward correctness-relevant signals (educational issues); drop the
    # layout/performance static noise the Judge must ignore by design.
    if critic_review and getattr(critic_review, "issues", None):
        edu = [i for i in critic_review.issues if any(
            k in i.lower() for k in ("formula", "incorrect", "wrong", "math", "concept", "sign", "equation")
        )]
        if edu:
            context_parts.append("Possible correctness concerns to verify:\n" + "\n".join(f"- {i}" for i in edu))
    if iteration > 1:
        context_parts.append(f"This is iteration {iteration}/{JUDGE_MAX_ITERATIONS} — re-check that earlier fixes are correct.")
    context_parts.append(f"\n```python\n{code_snippet}\n```")
    user_message = "\n\n".join(context_parts)

    last_err: Exception | None = None
    for attempt in (1, 2):  # retry once on transient failure
        try:
            content = await _judge_complete(system_prompt, user_message)
            review = _parse_review(content)
            logger.info(
                "Judge verdict: %s, score=%.1f, critical=%d, tier=%s, iteration=%d",
                review.verdict.value, review.score, len(review.critical_issues), tier_name, iteration,
            )
            if review.critical_issues:
                logger.info("  Critical: %s", review.critical_issues[0])
            return review
        except Exception as e:  # noqa: BLE001 — judge is best-effort transport
            last_err = e
            logger.warning("Judge attempt %d failed: %s", attempt, e)

    # Fail-CLOSED: do not pretend this was reviewed.
    logger.error("Judge unavailable after retry — returning UNREVIEWED (render proceeds, unendorsed): %s", last_err)
    return JudgeReview(
        verdict=JudgeVerdict.UNREVIEWED,
        score=0.0,
        regenerate_reason=f"Judge unavailable: {last_err}",
    )


# ── Repair code using Judge instructions ─────────────────────────────────────

async def repair_by_judge(
    manim_code: str,
    original_prompt: str,
    judge_review: JudgeReview,
    theme_instructions: str = "",
) -> str:
    """Ask the generator to fix ONLY the correctness defects the Judge found."""
    import importlib

    llm_mod = importlib.import_module("llm")
    strip_code_fences = llm_mod.strip_code_fences

    repair_text = "\n".join(f"- {i}" for i in judge_review.repair_instructions) or "\n".join(
        f"- {i}" for i in judge_review.critical_issues
    )

    messages = [
        {
            "role": "system",
            "content": (
                "Fix ONLY the correctness issues identified by the Judge of AI Court. "
                "Do NOT change the creative metaphor, animation concept, layout, or styling. "
                f"Only fix:\n{repair_text}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Original request: {original_prompt}\n\n"
                f"Current code:\n```python\n{manim_code[:4000]}\n```\n\n"
                f"Judge found {len(judge_review.critical_issues)} correctness issue(s):\n"
                + "\n".join(f"- {i}" for i in judge_review.critical_issues)
            ),
        },
    ]

    content = await llm_mod._codegen_complete(messages, timeout=180)
    code = strip_code_fences(content)
    logger.info("Code repaired by generator (%d Judge fixes)", len(judge_review.repair_instructions))
    return code
