"""Multi-Agent Debate — two code generators compete, critic chooses the best.

Two LLM instances independently generate Manim code for the same prompt.
A critic agent scores both and selects the winner.
This produces higher-quality code at the cost of 2× LLM calls.
"""

from __future__ import annotations

import asyncio
import logging

from config import GPT_MODEL
from critic_agent import critique_code
from common import extract_python_code
from llm import gpt_coding_client

logger = logging.getLogger(__name__)

DEBATE_SYSTEM_PROMPT = """You are an independent Manim code generator. Generate clean, correct code.

Follow all Manim best practices:
- Use GenScene class with construct method
- 12-25 second duration
- Clean color palette
- Explicit font sizes
- No heavy operations (Surface, >3 updaters)
"""


async def generate_debate_entry(prompt: str, theme_instructions: str, client_id: int) -> str:
    """Generate code from one agent in the debate."""
    try:
        # Use different temperatures for diversity
        temp = 0.7 if client_id == 0 else 0.9

        response = await gpt_coding_client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": DEBATE_SYSTEM_PROMPT + "\n\n" + theme_instructions},
                {"role": "user", "content": prompt},
            ],
            max_tokens=8192,
            temperature=temp,
            timeout=180,
            extra_body={"enable_thinking": False},
        )
        code = extract_python_code(response.choices[0].message.content or "")
        logger.info(f"Debate agent {client_id} generated {len(code)} chars")
        return code
    except Exception as e:
        logger.error(f"Debate agent {client_id} failed: {e}")
        return ""


async def debate_generate(prompt: str, theme_instructions: str) -> tuple[str, dict]:
    """Run a multi-agent debate: two generators → critic picks winner.

    Returns:
        (winning_code, scores_dict)
    """
    # Generate two independent solutions
    results = await asyncio.gather(
        generate_debate_entry(prompt, theme_instructions, 0),
        generate_debate_entry(prompt, theme_instructions, 1),
        return_exceptions=True,
    )
    code_a = results[0] if not isinstance(results[0], Exception) else ""
    code_b = results[1] if not isinstance(results[1], Exception) else ""

    if not code_a and not code_b:
        logger.warning("Both debate agents failed, returning empty")
        return "", {}

    # If only one succeeded, return it
    if not code_a:
        return code_b, {"agent_b": "winner_by_default"}
    if not code_b:
        return code_a, {"agent_a": "winner_by_default"}

    # Critic scores both
    review_a = await critique_code(code_a, prompt)
    review_b = await critique_code(code_b, prompt)

    logger.info(f"Debate scores: Agent A = {review_a.overall:.1f}, Agent B = {review_b.overall:.1f}")

    if review_a.overall >= review_b.overall:
        return code_a, {
            "agent_a": review_a.overall,
            "agent_b": review_b.overall,
            "winner": "A",
            "reason": f"Score {review_a.overall:.1f} vs {review_b.overall:.1f}",
        }
    else:
        return code_b, {
            "agent_a": review_a.overall,
            "agent_b": review_b.overall,
            "winner": "B",
            "reason": f"Score {review_b.overall:.1f} vs {review_a.overall:.1f}",
        }
