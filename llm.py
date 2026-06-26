"""LLM integration: GPT-5.5 for Manim code generation,
Qwen 3.6 Plus or Claude Opus 4.8 for chat, vision, and self-healing."""

import base64
import logging
import re

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from config import (
    DASHSCOPE_API_KEY,
    CHAT_MODEL,
    GPT_MODEL,
    GPT_BASE_URL,
    GPT_API_KEY,
    IMAGE_MODEL,
    GPT_REASONING_EFFORT,
    CLAUDE_BASE_URL,
    CLAUDE_API_KEY,
    CLAUDE_MODEL,
    LLM_PROVIDER,
)
from prompt_builder import (
    build_manim_fix_prompt,
    build_manim_system_prompt,
    build_scene_plan_prompt,
    build_layout_repair_prompt,
)

logger = logging.getLogger(__name__)

# Runtime-overridable provider (default from .env)
_active_provider = LLM_PROVIDER

# Qwen 3.7 Max client for Manim code generation
gpt_coding_client = AsyncOpenAI(
    api_key=GPT_API_KEY,
    base_url=GPT_BASE_URL,
    timeout=600,  # 10 min — Qwen 3.7 Max with long system prompts is slow
    max_retries=0,
)

# Qwen 3.6 Plus client for chat responses + vision
qwen_client = AsyncOpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=LLM_BASE_URL,
    timeout=120,
)

# Claude Opus 4.8 client for chat responses + vision (Anthropic API)
claude_client = AsyncAnthropic(
    api_key=CLAUDE_API_KEY,
    base_url=CLAUDE_BASE_URL,
    timeout=120,
)


def _strip_code_fences(code: str) -> str:
    """Strip markdown fences if the model wraps code in them."""
    code = re.sub(r"^```\w*\n?", "", code.strip())
    code = re.sub(r"\n?```$", "", code.strip())
    return code


def get_provider() -> str:
    """Return current LLM provider name."""
    return _active_provider


def set_provider(provider: str) -> None:
    """Set LLM provider at runtime (for /provider command)."""
    global _active_provider
    _active_provider = provider


# ── Manim code generation (Qwen 3.7 Max) ──────────────────────────────────────

async def generate_manim_code(prompt: str, theme_instructions: str = "", scene_plan: str = "") -> str:
    """Ask Qwen 3.7 Max to generate Manim animation code from a text description."""
    try:
        response = await gpt_coding_client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": build_manim_system_prompt(theme_instructions, prompt, scene_plan=scene_plan)},
                {"role": "user", "content": prompt},
            ],
            max_tokens=8192,
            timeout=300,
        )
        return _strip_code_fences(response.choices[0].message.content or "")
    except Exception as e:
        logger.error(f"GPT code generation error: {e}")
        raise


async def fix_manim_code(original_prompt: str, error: str, theme_instructions: str = "") -> str:
    """Ask Qwen 3.7 Max to fix broken Manim code given the compilation error."""
    try:
        response = await gpt_coding_client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": build_manim_fix_prompt(error, theme_instructions, original_prompt)},
                {"role": "user", "content": f"Original request: {original_prompt}"},
            ],
            max_tokens=8192,
        )
        return _strip_code_fences(response.choices[0].message.content or "")
    except Exception as e:
        logger.error(f"GPT self-heal error: {e}")
        raise


# ── Scene planning & layout repair ───────────────────────────────────────

async def generate_scene_plan(prompt: str) -> str:
    """Ask Qwen 3.7 Max to produce a JSON scene composition plan (objects, timeline, layout).

    This runs BEFORE code generation and constrains spatial layout without
    dictating the creative metaphor.
    """
    try:
        response = await gpt_coding_client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": build_scene_plan_prompt()},
                {"role": "user", "content": f"Plan the scene composition for: {prompt}"},
            ],
            max_tokens=2048,
            timeout=120,
            extra_body={"enable_thinking": False},  # Qwen thinking control
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.error(f"Scene plan generation error: {e}")
        raise


async def repair_layout(
    code: str,
    issues: list[str],
    theme_instructions: str = "",
    original_prompt: str = "",
) -> str:
    """Ask Qwen 3.7 Max to fix ONLY spatial/timing layout issues, preserving the creative metaphor."""
    issues_text = "\n".join(f"- {issue}" for issue in issues)
    try:
        response = await gpt_coding_client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": build_layout_repair_prompt(issues_text, theme_instructions, original_prompt),
                },
                {
                    "role": "user",
                    "content": f"Fix the layout issues in this Manim code:\n\n{code}",
                },
            ],
            max_tokens=8192,
            timeout=300,
        )
        return _strip_code_fences(response.choices[0].message.content or "")
    except Exception as e:
        logger.error(f"Layout repair error: {e}")
        raise


# ── Intent classification ─────────────────────────────────────────────────

async def classify_intent(prompt: str, provider: str | None = None) -> str:
    """Classify user intent: ANIMATE or CHAT — routed by provider (per-user or global)."""
    active = provider or _active_provider
    if active == "claude":
        return await _classify_intent_claude(prompt)
    return await _classify_intent_qwen(prompt)


async def _classify_intent_qwen(prompt: str) -> str:
    """Ask Qwen 3.6 Plus to classify user intent: ANIMATE or CHAT."""
    try:
        response = await qwen_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        'Classify the user message as either "ANIMATE" or "CHAT". '
                        "Reply with ONLY one word. "
                        "ANIMATE = wants a Manim animation/visualization/drawing. "
                        "CHAT = general conversation, question, or explanation."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=10,
            extra_body={"enable_thinking": False},
        )
        result = (response.choices[0].message.content or "").strip().upper()
        if "ANIM" in result:
            return "ANIMATE"
        return "CHAT"
    except Exception as e:
        logger.error(f"Qwen intent classification error: {e}")
        return "CHAT"


async def _classify_intent_claude(prompt: str) -> str:
    """Ask Claude Opus 4.8 to classify user intent: ANIMATE or CHAT."""
    try:
        response = await claude_client.messages.create(
            model=CLAUDE_MODEL,
            system=(
                'Classify the user message as either "ANIMATE" or "CHAT". '
                "Reply with ONLY one word. "
                "ANIMATE = wants a Manim animation/visualization/drawing. "
                "CHAT = general conversation, question, or explanation."
            ),
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10,
        )
        result = (response.content[0].text or "").strip().upper()
        if "ANIM" in result:
            return "ANIMATE"
        return "CHAT"
    except Exception as e:
        logger.error(f"Claude intent classification error: {e}")
        return "CHAT"


# ── Chat ──────────────────────────────────────────────────────────────────

async def chat(messages: list[dict], provider: str | None = None) -> str:
    """Chat — routed by provider (per-user or global)."""
    active = provider or _active_provider
    if active == "claude":
        return await _chat_claude(messages)
    return await _chat_qwen(messages)


async def _chat_qwen(messages: list[dict]) -> str:
    """Chat with Qwen 3.6 Plus — used for general conversation."""
    try:
        response = await qwen_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=2048,
            extra_body={"enable_thinking": False},
        )
        message = response.choices[0].message
        return (
            getattr(message, "content", None)
            or getattr(message, "reasoning_content", None)
            or "_(No response)_"
        )
    except Exception as e:
        logger.error(f"Qwen chat error: {e}")
        return f"⚠️ Chat temporarily unavailable: {e}"


async def _chat_claude(messages: list[dict]) -> str:
    """Chat with Claude Opus 4.8 — used for general conversation."""
    try:
        # Extract system message and convert OpenAI format to Anthropic
        system_msg = ""
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                anthropic_messages.append(msg)

        response = await claude_client.messages.create(
            model=CLAUDE_MODEL,
            system=system_msg,
            messages=anthropic_messages,
            temperature=0.7,
            max_tokens=2048,
        )
        return response.content[0].text or "_(No response)_"
    except Exception as e:
        logger.error(f"Claude chat error: {e}")
        return f"⚠️ Chat temporarily unavailable: {e}"


# ── Vision ────────────────────────────────────────────────────────────────

async def chat_with_image(image_bytes: bytes, caption: str, provider: str | None = None) -> str:
    """Vision — routed by provider (per-user or global)."""
    active = provider or _active_provider
    if active == "claude":
        return await _chat_with_image_claude(image_bytes, caption)
    return await _chat_with_image_qwen(image_bytes, caption)


async def _chat_with_image_qwen(image_bytes: bytes, caption: str) -> str:
    """Send image + text to Qwen 3.6 Plus vision endpoint."""
    b64 = base64.b64encode(image_bytes).decode()
    text = caption or "Describe this image in detail."

    try:
        response = await qwen_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                    {"type": "text", "text": text},
                ],
            }],
            max_tokens=2048,
            extra_body={"enable_thinking": False},
        )
        content = getattr(response.choices[0].message, "content", None) or ""
        content = re.sub(r"", "", content, flags=re.DOTALL).strip()
        return content or "_(empty response)_"
    except Exception as e:
        logger.error(f"Qwen vision error: {e}")
        return f"🖼️ Vision temporarily unavailable: {e}"


async def _chat_with_image_claude(image_bytes: bytes, caption: str) -> str:
    """Send image + text to Claude Opus 4.8 vision endpoint."""
    b64 = base64.b64encode(image_bytes).decode()
    text = caption or "Describe this image in detail."

    try:
        media_type = "image/jpeg"  # default for screenshots

        response = await claude_client.messages.create(
            model=CLAUDE_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": text},
                ],
            }],
            max_tokens=2048,
        )
        return response.content[0].text or "_(empty response)_"
    except Exception as e:
        logger.error(f"Claude vision error: {e}")
        return f"🖼️ Vision temporarily unavailable: {e}"
