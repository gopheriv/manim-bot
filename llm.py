"""LLM integration: GPT-5.5 for Manim code generation,
Qwen 3.6 Plus or Claude Opus 4.8 for chat, vision, and self-healing."""

import base64
import logging
import re
from typing import Any

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from common import parse_llm_json
from config import (
    DASHSCOPE_API_KEY,
    CHAT_MODEL,
    LLM_BASE_URL,
    GPT_MODEL,
    GPT_BASE_URL,
    GPT_API_KEY,
    CLAUDE_BASE_URL,
    CLAUDE_API_KEY,
    CLAUDE_MODEL,
    GLM_BASE_URL,
    GLM_API_KEY,
    GLM_MODEL,
    LLM_PROVIDER,
    MANIM_MAX_OUTPUT_TOKENS,
    MANIM_ENABLE_THINKING,
)
from prompt_builder import (
    build_manim_fix_prompt,
    build_manim_system_prompt,
    build_scene_plan_prompt,
    build_layout_repair_prompt,
)
from storyboard import build_storyboard_prompt

logger = logging.getLogger(__name__)

# Runtime-overridable provider (default from .env)
_active_provider = LLM_PROVIDER

# Qwen 3.7 Max client for Manim code generation (DashScope)
gpt_coding_client = AsyncOpenAI(
    api_key=GPT_API_KEY,
    base_url=GPT_BASE_URL,
    timeout=300,  # 5 min — Qwen 3.7 Max can be slow
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

# GLM-5.2 client (Baishan EdgeFN, Anthropic Messages format)
glm_client = AsyncAnthropic(
    api_key=GLM_API_KEY,
    base_url=GLM_BASE_URL,
    timeout=120,
)


def strip_code_fences(code: str) -> str:
    """Strip markdown fences if the model wraps code in them."""
    code = re.sub(r"^```\w*\n?", "", code.strip())
    code = re.sub(r"\n?```$", "", code.strip())
    return code


def get_provider() -> str:
    return _active_provider


def set_provider(provider: str) -> None:
    global _active_provider
    _active_provider = provider


def _is_qwen_provider() -> bool:
    """True when the coding client targets DashScope (Qwen), which supports enable_thinking."""
    return "dashscope" in (GPT_BASE_URL or "").lower()


def _build_extra_body(enable_thinking: bool = False) -> dict:
    """Build extra_body params — only for DashScope/Qwen. Other providers ignore this."""
    if not _is_qwen_provider():
        return {}
    return {"enable_thinking": enable_thinking}


def _qwen_kwargs(enable_thinking: bool = False) -> dict:
    """Keyword args to splat into a Qwen create() call.

    Centralizes the ``extra_body={"enable_thinking": …}`` decision so every Qwen
    call goes through one place. On a non-DashScope endpoint it contributes
    nothing (the endpoint would reject the unknown param), so callers can splat it
    unconditionally with ``**_qwen_kwargs()``.
    """
    extra = _build_extra_body(enable_thinking)
    return {"extra_body": extra} if extra else {}


def _split_system(messages: list[dict]) -> tuple[str, list[dict]]:
    """Split OpenAI-style messages into (system_prompt, non-system messages).

    Anthropic-format clients (Claude, GLM) take the system prompt as a separate
    ``system=`` argument rather than a message with role "system".
    """
    system_msg = ""
    rest: list[dict] = []
    for msg in messages:
        if msg.get("role") == "system":
            system_msg = msg["content"]
        else:
            rest.append(msg)
    return system_msg, rest


async def _codegen_stream(messages: list[dict], max_tokens: int, timeout: int, enable_thinking: bool) -> tuple[str, str]:
    """Run a streamed code-gen completion, accumulating content + reasoning.

    DashScope Qwen requires stream=True when enable_thinking is on, and emits the
    chain-of-thought in `reasoning_content` (which we discard) and the answer in
    `content` (which we keep).
    """
    stream = await gpt_coding_client.chat.completions.create(
        model=GPT_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        timeout=timeout,
        stream=True,
        **_qwen_kwargs(enable_thinking),
    )
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        if getattr(delta, "content", None):
            content_parts.append(delta.content)
        rc = getattr(delta, "reasoning_content", None)
        if rc:
            reasoning_parts.append(rc)
    return "".join(content_parts), "".join(reasoning_parts)


async def _codegen_complete(messages: list[dict], max_tokens: int | None = None, timeout: int = 180) -> str:
    """Code-generation completion with reasoning ON (safeguarded).

    With MANIM_ENABLE_THINKING, streams the answer with thinking enabled. If that
    path errors (e.g. an endpoint that rejects thinking) or returns an empty
    answer (reasoning only), it falls back to a plain non-thinking completion so
    we never ship empty code.
    """
    max_tokens = max_tokens or MANIM_MAX_OUTPUT_TOKENS

    if MANIM_ENABLE_THINKING:
        try:
            content, reasoning = await _codegen_stream(messages, max_tokens, timeout, enable_thinking=True)
            if content and content.strip():
                return content
            logger.warning(
                "Thinking code-gen returned empty content (reasoning=%d chars); "
                "falling back to non-thinking completion", len(reasoning),
            )
        except Exception as e:
            logger.warning(f"Thinking code-gen failed ({e}); falling back to non-thinking")

    response = await gpt_coding_client.chat.completions.create(
        model=GPT_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        timeout=timeout,
        **_qwen_kwargs(False),
    )
    return response.choices[0].message.content or ""


# ── Manim code generation (GPT-5.5) ─────────────────────────────────────────

async def generate_manim_code(prompt: str, theme_instructions: str = "", scene_plan: str = "", storyboard: str = "") -> str:
    """Generate Manim animation code (Qwen 3.7 Max, reasoning ON, large output)."""
    try:
        messages = [
            {"role": "system", "content": build_manim_system_prompt(theme_instructions, prompt, scene_plan=scene_plan, storyboard=storyboard)},
            {"role": "user", "content": prompt},
        ]
        content = await _codegen_complete(messages, max_tokens=MANIM_MAX_OUTPUT_TOKENS, timeout=240)
        return strip_code_fences(content)
    except Exception as e:
        logger.error(f"GPT code generation error: {e}")
        raise


async def fix_manim_code(original_prompt: str, error: str, theme_instructions: str = "", original_code: str = "") -> str:
    """Fix broken Manim code (Qwen 3.7 Max, reasoning ON, large output)."""
    try:
        # Send the full failing code (generous guard) — truncating to 4000 chars
        # hid the actual broken line for any non-trivial scene, so the fix model
        # was guessing. The output ceiling (MANIM_MAX_OUTPUT_TOKENS) is large.
        code_context = f"\n\nBroken code:\n```python\n{original_code[:12000]}\n```" if original_code else ""
        messages = [
            {"role": "system", "content": build_manim_fix_prompt(error, theme_instructions, original_prompt)},
            {"role": "user", "content": f"Original request: {original_prompt}{code_context}\n\nFix the error: {error}"},
        ]
        content = await _codegen_complete(messages, max_tokens=MANIM_MAX_OUTPUT_TOKENS, timeout=240)
        return strip_code_fences(content)
    except Exception as e:
        logger.error(f"GPT self-heal error: {e}")
        raise


async def complete_manim_code(
    partial_code: str,
    original_prompt: str,
    theme_instructions: str = "",
    scene_plan: str = "",
    storyboard: str = "",
) -> str:
    """Finish code that was cut off by the token limit (truncation, not a bug).

    The model is given the partial output and asked to return the COMPLETE script
    — keeping everything already written verbatim and only continuing from the cut
    point. Much cheaper and more faithful than regenerating from scratch (which
    discards correct work and often re-truncates). Uses the same large output
    ceiling so the completed code has room to finish.
    """
    try:
        system = build_manim_system_prompt(
            theme_instructions, original_prompt, scene_plan=scene_plan, storyboard=storyboard,
        )
        system += (
            "\n\n## COMPLETION MODE (CRITICAL)\n"
            "The Python code below was CUT OFF by a length limit — it is INCOMPLETE, "
            "not wrong. Return the FULL corrected script: keep everything already "
            "written EXACTLY as-is (same objects, layout, colors, timing) and simply "
            "continue from where it stops, closing every open block/animation and "
            "finishing the scene. Do NOT redesign, do NOT start over, do NOT shorten "
            "what is already there. Output ONLY the complete Python code."
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": (
                f"Original request: {original_prompt}\n\n"
                f"Incomplete code (continue & complete it):\n```python\n{partial_code}\n```"
            )},
        ]
        content = await _codegen_complete(messages, max_tokens=MANIM_MAX_OUTPUT_TOKENS, timeout=240)
        return strip_code_fences(content)
    except Exception as e:
        logger.error(f"GPT completion error: {e}")
        raise


async def edit_manim_code(
    prev_code: str,
    edit_instruction: str,
    theme_instructions: str = "",
    original_prompt: str = "",
) -> str:
    """Apply a user's edit to existing code, preserving everything else.

    This is the difference between "make it slower" producing a *slowed version of
    the animation the user liked" vs. an unrelated new render. The previous code is
    the base; only the requested change is applied.
    """
    system = (
        "You are editing an existing Manim Community Edition animation. Apply ONLY the "
        "requested change and keep everything else exactly as it is — same concept, "
        "objects, composition, colors and timing except where the change requires "
        "otherwise. Keep the class named GenScene with a construct method. "
        "Output ONLY the complete updated Python code — no explanation, no markdown fences."
    )
    if theme_instructions:
        system += "\n\n" + theme_instructions
    try:
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"Original request: {original_prompt}\n\n"
                    f"Requested change: {edit_instruction}\n\n"
                    f"Current code:\n```python\n{prev_code}\n```"
                ),
            },
        ]
        content = await _codegen_complete(messages, max_tokens=MANIM_MAX_OUTPUT_TOKENS, timeout=240)
        return strip_code_fences(content)
    except Exception as e:
        logger.error(f"Edit-by-diff error: {e}")
        raise


async def repair_targeted(
    code: str,
    issues: list[str],
    original_prompt: str,
    theme_instructions: str = "",
    focus: str = "quality and correctness",
) -> str:
    """Fix ONLY the listed reviewer issues, preserving the creative concept.

    Used to turn pre-render review findings (education accuracy, critic issues)
    into actual code changes instead of merely logging them.
    """
    issues_text = "\n".join(f"- {i}" for i in issues)
    system = (
        "You are a Manim Community Edition code fixer. Fix ONLY the issues listed below, "
        f"focusing on {focus}. Preserve the visual concept, colors, composition, and timing. "
        "Do not add or remove unrelated elements, and keep the same GenScene structure. "
        "Output ONLY the corrected Python code — no explanation, no markdown fences.\n\n"
        f"## Issues to fix\n{issues_text}"
    )
    if theme_instructions:
        system += "\n\n" + theme_instructions
    try:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Original request: {original_prompt}\n\nCode to fix:\n```python\n{code}\n```"},
        ]
        content = await _codegen_complete(messages, max_tokens=MANIM_MAX_OUTPUT_TOKENS, timeout=180)
        return strip_code_fences(content)
    except Exception as e:
        logger.error(f"Targeted repair error: {e}")
        return code  # non-fatal: keep original on failure


# ── Scene planning & layout repair ───────────────────────────────────────────

async def generate_scene_plan(prompt: str) -> str:
    """Generate a JSON scene composition plan with GPT-5.5 (fast, low tokens)."""
    try:
        kwargs: dict[str, Any] = {
            "model": GPT_MODEL,
            "messages": [
                {"role": "system", "content": build_scene_plan_prompt()},
                {"role": "user", "content": f"Plan the scene composition for: {prompt}"},
            ],
            "max_tokens": 1024,
            "timeout": 60,
        }
        extra = _build_extra_body()
        if extra:
            kwargs["extra_body"] = extra

        response = await gpt_coding_client.chat.completions.create(**kwargs)
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.error(f"Scene plan generation error: {e}")
        raise


async def generate_storyboard(
    prompt: str,
    lessons: list[str] | None = None,
    hard_constraints: list[str] | None = None,
    depth: str = "standard",
) -> str:
    """Generate a cinematography storyboard (JSON IR) for a request.

    Uses the reasoning-on code-gen path: temporal/spatial/narrative planning is
    exactly where chain-of-thought helps. Returns raw JSON text (caller parses).
    ``depth`` ('compact'|'standard'|'deep') sets the length/coverage bands.
    Recurring Judge lessons (and hard constraints) are injected into the director
    system prompt so defects are designed out at the planning stage.
    """
    try:
        messages = [
            {"role": "system", "content": build_storyboard_prompt(lessons, hard_constraints, depth=depth)},
            {"role": "user", "content": f"Storyboard this animation request: {prompt}"},
        ]
        # Reuse the thinking-on completion (with non-thinking fallback) — the
        # output is JSON, but the planning benefits from reasoning. A deep
        # storyboard (key_points + more beats + richer narration) is longer, so
        # give it more headroom.
        content = await _codegen_complete(messages, max_tokens=8192, timeout=180)
        return (content or "").strip()
    except Exception as e:
        logger.error(f"Storyboard generation error: {e}")
        raise


async def repair_layout(
    code: str,
    issues: list[str],
    theme_instructions: str = "",
    original_prompt: str = "",
) -> str:
    """Fix ONLY spatial/timing layout issues, preserving the creative metaphor."""
    issues_text = "\n".join(f"- {issue}" for issue in issues)
    try:
        messages = [
            {"role": "system", "content": build_layout_repair_prompt(issues_text, theme_instructions, original_prompt)},
            {"role": "user", "content": f"Fix the layout issues in this Manim code:\n\n{code}"},
        ]
        content = await _codegen_complete(messages, max_tokens=MANIM_MAX_OUTPUT_TOKENS, timeout=180)
        return strip_code_fences(content)
    except Exception as e:
        logger.error(f"Layout repair error: {e}")
        raise


# ── Intent classification ─────────────────────────────────────────────────────

async def classify_intent(prompt: str, provider: str | None = None) -> str:
    """Classify user intent: ANIMATE or CHAT."""
    active = provider or _active_provider
    if active == "claude":
        return await _classify_intent_claude(prompt)
    if active == "glm":
        return await _classify_intent_glm(prompt)
    return await _classify_intent_qwen(prompt)


async def _classify_intent_qwen(prompt: str) -> str:
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
            **_qwen_kwargs(),
        )
        result = (response.choices[0].message.content or "").strip().upper()
        if "ANIM" in result:
            return "ANIMATE"
        return "CHAT"
    except Exception as e:
        logger.error(f"Qwen intent classification error: {e}")
        return "CHAT"


async def _classify_intent_claude(prompt: str) -> str:
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


async def _classify_intent_glm(prompt: str) -> str:
    try:
        response = await glm_client.messages.create(
            model=GLM_MODEL,
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
        logger.error(f"GLM intent classification error: {e}")
        return "CHAT"


# ── Chat ──────────────────────────────────────────────────────────────────────

async def chat(messages: list[dict], provider: str | None = None) -> str:
    """Chat — routed by provider."""
    active = provider or _active_provider
    if active == "claude":
        return await _chat_claude(messages)
    if active == "glm":
        return await _chat_glm(messages)
    return await _chat_qwen(messages)


async def _chat_qwen(messages: list[dict]) -> str:
    try:
        response = await qwen_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=2048,
            **_qwen_kwargs(),
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
    try:
        system_msg, anthropic_messages = _split_system(messages)

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


async def _chat_glm(messages: list[dict]) -> str:
    """Chat via GLM-5.2 (Anthropic Messages format)."""
    try:
        system_msg, anthropic_messages = _split_system(messages)

        response = await glm_client.messages.create(
            model=GLM_MODEL,
            system=system_msg,
            messages=anthropic_messages,
            temperature=0.7,
            max_tokens=2048,
        )
        return response.content[0].text or "_(No response)_"
    except Exception as e:
        logger.error(f"GLM chat error: {e}")
        return f"⚠️ Chat temporarily unavailable: {e}"


# ── Vision ────────────────────────────────────────────────────────────────────

async def chat_with_image(image_bytes: bytes, caption: str, provider: str | None = None) -> str:
    """Vision — routed by provider. GLM has no vision support — falls back to qwen."""
    active = provider or _active_provider
    if active == "claude":
        return await _chat_with_image_claude(image_bytes, caption)
    if active == "glm":
        logger.warning("GLM has no vision support — falling back to Qwen")
    return await _chat_with_image_qwen(image_bytes, caption)


async def chat_with_images(images: list[bytes], caption: str, provider: str | None = None) -> str:
    """Multi-image vision — send several frames in one message (for the visual critic).
    GLM has no vision support — falls back to qwen."""
    active = provider or _active_provider
    if active == "claude":
        return await _chat_with_images_claude(images, caption)
    if active == "glm":
        logger.warning("GLM has no vision support — falling back to Qwen for visual critic")
    return await _chat_with_images_qwen(images, caption)


async def _chat_with_images_qwen(images: list[bytes], caption: str) -> str:
    content: list[dict] = []
    for img in images:
        b64 = base64.b64encode(img).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    content.append({"type": "text", "text": caption or "Describe these frames."})
    try:
        response = await qwen_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": content}],
            max_tokens=1024,
            temperature=0.1,
            **_qwen_kwargs(),
        )
        return (getattr(response.choices[0].message, "content", None) or "").strip()
    except Exception as e:
        logger.error(f"Qwen multi-image vision error: {e}")
        return ""


async def _chat_with_images_claude(images: list[bytes], caption: str) -> str:
    content: list[dict] = []
    for img in images:
        b64 = base64.b64encode(img).decode()
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
        })
    content.append({"type": "text", "text": caption or "Describe these frames."})
    try:
        response = await claude_client.messages.create(
            model=CLAUDE_MODEL,
            messages=[{"role": "user", "content": content}],
            max_tokens=1024,
        )
        return response.content[0].text or ""
    except Exception as e:
        logger.error(f"Claude multi-image vision error: {e}")
        return ""


async def _chat_with_image_qwen(image_bytes: bytes, caption: str) -> str:
    b64 = base64.b64encode(image_bytes).decode()
    text = caption or "Describe this image in detail."
    try:
        response = await qwen_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": text},
                ],
            }],
            max_tokens=2048,
            **_qwen_kwargs(),
        )
        content = getattr(response.choices[0].message, "content", None) or ""
        return strip_code_fences(content).strip() or "_(empty response)_"
    except Exception as e:
        logger.error(f"Qwen vision error: {e}")
        return f"🖼️ Vision temporarily unavailable: {e}"


async def _chat_with_image_claude(image_bytes: bytes, caption: str) -> str:
    b64 = base64.b64encode(image_bytes).decode()
    text = caption or "Describe this image in detail."
    try:
        response = await claude_client.messages.create(
            model=CLAUDE_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
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


# NOTE: GLM-5.2 has no vision capability, so there are deliberately no GLM image
# handlers — chat_with_image[s] route the "glm" provider to the Qwen vision path.


# ── Template config filling ──────────────────────────────────────────────────

TEMPLATE_CONFIG_PROMPT = """You are a scene configuration assistant. Given a user's animation description and a template name, fill in the template parameters as JSON.

Template: {template_name}
User prompt: {prompt}

Fields (include only those that differ from the defaults):
- title: string — title of the animation
- equation: string — LaTeX equation to display (or empty)
- damping: number — damping coefficient (default 0.15)
- frequency: number — oscillation frequency (default 1.0)
- amplitude: number — amplitude (default 1.0)
- colors: array of exactly 3 hex color strings, e.g. ["#1f77b4", "#ff7f0e", "#2ca02c"]
- duration: integer — scene duration in seconds (10-20)
- extra_params: object — any additional template-specific key/value parameters

Respond with ONLY a valid JSON object (no comments, no trailing prose, no markdown fences). Example:
{{"title": "Damped Oscillator", "damping": 0.2, "colors": ["#1f77b4", "#ff7f0e", "#2ca02c"], "duration": 15}}
"""


async def fill_template_config(template_name: str, prompt: str) -> dict[str, Any]:
    """Ask LLM to fill a small JSON config for a template."""
    try:
        response = await qwen_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": "You are a JSON-only parameter filler for Manim animation templates."},
                {"role": "user", "content": TEMPLATE_CONFIG_PROMPT.format(
                    template_name=template_name, prompt=prompt
                )},
            ],
            max_tokens=512,
            timeout=30,
            **_qwen_kwargs(),
        )
        content = getattr(response.choices[0].message, "content", None) or ""
        return parse_llm_json(content) or {}
    except Exception as e:
        logger.error(f"Template config fill error: {e}")
        return {}
