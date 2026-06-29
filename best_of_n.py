"""Best-of-N tournament — sample many, keep the best (judged on real pixels).

For a stochastic generator with unlimited compute, the highest-leverage quality
move is: generate N candidates, render them, and SELECT the best by looking at
the actual rendered frames — not at the source code. This module does exactly
that and returns the winning *code*, which the main pipeline then renders at full
quality and polishes (so the winner is rendered once at draft for ranking, once
at final).

Flow:
  1. generate N candidates concurrently (each: storyboard IR → Manim code),
  2. render N drafts in parallel on the cloud farm,
  3. vision-rank the drafts on their actual frames (reusing the visual critic),
  4. return the highest-scoring candidate's code.

Every stage degrades gracefully: if drafts can't render, a generated candidate
is still returned so the main pipeline renders *something*; if nothing generates,
None is returned and the caller falls back to single-candidate generation.

The three I/O helpers are module-level so tests can monkeypatch them and exercise
the orchestration without any LLM / cloud / vision calls.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

# Imported at module scope so any import error surfaces at startup (not mid-gather,
# repeated per candidate). No cycle: only bot.py imports this module.
import cloud_render
from llm import generate_storyboard, generate_manim_code, strip_code_fences
from storyboard import parse_storyboard, format_storyboard_for_codegen
from visual_critic import critique_render

logger = logging.getLogger("best_of_n")


async def _gen_candidate(prompt: str, theme_prompt: str) -> str:
    """Generate ONE candidate: its own storyboard IR, then code (sampling = diversity)."""
    storyboard_text = ""
    try:
        sb = parse_storyboard(await generate_storyboard(prompt))
        if sb:
            storyboard_text = format_storyboard_for_codegen(sb)
    except Exception as e:  # noqa: BLE001 — storyboard is best-effort
        logger.debug("Best-of-N candidate storyboard failed (non-fatal): %s", e)
    code = await generate_manim_code(prompt, theme_instructions=theme_prompt, storyboard=storyboard_text)
    return strip_code_fences(code)


async def _render_draft(code: str, chat_id: int, idx: int, quality: str, fps: int) -> Path | None:
    """Render one candidate draft on the cloud farm. Returns the mp4 path or None."""
    dest = Path("tmp/cloud") / str(chat_id) / f"bestof_{idx}"
    return await cloud_render.cloud_render(code, quality=quality, fps=fps, dest_dir=dest)


async def _score(video: Path, prompt: str, code: str) -> float:
    """Vision-score a rendered draft on its actual frames (0-10)."""
    verdict = await critique_render(video, prompt, code)
    return float(verdict.score) if verdict else 0.0


def _is_valid_code(code: object) -> bool:
    return isinstance(code, str) and "class GenScene" in code and "def construct" in code


async def select_best_code(
    prompt: str,
    theme_prompt: str,
    n: int,
    chat_id: int,
    draft_quality: str = "-ql",
    draft_fps: int = 15,
) -> str | None:
    """Run the tournament and return the winning candidate's code (or None)."""
    n = max(2, int(n))

    # 1) Generate N candidates concurrently. Keep each candidate's ORIGINAL index
    # so draft dirs and logs stay aligned with the candidate that produced them
    # (filtering out invalid ones must not renumber the survivors).
    gen = await asyncio.gather(
        *[_gen_candidate(prompt, theme_prompt) for _ in range(n)],
        return_exceptions=True,
    )
    codes = [(i, c) for i, c in enumerate(gen) if _is_valid_code(c)]
    logger.info("Best-of-N: %d/%d candidates generated", len(codes), n)
    if not codes:
        return None

    # 2) Render drafts in parallel on the cloud farm.
    renders = await asyncio.gather(
        *[_render_draft(c, chat_id, i, draft_quality, draft_fps) for i, c in codes],
        return_exceptions=True,
    )
    pairs = [(codes[k][1], r) for k, r in enumerate(renders) if isinstance(r, Path)]
    logger.info("Best-of-N: %d/%d drafts rendered", len(pairs), len(codes))
    if not pairs:
        # Drafts all failed (e.g. cloud hiccup) — still hand back a candidate so the
        # main pipeline renders something instead of falling all the way through.
        logger.warning("Best-of-N: no drafts rendered; returning first candidate unranked")
        return codes[0][1]

    # 3) Vision-rank the drafts on their ACTUAL frames; keep the best.
    # A scoring *failure* (None) is NOT a real 0 — otherwise, if every score call
    # failed, a genuinely broken candidate would "win" by sort order. Rank only
    # successfully-scored candidates; if none scored, fall back to the first draft.
    scored: list[tuple[float, str]] = []
    for code, video in pairs:
        try:
            s = await _score(video, prompt, code)
        except Exception as e:  # noqa: BLE001 — scoring is best-effort
            logger.warning("Best-of-N: scoring failed (non-fatal): %s", e)
            continue
        scored.append((float(s), code))

    if not scored:
        logger.warning("Best-of-N: all scoring failed; returning first rendered draft unranked")
        return pairs[0][0]

    scored.sort(key=lambda x: x[0], reverse=True)
    logger.info(
        "Best-of-N: winner score=%.1f across %d ranked candidates (scores: %s)",
        scored[0][0], len(scored), ", ".join(f"{s:.1f}" for s, _ in scored),
    )
    return scored[0][1]
