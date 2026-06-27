"""Prompt Enhancer Agent — improves vague animation requests.

Takes a raw user prompt and expands it into a detailed, specific
animation description that produces higher-quality Manim code.
"""

from __future__ import annotations

import logging

from llm import qwen_client
from config import CHAT_MODEL

logger = logging.getLogger(__name__)

ENHANCE_SYSTEM_PROMPT = """You are a Prompt Enhancer for a Manim animation bot.

Your job: take a user's animation request and make it SPECIFIC, DETAILED, and ACTIONABLE.

Rules:
1. Keep the original intent — don't change what they want
2. Add missing details: what objects? what colors? what animation sequence?
3. Specify the educational flow: what concept to highlight? what should the viewer learn?
4. Suggest timing: what appears first? what transforms happen?
5. Keep it under 200 words — concise but detailed
6. Output ONLY the enhanced prompt — no explanation, no markdown

Example:
Input: "show me derivatives"
Output: "Animate the concept of derivatives step by step. Start with a curve y=x² on clean axes. Show a tangent line at x=1 in yellow. Animate the tangent point moving along the curve while the slope value updates in real-time as a large formula at the bottom: f'(x) = 2x. Use smooth color transitions: white curve, yellow tangent, teal slope display. End with the derivative function plotted alongside the original, showing how slope at each point becomes the derivative curve. Duration: 15-20 seconds."

Example:
Input: "fourier series"
Output: "Visualize how Fourier series decomposes a square wave into sine waves. Start with a square wave in white on the left. Show the first harmonic (fundamental sine wave) building up. Add the 3rd harmonic in cyan, showing how it starts sharpening the edges. Add the 5th and 7th harmonics, watching the approximation improve. Display the frequency spectrum as bars at the bottom: each bar represents one harmonic's amplitude. End with a side-by-side: original square wave vs 7-term Fourier approximation. Use smooth animations, clear labels, and a clean dark background. Duration: 18-22 seconds."
"""


async def enhance_prompt(raw_prompt: str, is_tiktok: bool = False) -> str:
    """Enhance a raw user prompt into a detailed animation specification.

    Args:
        raw_prompt: The user's original request.
        is_tiktok: If True, optimize for short-form vertical format.

    Returns:
        Enhanced prompt ready for code generation.
    """
    extra_instruction = ""
    if is_tiktok:
        extra_instruction = (
            "\nIMPORTANT: This is for TikTok (9:16 vertical, 25-30s max). "
            "Optimize for: fast hook (3s), large mobile-friendly text, "
            "simplified visuals (3-4 beats max), clear CTA at end."
        )

    try:
        response = await qwen_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": ENHANCE_SYSTEM_PROMPT + extra_instruction},
                {"role": "user", "content": f"Enhance this animation request:\n\n{raw_prompt}"},
            ],
            temperature=0.5,
            max_tokens=512,
            timeout=15,
            extra_body={"enable_thinking": False},
        )
        enhanced = (response.choices[0].message.content or "").strip()
        if enhanced and len(enhanced) > len(raw_prompt) * 0.5:
            logger.info(f"Prompt enhanced: {len(raw_prompt)} → {len(enhanced)} chars")
            return enhanced
        # If enhancement made it shorter, keep original
        logger.warning("Enhancement degraded prompt, using original")
        return raw_prompt
    except Exception as e:
        logger.warning(f"Prompt enhancement failed: {e}")
        return raw_prompt
