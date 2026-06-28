"""Manim Animation Bot — Telegram bot with GPT-5.5 code gen, Qwen 3.6 chat,
edge-tts voiceover, themes, queue management, rate limiting, and D1 caching."""

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import psutil

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

import d1
from analytics import analytics
from config import (
    BOT_TOKEN,
    CHAT_MODEL,
    GPT_MODEL,
    GPT_REASONING_EFFORT,
    GPT_MAX_RETRIES,
    D1_ENABLED,
    VOICEOVER_ENABLED,
    TTS_VOICE,
    TTS_RATE,
    MANIM_QUALITY,
    MANIM_TIMEOUT,
    MANIM_MAX_RETRIES,
    REVIEW_REPAIR_ENABLED,
    CRITIC_REPAIR_THRESHOLD,
    VISUAL_CRITIC_ENABLED,
    VISUAL_CRITIC_MAX_PASSES,
)
from database import db
from fallback_scene import build_fallback_scene
from llm import classify_intent, chat, chat_with_image, generate_manim_code, fix_manim_code, generate_scene_plan, repair_layout, repair_targeted, edit_manim_code, strip_code_fences, fill_template_config
from scene_planner import parse_scene_plan, format_plan_for_prompt
from scene_validator import validate_layout, has_issues
from markdown_utils import strip_markdown
from queue_manager import render_queue, TaskStatus
from rate_limiter import rate_limiter
from renderer import render, cleanup, get_last_generated_code, classify_render_error
from render_tier import get_tier
import settings as user_settings
from themes import get_theme, next_theme, build_theme_prompt, THEME_ORDER
from voiceover import add_voiceover
from templates import get_registry
from tiktok_integration import detect_tiktok_mode
from prompt_builder_tiktok import get_tiktok_prompt
from feedback import log_feedback
from watermark import add_watermark
from prompt_enhancer import enhance_prompt
from critic_agent import critique_code, static_quality_check
from judge_ai import judge_code, repair_by_judge, JudgeVerdict, JudgeReview
from error_learner import log_error, get_adaptive_prompt_modifiers
from edu_reviewer import review_education
from course_generator import generate_course
from exam_prep import get_question_bank, get_random_question, generate_animation_for_question
from gallery import GALLERY_CATALOG, get_featured, get_by_category, get_by_id, search as gallery_search, increment_view, increment_render
from multi_agent_debate import debate_generate
from visual_critic import critique_render
from referral import register_user, get_user_referral_info, get_referral_stats, use_bonus_render
from teacher_dashboard import register_teacher, get_teacher_dashboard, get_engagement_stats

# Ensure log directory exists before configuring handlers
from pathlib import Path
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler("logs/manim-bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("bot")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---------------------------------------------------------------------------
# Telegram Markdown safety
# ---------------------------------------------------------------------------

async def _safe_reply(message: types.Message, text: str, **kwargs) -> None:
    """Send a text reply with Markdown safety — falls back to plain text on parse errors."""
    try:
        await message.reply(text, parse_mode=ParseMode.MARKDOWN, **kwargs)
    except TelegramBadRequest:
        plain = strip_markdown(text)
        try:
            await message.reply(plain, **kwargs)
        except TelegramBadRequest as e:
            logger.error(f"Safe reply fallback failed: {e}")
            await message.reply(plain[:4000])


async def _safe_answer(message: types.Message, text: str, **kwargs) -> None:
    """Same as _safe_reply but uses answer instead of reply."""
    try:
        await message.answer(text, parse_mode=ParseMode.MARKDOWN, **kwargs)
    except TelegramBadRequest:
        plain = strip_markdown(text)
        try:
            await message.answer(plain, **kwargs)
        except TelegramBadRequest as e:
            logger.error(f"Safe answer fallback failed: {e}")
            await message.answer(plain[:4000])


async def _cancel_task(task: asyncio.Task) -> None:
    """Cancel an asyncio task and properly await its completion."""
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def _safe_edit(message: types.Message, text: str, **kwargs) -> None:
    """Edit a message with Markdown safety — falls back to plain text on parse errors."""
    try:
        await message.edit_text(text, parse_mode=ParseMode.MARKDOWN, **kwargs)
    except TelegramBadRequest:
        plain = strip_markdown(text)
        try:
            await message.edit_text(plain, **kwargs)
        except TelegramBadRequest:
            pass  # Ignore repeated edit failures


def _build_progress_bar(pct: int, width: int = 20) -> str:
    """Build a filled progress bar string."""
    filled = pct * width // 100
    return "█" * filled + "░" * (width - filled)


# ---------------------------------------------------------------------------
# Inline example list (replaces deleted examples.py module)
# ---------------------------------------------------------------------------

_EXAMPLES = [
    {"name": "Taylor Series", "prompt": "animate the Taylor series approximation of sin(x) showing each term building up", "category": "Calculus", "is_3d": False},
    {"name": "Fourier Transform", "prompt": "show me how a Fourier transform decomposes a signal into sine waves", "category": "Calculus", "is_3d": False},
    {"name": "Parametric Curve", "prompt": "animate a particle moving along a parametric curve with a glowing trail", "category": "Geometry", "is_3d": False},
    {"name": "Eigenvalues", "prompt": "visualize the eigenvalues of a 2x2 matrix as it transforms the unit circle", "category": "Linear Algebra", "is_3d": False},
    {"name": "Central Limit Theorem", "prompt": "animate the central limit theorem with random distributions converging to a bell curve", "category": "Probability", "is_3d": False},
    {"name": "Riemann Sum", "prompt": "show the Riemann sum approximation of an integral with rectangles converging", "category": "Calculus", "is_3d": False},
    {"name": "Damped Oscillator", "prompt": "animate a damped harmonic oscillator with phase space diagram", "category": "Physics", "is_3d": False},
    {"name": "Gradient Descent", "prompt": "visualize how gradient descent finds the minimum of a loss function", "category": "Calculus", "is_3d": False},
    {"name": "Voronoi Diagram", "prompt": "animate the construction of a Voronoi diagram from random seed points", "category": "Geometry", "is_3d": False},
    {"name": "Newton's Method", "prompt": "show the convergence of Newton's method for finding roots", "category": "Calculus", "is_3d": False},
    {"name": "Mandelbrot Zoom", "prompt": "animate the Mandelbrot set zoom-in revealing self-similarity", "category": "Complex Analysis", "is_3d": False},
    {"name": "Cross Product", "prompt": "visualize the cross product of two vectors as a changing parallelogram area", "category": "Linear Algebra", "is_3d": False},
]


def get_all_examples() -> list[dict]:
    """Return all example prompts."""
    return list(_EXAMPLES)


def get_example_by_index(index: int) -> dict:
    """Return a specific example by index (wraps around)."""
    return _EXAMPLES[index % len(_EXAMPLES)]


# ---------------------------------------------------------------------------
# Progress Updates (chat action spinner while LLM generates code)
# ---------------------------------------------------------------------------

async def _progress_loop(chat_id: int, render_task, narration_task: asyncio.Task | None, status_message: types.Message | None = None):
    """Send periodic chat-action spinner updates while render/narration run.

    Note: this loop only sends the lightweight Telegram chat-action (the
    "recording video…" indicator). It deliberately does NOT edit the status
    message text — the renderer's progress callback (`_on_manim_progress`) is
    the single owner of the status text, so the two never clobber each other.
    """
    actions = [
        ChatAction.RECORD_VIDEO,
        ChatAction.RECORD_VIDEO,
        ChatAction.UPLOAD_VIDEO,
    ]
    idx = 0
    try:
        while not (render_task.done() and (narration_task is None or narration_task.done())):
            try:
                await bot.send_chat_action(chat_id, actions[idx % len(actions)])
            except Exception:
                pass
            idx += 1
            await asyncio.sleep(15)
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# Intent Classification (hardened)
# ---------------------------------------------------------------------------

_ANIMATE_RE = re.compile(
    r"\b(animat|render|draw|visuali[sz]e|manim|animate|show\s+me|make\s+(a|an)\s+(video|animation|clip))\b",
    re.IGNORECASE,
)
_CHAT_RE = re.compile(
    r"\b(explain|what\s+is|how\s+to|why|help|hello|hi\b|thanks|translate|write\s+(a|an)\s+(poem|essay|story))\b",
    re.IGNORECASE,
)
_HEURISTIC_SHORT_THRESHOLD = 6


async def _classify_intent(text: str, chat_id: int) -> str:
    """Hardened intent classification with heuristic fast-path + LLM fallback."""
    cleaned = text.strip().rstrip(".!?,:;")
    word_count = len(cleaned.split())

    if _ANIMATE_RE.search(cleaned) and not _CHAT_RE.search(cleaned):
        if word_count <= _HEURISTIC_SHORT_THRESHOLD:
            logger.debug(f"Heuristic ANIMATE: '{cleaned}'")
            return "ANIMATE"

    if _CHAT_RE.search(cleaned) and not _ANIMATE_RE.search(cleaned):
        logger.debug(f"Heuristic CHAT: '{cleaned}'")
        return "CHAT"

    try:
        result = await classify_intent(cleaned, provider=user_settings.get(chat_id, "provider"))
        logger.debug(f"LLM intent: '{cleaned}' → {result}")
        return result
    except Exception as e:
        logger.warning(f"Intent classification failed, defaulting to CHAT: {e}")
        return "CHAT"


# ---------------------------------------------------------------------------
# Manim Animation Pipeline
# ---------------------------------------------------------------------------

async def _send_animation(
    message: types.Message,
    prompt: str,
    is_3d: bool = False,
    quality: str | None = None,
    theme_name: str | None = None,
    tiktok_mode: bool = False,
    skip_cache: bool = False,
    edit_base_code: str = "",
    edit_instruction: str = "",
    pregenerated_code: str = "",
) -> None:
    """Full animation pipeline with queue, themes, self-healing, and caching.

    When ``edit_base_code`` is provided, the generation step starts from that
    code and applies ``edit_instruction`` (edit-by-diff) instead of generating a
    brand-new animation from scratch.

    When ``pregenerated_code`` is provided (e.g. the winner of ``/debate``), the
    generation step is skipped entirely and that code goes straight into the
    validate → judge → render pipeline — so the work that produced it is not
    thrown away.
    """
    chat_id = message.chat.id
    original_prompt = prompt  # captured before any enhancement; used for the cache key
    # Edits always bypass the cache so the user gets the modified version.
    if edit_base_code:
        skip_cache = True
    # A pre-generated candidate (e.g. /debate winner) must be the thing rendered,
    # not a cached look-alike for the same prompt.
    if pregenerated_code:
        skip_cache = True

    # TikTok mode detection (auto-detect if not explicitly set)
    if not tiktok_mode:
        tiktok_mode = detect_tiktok_mode(prompt)

    if tiktok_mode:
        logger.info(f"TikTok mode activated for chat_id={chat_id}")

    # Rate limiting
    allowed, retry_after = rate_limiter.check_rate_limit(chat_id, "animate")
    if not allowed:
        await _safe_reply(message, f"⏳ Rate limit reached. Try again in {retry_after}s.")
        return

    # Check for existing task
    existing = render_queue.get_user_task(chat_id)
    if existing:
        await _safe_reply(message, f"⏳ You already have a render in progress: `{existing.prompt[:50]}…`")
        return

    # Pre-flight memory gate (truest fail-fast). The renderer blocks any render
    # at >85% RAM, so if we're already there, generating code + judging it would
    # just be thrown away when the render is blocked. Fail honestly now and spend
    # no LLM calls. (Threshold mirrors renderer.render's >85% block.)
    mem = psutil.virtual_memory()
    if mem.percent > 85:
        free_gb = mem.available / 1024 ** 3
        await _safe_reply(message, (
            f"⚠️ The server is low on memory right now (only {free_gb:.1f} GB free). "
            f"Renders need headroom — please close other apps or try again in a few minutes."
        ))
        analytics.log_render_failure(chat_id, "resource_blocked_preflight")
        return

    # Get user settings. Quality precedence: explicit arg (e.g. /draft) >
    # user's explicit /quality override > the active render tier's default.
    # The tier default (e.g. 1080p on capable hardware) wins when the user has
    # not deliberately chosen a quality.
    tier = get_tier()
    user_quality = quality or user_settings.get_override(chat_id, "quality") or tier.default_quality
    user_theme = theme_name or user_settings.get(chat_id, "theme") or "visual_math"
    user_voiceover = user_settings.get(chat_id, "voiceover_enabled")
    user_voice = user_settings.get(chat_id, "tts_voice") or TTS_VOICE
    user_rate = user_settings.get(chat_id, "tts_rate") or TTS_RATE
    theme = get_theme(user_theme)

    await bot.send_chat_action(chat_id, ChatAction.RECORD_VIDEO)

    # Submit to queue
    task = await render_queue.submit_task(chat_id, prompt, is_3d=is_3d, quality=user_quality)

    # Cache key includes theme + quality + format so different variants don't
    # collide (same prompt, different look = different cache entry). Built from
    # the original prompt so the check (here) and save (later) always agree even
    # after prompt enhancement rewrites `prompt`.
    cache_key = f"{original_prompt}|theme={user_theme}|q={user_quality}|tt={int(bool(tiktok_mode))}"

    # D1 cache check (skipped for edits so the user always gets the modified version)
    if not skip_cache:
        try:
            cached_file_id = await d1.check_cache(chat_id, cache_key)
            if cached_file_id:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                await message.reply_video(video=cached_file_id, caption="⚡ Cached result")
                logger.info(f"Animation done — chat_id={chat_id}, cache HIT")
                return
        except Exception as e:
            logger.warning(f"Cache check failed (degraded): {e}")

    # Acquire semaphore (blocks if another render is running)
    async with render_queue.semaphore:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()

        try:
            code: str = ""
            theme_prompt: str = ""  # Always defined — empty for templates, built for LLM path
            scene_plan_json: str = ""  # Always defined — empty for templates, built for LLM path

            # ── PRE-GENERATED: render a candidate produced upstream (e.g. the
            # /debate winner) instead of generating a fresh, unrelated one ──
            if pregenerated_code:
                theme_prompt = (
                    get_tiktok_prompt(prompt, theme_instructions=build_theme_prompt(theme))
                    if tiktok_mode else build_theme_prompt(theme)
                )
                code = strip_code_fences(pregenerated_code)
                logger.info("Using pre-generated code (%d chars), skipping generation", len(code))

            # ── EDIT-BY-DIFF: start from the prior code and apply the change ──
            elif edit_base_code:
                theme_prompt = (
                    get_tiktok_prompt(prompt, theme_instructions=build_theme_prompt(theme))
                    if tiktok_mode else build_theme_prompt(theme)
                )
                await _safe_reply(message, "✏️ Applying your change to the previous animation…")
                try:
                    edited = strip_code_fences(
                        await edit_manim_code(edit_base_code, edit_instruction, theme_prompt, prompt)
                    )
                    if "class GenScene" in edited and "def construct" in edited:
                        code = edited
                        logger.info("Edit-by-diff applied (%d → %d chars)", len(edit_base_code), len(code))
                    else:
                        logger.warning("Edit-by-diff produced invalid structure; falling back to full generation")
                except Exception as e:
                    logger.warning(f"Edit-by-diff failed ({e}); falling back to full generation")

            # ── TEMPLATE MATCHING: try fast path before full code gen ──
            template_match = get_registry().match(prompt) if not code else None

            if template_match:
                # Fast path: LLM fills small JSON config → template generates code
                await _safe_reply(message, (
                    f"🎨 Template: **{template_match.template.name}** "
                    f"(confidence {template_match.confidence:.2f})\n"
                    f"🔧 Filling parameters…"
                ))
                config_dict = await fill_template_config(
                    template_match.template.name, prompt
                )
                if config_dict:
                    config = template_match.config
                    # Override defaults with LLM-filled values
                    for key, val in config_dict.items():
                        if hasattr(config, key):
                            setattr(config, key, val)
                    # Style unification: deterministic templates must follow the
                    # active theme, not a fixed cyan/green/purple palette.
                    if getattr(theme, "colors", None):
                        config.colors = list(theme.colors[:3])
                    # Generate code from template (deterministic, no LLM)
                    code = template_match.template.generate_code(config)
                    # Force the theme background even if the template hard-codes one.
                    code = re.sub(
                        r'self\.camera\.background_color\s*=\s*"[^"]*"',
                        f'self.camera.background_color = "{theme.bg_color}"',
                        code, count=1,
                    )
                    logger.info(
                        "Template %s generated code (%d chars) in config-fill mode, theme=%s",
                        template_match.template.name, len(code), theme.name,
                    )

            if not code:
                # Enhance prompt for better code generation (skip if already template-matched)
                # Only enhance if prompt is short/vague (< 15 words)
                word_count = len(prompt.split())
                if word_count < 15:
                    await _safe_reply(message, "🔍 Enhancing your prompt for better quality...")
                    prompt = await enhance_prompt(prompt, is_tiktok=tiktok_mode)
                    logger.info(f"Prompt enhanced from {word_count} words: '{prompt[:100]}...'")

                # Slow path: full LLM code generation
                format_label = "📱 TikTok (9:16)" if tiktok_mode else f"🎨 Theme: **{theme.name}**"
                await _safe_reply(message, (
                    f"🤖 Generating Manim code with **{GPT_MODEL}**…\n"
                    f"{format_label} | Quality: `{user_quality}`"
                ))

                # Build theme/format-specific prompt
                if tiktok_mode:
                    theme_prompt = get_tiktok_prompt(prompt, theme_instructions=build_theme_prompt(theme))
                else:
                    theme_prompt = build_theme_prompt(theme)

                # Add error pattern avoidance from recent failures (the
                # memory-pressure modifier only applies on the constrained tier)
                error_modifiers = get_adaptive_prompt_modifiers(constrained=(tier.name == "constrained"))
                if error_modifiers:
                    theme_prompt += error_modifiers
                    logger.info("Error pattern modifiers added to prompt")

                # ── Scene Awareness: plan → generate → validate → repair ──
                # Step 1: Generate scene composition plan (non-fatal on failure)
                try:
                    raw_plan = await generate_scene_plan(prompt)
                    plan = parse_scene_plan(raw_plan)
                    if plan:
                        scene_plan_json = format_plan_for_prompt(plan)
                        logger.info(f"Scene plan generated: {len(plan.get('objects', []))} objects, "
                                    f"{len(plan.get('phases', []))} phases")
                    else:
                        logger.warning("Scene plan parsing failed, proceeding without plan")
                except Exception as e:
                    logger.warning(f"Scene plan generation failed (non-fatal): {e}")

                # Step 2: Generate code with scene plan context (with retries)
                for attempt in range(1, GPT_MAX_RETRIES + 1):
                    try:
                        logger.info(f"Trying {GPT_MODEL} for code generation (attempt {attempt}/{GPT_MAX_RETRIES})")
                        code = await generate_manim_code(
                            prompt, theme_instructions=theme_prompt, scene_plan=scene_plan_json
                        )
                        if code and code.strip():
                            break
                    except Exception as e:
                        logger.warning(f"Code gen attempt {attempt} failed: {e}")
                        if attempt == GPT_MAX_RETRIES:
                            raise
                        await asyncio.sleep(2)

                if not code or not code.strip():
                    await _safe_reply(message, "⚠️ Empty code generated. Try rephrasing your description.")
                    task.status = TaskStatus.FAILED
                    task.error_message = "Empty code"
                    task.completed_at = datetime.now()
                    analytics.log_render_failure(chat_id, "empty_code")
                    return

            code = strip_code_fences(code)

            # Step 3: Layout validation — detect overlap/crowding before rendering
            layout_issues = validate_layout(code)
            if has_issues(layout_issues):
                logger.info(f"Layout validator found {len(layout_issues)} issues, attempting repair")
                for issue in layout_issues:
                    logger.debug(f"  Layout issue: {issue}")

                # Step 4: Layout repair — fix ONLY spatial/timing, preserve creative metaphor
                try:
                    repaired = await repair_layout(code, layout_issues, theme_prompt, prompt)
                    if repaired and repaired.strip():
                        repaired = strip_code_fences(repaired)
                        # Verify repaired code still has structure
                        if "class GenScene" in repaired and "def construct" in repaired:
                            code = repaired
                            logger.info("Layout repair applied successfully")
                        else:
                            logger.warning("Layout repair produced invalid code structure, keeping original")
                    else:
                        logger.warning("Layout repair returned empty code, keeping original")
                except Exception as e:
                    logger.warning(f"Layout repair failed (non-fatal): {e}")

            # ── Static quality checks (fast, no LLM cost) ──
            static_checks = static_quality_check(code)
            if static_checks["issues"]:
                logger.info(f"Static checks: {len(static_checks['issues'])} issues")
                for issue in static_checks["issues"]:
                    logger.debug(f"  Static: {issue}")

            # ── Critic Agent: pre-render quality scoring (non-fatal) ──
            try:
                review = await critique_code(code, prompt)
                logger.info(f"Critic score: {review.overall:.1f}/10, issues={len(review.issues)}")
                if review.needs_repair and review.issues:
                    logger.info(f"Critic suggests repair: {review.issues[0]}")
            except Exception as e:
                logger.warning(f"Critique failed (non-fatal): {e}")
                review = None

            # ── Educational Reviewer: verify mathematical accuracy (non-fatal) ──
            try:
                edu_review = await review_education(code, prompt)
                if not edu_review.is_correct:
                    logger.warning(f"Education review found issues: {edu_review.issues}")
                if edu_review.missing_concepts:
                    logger.info(f"Missing concepts: {edu_review.missing_concepts}")
            except Exception as e:
                logger.warning(f"Education review failed (non-fatal): {e}")
                edu_review = None

            # ── Reviewer-driven repair: turn review FINDINGS into code changes ──
            # Previously the critic/education scores were only logged; now a low
            # critic score or an education-accuracy problem triggers ONE targeted
            # repair before the render gate (concept preserved, bounded, non-fatal).
            if REVIEW_REPAIR_ENABLED:
                repair_issues: list[str] = []
                focus_parts: list[str] = []
                if edu_review and (not edu_review.is_correct or edu_review.issues):
                    repair_issues.extend(edu_review.issues or ["Mathematical/conceptual inaccuracy detected."])
                    focus_parts.append("mathematical accuracy")
                if review and review.overall < CRITIC_REPAIR_THRESHOLD and review.issues:
                    repair_issues.extend(review.issues)
                    focus_parts.append("visual clarity and composition")
                if repair_issues:
                    logger.info(
                        "Reviewer-repair triggered (%d issues, critic=%.1f) — applying targeted fix",
                        len(repair_issues), (review.overall if review else -1.0),
                    )
                    try:
                        fixed = await repair_targeted(
                            code, repair_issues, prompt,
                            theme_instructions=theme_prompt,
                            focus=" and ".join(focus_parts) or "quality and correctness",
                        )
                        fixed = strip_code_fences(fixed)
                        if "class GenScene" in fixed and "def construct" in fixed:
                            code = fixed
                            logger.info("Reviewer-repair applied")
                        else:
                            logger.warning("Reviewer-repair produced invalid structure — keeping original")
                    except Exception as e:
                        logger.warning(f"Reviewer-repair failed (non-fatal): {e}")

            # ── Judge of AI Court: code review with verdict (MiniMax M3) ──
            static_issues = static_checks.get("issues", []) if static_checks else []
            judge_iteration = 0
            judge_review: JudgeReview | None = None

            # Create status message early so Judge can update it
            status_msg = await message.reply("🎬 Preparing render…")

            while judge_iteration < 2:  # max 2 iterations
                judge_iteration += 1

                await _safe_edit(
                    status_msg,
                    "⚖️ *Judge reviewing…*\n_Iteration {}/2_".format(judge_iteration)
                )

                judge_review = await judge_code(
                    code,
                    prompt,
                    critic_review=review,
                    static_issues=static_issues,
                    iteration=judge_iteration,
                )

                logger.info(
                    f"Judge #{judge_iteration}: {judge_review.verdict.value}, "
                    f"score={judge_review.score:.1f}, "
                    f"critical={len(judge_review.critical_issues)}, "
                    f"warnings={len(judge_review.warnings)}"
                )

                if judge_review.verdict == JudgeVerdict.ACCEPT:
                    logger.info("Judge ACCEPTED code for render")
                    await _safe_edit(
                        status_msg,
                        "✅ *Judge approved* (score: {}/10)\n_Preparing render…".format(
                            judge_review.score
                        )
                    )
                    break

                if judge_review.verdict == JudgeVerdict.REPAIR and judge_iteration < 2:
                    # Send back to generator for repair
                    await _safe_edit(
                        status_msg,
                        "🔧 *Judge found {} issues*\n_Repairing (iteration {}/2)_".format(
                            len(judge_review.critical_issues), judge_iteration
                        )
                    )
                    logger.info(
                        f"Judge REPAIR: {len(judge_review.repair_instructions)} fixes, "
                        f"sending to generator"
                    )
                    try:
                        code = await repair_by_judge(code, prompt, judge_review)
                        logger.info("Code repaired, re-judging…")
                    except Exception as e:
                        logger.error(f"Judge-driven repair failed: {e}")
                        # If repair fails, still try to render original (fail-safe)
                        await _safe_edit(
                            status_msg,
                            "⚠️ *Repair failed*\n_Rendering as-is…"
                        )
                        break

                elif judge_review.verdict == JudgeVerdict.REJECT and judge_iteration < 2:
                    # Full regeneration
                    await _safe_edit(
                        status_msg,
                        "❌ *Judge rejected*\n_Regenerating from scratch (iteration {}/2)_".format(judge_iteration)
                    )
                    logger.info(
                        f"Judge REJECT: {judge_review.regenerate_reason}, "
                        f"regenerating code"
                    )
                    try:
                        code = await generate_manim_code(
                            prompt + "\n\nAVOID: " + "; ".join(judge_review.critical_issues[:3]),
                            theme_instructions=theme_prompt,
                            scene_plan=scene_plan_json,
                        )
                        if "class GenScene" not in code or "def construct" not in code:
                            logger.warning("Regenerated code missing structure, trying layout repair")
                            try:
                                repaired = await repair_layout(
                                    code,
                                    ["Missing GenScene class or construct method"],
                                    original_prompt=prompt,
                                )
                                if "class GenScene" in repaired and "def construct" in repaired:
                                    code = repaired
                            except Exception:
                                pass
                        logger.info("Code regenerated, re-judging…")
                    except Exception as e:
                        logger.error(f"Code regeneration failed: {e}")
                        await _safe_edit(
                            status_msg,
                            "⚠️ *Regeneration failed*\n_Rendering as-is…"
                        )
                        break
                else:
                    # UNREVIEWED (judge unavailable) or max iterations reached.
                    # Render either way, but be honest about which one happened.
                    if judge_review and judge_review.verdict == JudgeVerdict.UNREVIEWED:
                        logger.warning("Judge UNREVIEWED — rendering without correctness review")
                        await _safe_edit(
                            status_msg,
                            "⚠️ *Correctness review unavailable*\n_Rendering anyway…_"
                        )
                    elif judge_review:
                        await _safe_edit(
                            status_msg,
                            "⚠️ *Judge max iterations reached*\n_Rendering as-is…_"
                        )
                    break

            # Check scene weight before rendering (for user info)
            from renderer import _estimate_scene_weight
            weight = _estimate_scene_weight(code)
            if weight.is_heavy:
                await _safe_edit(status_msg, "⚠️ Heavy scene detected — auto-optimizing for your hardware…")
                await asyncio.sleep(0.5)  # Let user see the warning
            _render_progress = {"pct": 0, "anim": ""}
            _background_tasks: set[asyncio.Task] = set()

            def _on_manim_progress(pct: int, anim_name: str) -> None:
                """Callback from renderer — updates Telegram status message."""
                _render_progress["pct"] = pct
                _render_progress["anim"] = anim_name or "unknown"
                bar = _build_progress_bar(pct)
                task = asyncio.create_task(
                    _safe_edit(status_msg, f"🎬 *Rendering…*\n{bar} {pct}%\n🎞️ `{(anim_name or 'unknown')[:40]}`")
                )
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)

            render_coro = render(
                code, chat_id, timeout=MANIM_TIMEOUT, quality=user_quality,
                tiktok_mode=tiktok_mode, cancel_event=task.cancel_event,
                progress_cb=_on_manim_progress,
            )

            render_start = datetime.now()
            # Render first. Narration is generated AFTER the render, from the
            # final code, so the script can reference the actual visual beats
            # (and so a self-heal/fallback that changes the code is reflected).
            # Latency is not a concern here; correctness of sync is.
            render_task = asyncio.create_task(render_coro)
            progress_task = asyncio.create_task(_progress_loop(chat_id, render_task, None, status_msg))
            try:
                video_path = await render_task
            except asyncio.CancelledError:
                await _cancel_task(progress_task)
                task.status = TaskStatus.CANCELLED
                raise
            await _cancel_task(progress_task)
            narration = None  # generated later, from the final code

            # Check if user cancelled
            if task.is_cancelled():
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                await _safe_reply(message, "❌ Render cancelled.")
                return

            # Resource failures (RAM / timeout) cannot be fixed by rewriting code:
            # an OOM/timeout would re-render into the same wall, and even the
            # lightweight fallback render would be blocked at >85% RAM. Fail fast
            # with an honest message and spend NO LLM repair calls.
            if (video_path is None and render._last_error
                    and classify_render_error(render._last_error) == "resource"):
                err = render._last_error
                low = err.lower()
                if "timed out" in low or "too heavy" in low:
                    msg = (
                        f"⚠️ That scene was too heavy and timed out at {MANIM_TIMEOUT}s. "
                        f"Try a simpler prompt or fewer moving parts."
                    )
                    reason = "resource_timeout"
                else:
                    free_gb = psutil.virtual_memory().available / 1024 ** 3
                    msg = (
                        f"⚠️ The render couldn't run — the server is low on memory right now "
                        f"({free_gb:.1f} GB free). Please close other apps or try again shortly."
                    )
                    reason = "resource_blocked"
                logger.warning("Render hit a resource limit (%s) — failing fast, skipping code repair + fallback", reason)
                task.status = TaskStatus.FAILED
                task.error_message = err[:500]
                task.completed_at = datetime.now()
                analytics.log_render_failure(chat_id, reason)
                await _safe_reply(message, msg)
                return

            # Self-healing (CODE errors only — resource errors returned above):
            # up to MANIM_MAX_RETRIES attempts with escalating simplification.
            if video_path is None and render._last_error and MANIM_MAX_RETRIES > 0:
                error_msg = render._last_error
                if "cancelled" not in error_msg.lower():
                    for heal_attempt in range(1, MANIM_MAX_RETRIES + 1):
                        logger.info("Render failed — self-healing attempt %d/%d", heal_attempt, MANIM_MAX_RETRIES)
                        await _safe_reply(message, f"🔧 Render failed, asking {GPT_MODEL} to fix the code (attempt {heal_attempt})…")

                        try:
                            fixed_code = await fix_manim_code(prompt, error_msg, theme_prompt, original_code=code)
                            if fixed_code and fixed_code.strip():
                                fixed_code = strip_code_fences(fixed_code)
                                video_path = await render(
                                    fixed_code, chat_id, timeout=MANIM_TIMEOUT, quality=user_quality,
                                    tiktok_mode=tiktok_mode, cancel_event=task.cancel_event,
                                    progress_cb=_on_manim_progress,
                                )
                                if video_path:
                                    code = fixed_code
                                    break
                                # Second attempt: simplify if first repair also failed
                                if heal_attempt == 1:
                                    error_msg = render._last_error or error_msg
                                    await _safe_reply(message, "🔧 Still failing — trying a simpler version…")
                                    fixed_code = await fix_manim_code(
                                        prompt,
                                        f"Previous repair also failed. SIMPLIFY the scene: reduce object count, remove heavy updaters, fewer self.play() calls, shorter duration. Error: {error_msg}",
                                        theme_prompt,
                                        original_code=fixed_code,
                                    )
                                    if fixed_code and fixed_code.strip():
                                        fixed_code = strip_code_fences(fixed_code)
                                        video_path = await render(
                                            fixed_code, chat_id, timeout=MANIM_TIMEOUT, quality=user_quality,
                                            tiktok_mode=tiktok_mode, cancel_event=task.cancel_event,
                                            progress_cb=_on_manim_progress,
                                        )
                                        if video_path:
                                            code = fixed_code
                                            break
                        except Exception as e:
                            logger.error(f"Self-healing attempt {heal_attempt} failed: {e}")

                    # Log error pattern for learning (after all self-heal attempts exhausted)
                    if video_path is None:
                        log_error(prompt, render._last_error or "unknown", code)

            # Check cancellation again after self-heal
            if task.is_cancelled():
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                await _safe_reply(message, "❌ Render cancelled.")
                return

            # Deterministic fallback: never fail a user request just because generated code is brittle.
            if video_path is None:
                error_detail = render._last_error or "Unknown error"
                logger.warning("LLM render failed after repair; using deterministic fallback. Last error: %s", error_detail[:700])
                await _safe_reply(message, "🛟 Generated code was unstable, rendering a safe fallback animation instead…")
                fallback_code = build_fallback_scene(prompt, bg_color=theme.bg_color)
                video_path = await render(
                    fallback_code, chat_id, timeout=min(MANIM_TIMEOUT, 180), quality="-ql",
                    tiktok_mode=tiktok_mode, cancel_event=task.cancel_event,
                    progress_cb=_on_manim_progress,
                )
                if video_path:
                    code = fallback_code
                else:
                    if task.is_cancelled():
                        task.status = TaskStatus.CANCELLED
                        task.completed_at = datetime.now()
                        await _safe_reply(message, "❌ Render cancelled.")
                        return
                    error_display = (render._last_error or error_detail or "Unknown error")[:500]
                    task.status = TaskStatus.FAILED
                    task.error_message = error_display
                    task.completed_at = datetime.now()
                    analytics.log_render_failure(chat_id, "render_failed")
                    await _safe_reply(message, (
                        f"❌ Animation failed after generated, repaired, and fallback attempts.\n\n"
                        f"**Error:**\n```\n{error_display}\n```"
                    ))
                    return

            # ── Visual feedback loop: critique the ACTUAL rendered frames ──
            # The only quality check that SEES the pixels. On a fail it feeds the
            # visible issues back to the generator and re-renders. Bounded + fully
            # non-fatal (any error keeps the current render).
            if VISUAL_CRITIC_ENABLED and video_path and not task.is_cancelled():
                for vpass in range(VISUAL_CRITIC_MAX_PASSES):
                    try:
                        verdict = await critique_render(video_path, prompt, code)
                    except Exception as e:
                        logger.warning(f"Visual critic error (non-fatal): {e}")
                        break
                    if verdict is None or verdict.passed:
                        if verdict:
                            logger.info("Visual critic passed (score %.1f)", verdict.score)
                        break
                    await _safe_edit(
                        status_msg,
                        "🔎 *Visual critic found issues* (score {:.1f}/10)\n_Polishing the composition…_".format(verdict.score),
                    )
                    guidance = list(verdict.issues)
                    if verdict.regenerate_guidance:
                        guidance.append(verdict.regenerate_guidance)
                    if not guidance:
                        break
                    try:
                        improved = strip_code_fences(await repair_targeted(
                            code, guidance, prompt,
                            theme_instructions=theme_prompt,
                            focus="visual composition, readability, spacing and removing overlap/clutter",
                        ))
                    except Exception as e:
                        logger.warning(f"Visual-critic repair failed (non-fatal): {e}")
                        break
                    if "class GenScene" not in improved or "def construct" not in improved:
                        logger.warning("Visual-critic repair invalid structure; keeping current render")
                        break
                    new_video = await render(
                        improved, chat_id, timeout=MANIM_TIMEOUT, quality=user_quality,
                        tiktok_mode=tiktok_mode, cancel_event=task.cancel_event,
                        progress_cb=_on_manim_progress,
                    )
                    if new_video:
                        video_path, code = new_video, improved
                        logger.info("Visual-critic re-render succeeded (pass %d)", vpass + 1)
                    else:
                        logger.warning("Visual-critic re-render failed; keeping previous render")
                        break

            # Record render success
            render_time = (datetime.now() - render_start).total_seconds()
            analytics.log_render_success(chat_id, render_time)

            # Add watermark (non-fatal)
            try:
                wm_dir = Path("tmp") / "watermark" / str(chat_id)
                watermarked = await add_watermark(video_path, wm_dir)
                if watermarked:
                    video_path = watermarked
                    logger.info("Watermark applied")
                else:
                    logger.warning("Watermark failed (non-fatal)")
            except Exception as e:
                logger.warning(f"Watermark error (non-fatal): {e}")

            # Voiceover: derive narration FROM the final code (references the
            # actual visual beats), then fit it to the video length so the audio
            # tracks the animation instead of forcing a frozen tail frame.
            if user_voiceover and VOICEOVER_ENABLED:
                try:
                    await bot.send_chat_action(chat_id, ChatAction.RECORD_VOICE)
                    narration = await _generate_narration(prompt, code)
                    if narration:
                        vo_dir = Path("tmp") / "voiceover" / str(chat_id)
                        narrated = await add_voiceover(
                            video_path, narration, vo_dir,
                            voice=user_voice, rate=user_rate,
                            fit_to_video=True,
                        )
                        if narrated:
                            video_path = narrated
                except Exception as e:
                    logger.warning(f"Voiceover merge failed (non-fatal): {e}")

            # Send result with inline feedback buttons
            await bot.send_chat_action(chat_id, ChatAction.UPLOAD_VIDEO)
            reasoning_tag = f" | {GPT_REASONING_EFFORT} reasoning" if GPT_REASONING_EFFORT else ""
            format_tag = " 📱 TikTok 9:16" if tiktok_mode else ""
            video_file = FSInputFile(str(video_path))

            # Inline keyboard for feedback
            feedback_kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="👍 Great", callback_data=f"feedback:up:{task.task_id}"),
                    InlineKeyboardButton(text="👎 Needs work", callback_data=f"feedback:down:{task.task_id}"),
                ],
                [
                    InlineKeyboardButton(text="✏️ Edit this", callback_data=f"edit:{task.task_id}"),
                    InlineKeyboardButton(text="📋 Code", callback_data=f"code:{task.task_id}"),
                ],
            ])

            sent = await message.reply_video(
                video=video_file,
                caption=f"🎬 `{GPT_MODEL}` | {theme.name}{reasoning_tag}{format_tag}\n\n💬 Reply to this video with changes like _\"make it slower\"_ or _\"add more details\"_",
                reply_markup=feedback_kb,
            )

            # Save to database
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result_path = str(video_path)
            telegram_file_id = sent.video.file_id if sent.video else None

            db.save_render(
                chat_id=chat_id,
                task_id=task.task_id,
                prompt=prompt,
                is_3d=is_3d,
                quality=user_quality,
                theme=user_theme,
                status="completed",
                code=code,
                video_path=str(video_path),
                video_file_id=telegram_file_id,
                started_at=task.started_at,
                completed_at=task.completed_at,
            )

            # Save to D1 cache (fire-and-forget with tracking).
            # Uses the same composite cache_key as the lookup; skipped for edits.
            if telegram_file_id and not skip_cache:
                _d1_tasks: set[asyncio.Task] = set()
                d1_task = asyncio.create_task(
                    d1.save_render(chat_id, cache_key, code, telegram_file_id)
                )
                _d1_tasks.add(d1_task)
                d1_task.add_done_callback(_d1_tasks.discard)

            logger.info(f"Animation done — chat_id={chat_id}, prompt={prompt[:50]}…")

        except Exception as e:
            logger.error(f"Animation pipeline error: {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.now()
            analytics.log_render_failure(chat_id, "pipeline_error")
            await _safe_reply(message, f"⚠️ Animation failed: {e}")


async def _generate_narration(prompt: str, code: str = "") -> str | None:
    """Generate TTS narration that follows the ACTUAL animation.

    Derived from the generated Manim code (not just the prompt) so the spoken
    script tracks the real visual beats in order. The audio is later fit to the
    video length, so the script should describe the animation's full arc.
    """
    code_context = ""
    if code:
        code_context = (
            "\n\nThe animation is produced by this Manim code. Narrate the visual "
            "events in the order they occur on screen:\n```python\n"
            f"{code[:4000]}\n```"
        )
    messages = [
        {
            "role": "system",
            "content": (
                "You are a narrator for short mathematical animations. Write a narration "
                "that walks through what appears on screen, in order, guiding the viewer's "
                "eye ('first…', 'then…', 'notice how…'). Explain the WHY, not just the WHAT. "
                "Keep it concise (about 2-5 sentences, 35-90 words depending on the "
                "animation's length and complexity). Output ONLY the narration text — no "
                "markdown, no stage directions, no scene numbers."
            ),
        },
        {"role": "user", "content": f"Animation request: {prompt}{code_context}"},
    ]
    try:
        text = await chat(messages)
        return text.strip() if text and not text.startswith("⚠️") else None
    except Exception as e:
        logger.warning(f"Narration generation failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Handlers — Commands

@dp.message(Command("tiktok"))
async def cmd_tiktok(message: types.Message) -> None:
    """Re-render the last animation in TikTok 9:16 format."""
    chat_id = message.chat.id
    last_render = db.get_last_render(chat_id)
    if not last_render or not last_render.get("prompt"):
        await _safe_reply(message, "No animation found. Render something first!")
        return
    original_prompt = last_render["prompt"]
    await _safe_reply(message, "📱 Re-rendering in TikTok format (9:16, 25-30s)...")
    await _send_animation(message, original_prompt, tiktok_mode=True)



@dp.message(Command("draft"))
async def cmd_draft(message: types.Message) -> None:
    """Quick draft render of last animation at lowest quality."""
    chat_id = message.chat.id
    last_render = db.get_last_render(chat_id)
    if not last_render or not last_render.get("prompt"):
        await _safe_reply(message, "⚠️ No animation found. Render something first!")
        return
    original_prompt = last_render["prompt"]
    await _safe_reply(message, "📝 Draft mode: quick preview at 480p, 60s timeout...")
    await _send_animation(message, original_prompt, quality="-l")


@dp.message(Command("export"))
async def cmd_export(message: types.Message) -> None:
    """Export last animation with TikTok-ready caption and hashtags."""
    chat_id = message.chat.id
    last_render = db.get_last_render(chat_id)
    if not last_render:
        await _safe_reply(message, "No animation found. Render something first!")
        return
    prompt = last_render.get("prompt", "")
    hashtags = _generate_hashtags(prompt)
    caption = f"{prompt[:80]}...\n\n{hashtags}\n\nMade with @Manim_is_so_useful_bot"
    video_path = last_render.get("video_path")
    if video_path and Path(video_path).exists():
        await message.reply_video(video=FSInputFile(video_path), caption=caption)
    else:
        await _safe_reply(message, f"TikTok-ready caption:\n\n{caption}")


def _generate_hashtags(prompt: str) -> str:
    """Generate relevant hashtags for TikTok/Reels export."""
    p = prompt.lower()
    base = "#MathExplained #LearnOnTikTok #STEM #Education #Animation"
    topics = {
        "fourier": "#Fourier #SignalProcessing",
        "derivative": "#Calculus #Derivatives",
        "integral": "#Calculus #Integrals",
        "eigenvalue": "#LinearAlgebra",
        "matrix": "#LinearAlgebra #Matrix",
        "probability": "#Probability #Statistics",
        "physics": "#Physics #Science",
        "quantum": "#Quantum #Physics",
        "oscillat": "#Oscillation #Waves",
        "gradient": "#MachineLearning #AI",
        "mandelbrot": "#Mandelbrot #Fractal",
        "calculus": "#Calculus",
        "taylor": "#TaylorSeries",
    }
    for kw, tags in topics.items():
        if kw in p:
            return f"{base} {tags}"
    return base


# ---------------------------------------------------------------------------

@dp.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    chat_id = message.chat.id

    # Check for referral code in args: /start ABC12345
    args = (message.text or "").replace("/start", "", 1).strip()
    referred_by = None
    bonus_msg = ""
    if args and args.isalnum():
        # Try to find who owns this referral code
        from referral import _load
        data = _load()
        for uid, udata in data.get("users", {}).items():
            if udata.get("referral_code", "").upper() == args.upper():
                referred_by = int(uid)
                break
        if referred_by:
            result = register_user(chat_id, referred_by=referred_by)
            if result.get("bonus", 0) > 0:
                bonus_msg = f"\n\n🎁 You and your friend each got +{result['bonus']} free renders!"
        else:
            register_user(chat_id)
    else:
        register_user(chat_id)

    user_provider = user_settings.get(chat_id, "provider")
    provider_name = "Claude Opus 4.8" if user_provider == "claude" else "Qwen 3.6 Plus"
    models = (
        f"**Code gen**: `{GPT_MODEL}` (reasoning: `{GPT_REASONING_EFFORT or 'default'}`)\n"
        f"**Chat**: `{provider_name}` (`{user_provider}`)"
    )
    await _safe_answer(message, (
        "🎬 **Manim Animation Bot + AI Assistant**\n\n"
        f"{models}\n\n"
        "I create polished Manim explainers: "
        "clean geometry, semantic color, smooth transforms, and readable equations.\n\n"
        "**Commands:**\n"
        "• Send me text → I'll classify intent automatically\n"
        "• `/animation <description>` → force animation mode\n"
        "• `/provider` → switch chat LLM (Qwen / Claude)\n"
        "• `/settings` → per-user preferences\n"
        "• `/theme` → cycle visual theme\n"
        "• `/examples` → visual math demo prompts\n"
        "• `/example <number>` → render a curated demo\n"
        "• `/code` → show last generated code\n"
        "• `/history` → your recent animations\n"
        "• `/stats` → global statistics\n"
        "• `/clean` → clear render cache\n"
        "• `/cancel` → cancel current render\n"
        "• `/tiktok` → re-render last in TikTok 9:16\n"
        "• `/export` → export with hashtags\n"
        "• `/draft` → quick preview of last animation\n"
        "• `/versions` → last 3 animation versions\n"
        "• `/gallery` → browse curated animations\n"
        "• `/course <topic>` → generate learning course\n"
        "• `/exam [STEP|EGE]` → exam prep mode\n"
        "• `/debate <prompt>` → two AIs compete, best wins\n"
        "• `/referral` → earn free renders by inviting friends\n"
        "• `/teacher` → educator analytics dashboard\n\n"
        "Try: *Animate why matrix multiplication is function composition*"
    ))


@dp.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    await cmd_start(message)


@dp.message(Command("clean"))
async def cmd_clean(message: types.Message) -> None:
    cleanup()
    render_queue.cleanup_old_tasks()
    await _safe_answer(message, "🧹 Render cache cleaned.")


@dp.message(Command("history"))
async def cmd_history(message: types.Message) -> None:
    """Show last 10 animations for this user."""
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        records = db.get_user_history(message.chat.id, limit=10)
        if not records:
            await _safe_reply(message, "📭 No animation history yet. Try `/animation rotating cube`!")
            return

        lines = ["📜 **Your Recent Animations:**\n"]
        for i, rec in enumerate(records, 1):
            prompt = rec.get("prompt", "unknown")[:50]
            status = rec.get("status", "unknown")
            theme = rec.get("theme", "default")
            emoji = "✅" if status == "completed" else "❌" if status == "failed" else "⏳"
            lines.append(f"{i}. {emoji} `{prompt}` — _{theme}_")
        lines.append(f"\n**Total:** {len(records)} animation(s)")
        await _safe_reply(message, "\n".join(lines))
    except Exception as e:
        logger.error(f"History error: {e}")
        await _safe_reply(message, f"⚠️ Couldn't fetch history: {e}")


@dp.message(Command("code"))
async def cmd_code(message: types.Message) -> None:
    """Show the generated Manim code from the user's latest render."""
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        last = db.get_last_render(message.chat.id)
        code = last.get("code") if last else None

        if not code:
            code = get_last_generated_code(message.chat.id)

        if not code:
            await _safe_reply(message, "📭 No code available yet. Try `/animation rotating cube` first!")
            return

        if len(code) > 3800:
            code = code[:3800] + "\n\n# ... truncated"

        await _safe_answer(message, f"🐍 **Last Generated Code:**\n```python\n{code}\n```")
    except Exception as e:
        logger.error(f"Code fetch error: {e}")
        await _safe_reply(message, f"⚠️ Couldn't fetch code: {e}")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message) -> None:
    """Show global and per-user statistics."""
    try:
        global_stats = db.get_stats()
        user_stats = analytics.get_user_stats(message.chat.id)
        render_stats = analytics.get_render_stats()
        top_errors = analytics.get_top_errors(limit=5)

        lines = [
            "📊 **Bot Statistics**\n",
            f"**Global:** {global_stats['total']} renders | "
            f"{global_stats['completed']} ✅ | {global_stats['failed']} ❌ | "
            f"{global_stats['unique_users']} users",
            f"**You:** {user_stats['renders']} renders | "
            f"{user_stats['success']} ✅ | {user_stats['failed']} ❌",
            f"**Avg render time:** {render_stats['avg_render_time']:.1f}s",
            f"**Success rate:** {render_stats['success_rate']:.1f}%",
        ]

        if top_errors:
            lines.append("\n**Top Errors (24h):**")
            for err_type, count in top_errors:
                lines.append(f"  • `{err_type}`: {count}")

        await _safe_reply(message, "\n".join(lines))
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await _safe_reply(message, f"⚠️ Couldn't fetch stats: {e}")


@dp.message(Command("animation"))
async def cmd_animation(message: types.Message) -> None:
    """Force animation mode: /animation <description>"""
    prompt = (message.text or "").replace("/animation", "", 1).strip()
    if not prompt:
        await _safe_reply(message, "Usage: `/animation <description>`\nExample: `/animation rotating 3D cube`")
        return

    # Check for 3D hint
    is_3d = any(w in prompt.lower() for w in ("3d", "three-dimensional", "three dimensional"))
    await _send_animation(message, prompt, is_3d=is_3d)


@dp.message(Command("theme"))
async def cmd_theme(message: types.Message) -> None:
    """Cycle through visual themes."""
    current = user_settings.get(message.chat.id, "theme") or "default"
    new_theme = next_theme(current)
    user_settings.set(message.chat.id, "theme", new_theme)
    theme = get_theme(new_theme)
    await _safe_reply(message, f"🎨 Theme set to **{theme.name}**\n\n_{theme.palette_desc[:100]}…_")


@dp.message(Command("settings"))
async def cmd_settings(message: types.Message) -> None:
    """Show current per-user settings."""
    try:
        s = user_settings.get_all(message.chat.id)
        theme = get_theme(s.get("theme", "visual_math"))
        provider_name = "Claude Opus 4.8" if s.get("provider") == "claude" else "Qwen 3.6 Plus"
        lines = [
            "⚙️ **Your Settings**\n",
            f"**Theme:** {theme.name}",
            f"**Style:** visual intuition → transformation → insight → recap",
            f"**Quality:** `{s.get('quality', MANIM_QUALITY)}`",
            f"**Chat LLM:** {provider_name}",
            f"**Voiceover:** {'✅ enabled' if s.get('voiceover_enabled') else '❌ disabled'}",
            f"**TTS Voice:** `{s.get('tts_voice', TTS_VOICE)}`",
            f"**TTS Rate:** `{s.get('tts_rate', TTS_RATE)}`",
            "",
            "**Commands:**",
            "• `/theme` — cycle visual theme",
            "• `/provider qwen|claude` — switch chat LLM",
            "• `/voice on|off` — toggle voiceover",
            "• `/quality -ql|-qm|-qh` — set render quality",
            "• `/reset` — revert to defaults",
        ]
        await _safe_reply(message, "\n".join(lines))
    except Exception as e:
        logger.error(f"Settings error: {e}")
        await _safe_reply(message, f"⚠️ Couldn't load settings: {e}")


@dp.message(Command("voice"))
async def cmd_voice(message: types.Message) -> None:
    """Toggle voiceover on/off."""
    args = (message.text or "").replace("/voice", "", 1).strip().lower()
    if args in ("on", "1", "yes", "true"):
        user_settings.set(message.chat.id, "voiceover_enabled", True)
        await _safe_reply(message, "🔊 Voiceover **enabled**")
    elif args in ("off", "0", "no", "false"):
        user_settings.set(message.chat.id, "voiceover_enabled", False)
        await _safe_reply(message, "🔇 Voiceover **disabled**")
    else:
        current = user_settings.get(message.chat.id, "voiceover_enabled")
        await _safe_reply(message, f"Voiceover is currently {'**enabled**' if current else '**disabled**'}.\n\nUsage: `/voice on` or `/voice off`")


@dp.message(Command("quality"))
async def cmd_quality(message: types.Message) -> None:
    """Set render quality."""
    args = (message.text or "").replace("/quality", "", 1).strip()
    valid = {"-l": "⚡ Preview", "-ql": "🚀 Fast", "-qm": "✅ Standard", "-qh": "🎬 High"}
    if args in valid:
        user_settings.set(message.chat.id, "quality", args)
        await _safe_reply(message, f"Quality set to **{valid[args]}** (`{args}`)")
    else:
        await _safe_reply(message, "Usage: `/quality -ql` or `-qm` or `-qh`\n\n" +
                          "\n".join(f"  `{k}` — {v}" for k, v in valid.items()))


@dp.message(Command("provider"))
async def cmd_provider_cmd(message: types.Message) -> None:
    """Switch LLM provider per-user: qwen or claude."""
    args = (message.text or "").replace("/provider", "", 1).strip().lower()
    chat_id = message.chat.id
    current = user_settings.get(chat_id, "provider")
    if args in ("claude", "opus"):
        user_settings.set(chat_id, "provider", "claude")
        await _safe_reply(message, "🧠 Your LLM switched to **Claude Opus 4.8**")
    elif args in ("qwen", "qwen3"):
        user_settings.set(chat_id, "provider", "qwen")
        await _safe_reply(message, "🧠 Your LLM switched to **Qwen 3.6 Plus**")
    else:
        await _safe_reply(message,
            f"Your current LLM: **{current.upper()}**\n\n"
            f"Usage: `/provider qwen` or `/provider claude`\n\n"
            f"• `qwen` — Qwen 3.6 Plus (fast, DashScope)\n"
            f"• `claude` — Claude Opus 4.8 (high reasoning, Anthropic)"
        )


@dp.message(Command("reset"))
async def cmd_reset(message: types.Message) -> None:
    """Reset per-user settings to defaults."""
    user_settings.reset(message.chat.id)
    await _safe_reply(message, "⚙️ Settings reset to defaults.")


@dp.message(Command("examples"))
async def cmd_examples(message: types.Message) -> None:
    """Show example animation prompts."""
    examples = get_all_examples()
    lines = ["📚 **Example Animations**\n"]
    current_cat = None
    for i, ex in enumerate(examples):
        if ex.get("category") != current_cat:
            current_cat = ex.get("category")
            lines.append(f"\n**{current_cat}:**")
        dim = "🎲" if ex.get("is_3d") else "📐"
        lines.append(f"  {i+1}. {dim} **{ex['name']}** — _{ex.get('description', '')}_")

    lines.append(f"\n_Run `/example 1` or send me any prompt for a polished Visual Math render._")
    await _safe_reply(message, "\n".join(lines))


@dp.message(Command("example"))
async def cmd_example(message: types.Message) -> None:
    """Render an example by index: /example <number>."""
    args = (message.text or "").replace("/example", "", 1).strip()
    if not args.isdigit():
        await _safe_reply(message, "Usage: `/example 1`\n\nUse `/examples` to see the gallery.")
        return

    example = get_example_by_index(int(args) - 1)
    if not example:
        await _safe_reply(message, "📭 Example not found. Use `/examples` to see available demos.")
        return

    await _safe_reply(message, f"📐 Rendering **{example['name']}** in Visual Math style…")
    await _send_animation(
        message,
        example["prompt"],
        is_3d=bool(example.get("is_3d")),
        theme_name="visual_math",
    )


@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message) -> None:
    """Cancel current render task."""
    task = render_queue.get_user_task(message.chat.id)
    if task:
        if task.cancel():
            await _safe_reply(message, f"❌ Cancelled: `{task.prompt[:50]}…`")
            analytics.log_render_cancelled(message.chat.id)
        else:
            await _safe_reply(message, "⚠️ Could not cancel task.")
    else:
        await _safe_reply(message, "📭 No active render task.")


# ---------------------------------------------------------------------------
# Handlers — WebApp Data (Settings)
# ---------------------------------------------------------------------------


@dp.message(Command("versions"))
async def cmd_versions(message: types.Message) -> None:
    """Show last 3 render versions with prompts."""
    chat_id = message.chat.id
    history = db.get_user_history(chat_id, limit=3)
    if not history:
        await _safe_reply(message, "No animation history yet. Render something first!")
        return

    lines = ["📑 **Your Last Versions:**\n"]
    for i, rec in enumerate(history, 1):
        prompt = rec.get("prompt", "unknown")[:60]
        status = rec.get("status", "unknown")
        theme = rec.get("theme", "default")
        created = rec.get("created_at", "?")[:16]
        emoji = "✅" if status == "completed" else "❌" if status == "failed" else "⏳"
        lines.append(f"{i}. {emoji} `{prompt}...`")
        lines.append(f"   _{theme}_ | {created}")

    await _safe_reply(message, "\n".join(lines))



@dp.message(Command("course"))
async def cmd_course(message: types.Message) -> None:
    """Generate a course series: /course <topic>."""
    args = (message.text or "").replace("/course", "", 1).strip()
    if not args:
        await _safe_reply(message, "Usage: `/course <topic>`\n\nExample: `/course derivatives`")
        return

    await _safe_reply(message, f"📚 Designing a course on **{args}**...")
    try:
        course = await generate_course(args)
        lines = [f"📚 **Course: {course.topic}**\n"]
        for i, lesson in enumerate(course.lessons, 1):
            level_emoji = "🟢" if lesson.level == "beginner" else "🟡" if lesson.level == "intermediate" else "🔴"
            lines.append(f"{i}. {level_emoji} **{lesson.title}** ({lesson.level})")
            lines.append(f"   _{', '.join(lesson.key_concepts[:3])}_")
        lines.append(f"\nReply with a lesson number to generate that animation!")
        await _safe_reply(message, "\n".join(lines))
    except Exception as e:
        logger.error(f"Course generation failed: {e}")
        await _safe_reply(message, f"⚠️ Course generation failed: {e}")




@dp.message(Command("exam"))
async def cmd_exam(message: types.Message) -> None:
    """Exam prep mode: /exam [STEP|EGE] [topic]."""
    args = (message.text or "").replace("/exam", "", 1).strip()

    if not args:
        await _safe_reply(message, (
            "📝 **Exam Prep Mode**\n\n"
            "Usage:\n"
            "• `/exam STEP` — random STEP question\n"
            "• `/exam EGE` — random ЕГЭ question\n"
            "• `/exam STEP derivatives` — STEP question about derivatives\n"
            "• `/exam STEP2 2022 Q3` — specific question"
        ))
        return

    parts = args.split()
    exam_type = parts[0].upper()

    if exam_type in ("STEP", "STEP2", "STEP3"):
        bank_name = "STEP"
    elif exam_type in ("EGE", "ЕГЭ"):
        bank_name = "ЕГЭ"
    else:
        await _safe_reply(message, f"⚠️ Unknown exam: {exam_type}. Use STEP or EGE.")
        return

    # Check for specific topic
    topic = " ".join(parts[1:]) if len(parts) > 1 else ""

    if topic:
        await _safe_reply(message, f"📝 Finding a {bank_name} question about: _{topic}_...")
        question = await generate_animation_for_question(topic, bank_name)
    else:
        await _safe_reply(message, f"📝 Getting a random {bank_name} question...")
        question = get_random_question(bank_name)

    if not question:
        await _safe_reply(message, f"⚠️ No {bank_name} questions available.")
        return

    difficulty_stars = "⭐" * (question.difficulty // 2)
    await _safe_reply(message, (
        f"📝 **{bank_name} {question.year}, Q{question.question_num}** {difficulty_stars}\n\n"
        f"**Topic:** {question.topic}\n"
        f"**Question:** {question.question_text[:200]}...\n\n"
        f"🎬 Generating animation..."
    ))
    is_3d = any(w in question.animation_prompt.lower() for w in ("3d", "three-dimensional"))
    await _send_animation(message, question.animation_prompt, is_3d=is_3d)



@dp.message(Command("gallery"))
async def cmd_gallery(message: types.Message) -> None:
    """Browse gallery: /gallery [category|search|<id>]."""
    args = (message.text or "").replace("/gallery", "", 1).strip()

    if not args:
        # Show featured + categories
        featured = get_featured()
        lines = ["🖼️ **Gallery — Featured**\n"]
        for item in featured:
            diff = "⭐" * (item.difficulty // 2)
            lines.append(f"{item.id}. **{item.title}** {diff}")
            lines.append(f"   _{item.category}_")
        lines.append("\n📂 **Categories:** " + ", ".join(f"`{c}`" for c in ["Calculus", "Linear Algebra", "Probability", "Physics", "Geometry", "Complex Analysis"]))
        lines.append("\nUse `/gallery calculus` to browse a category")
        lines.append("Use `/gallery fourier` to search")
        lines.append("Use `/gallery 3` to render item #3")
        await _safe_reply(message, "\n".join(lines))
        return

    # Try parsing as item ID
    if args.isdigit():
        item_id = int(args)
        item = get_by_id(item_id)
        if not item:
            await _safe_reply(message, f"⚠️ Item #{item_id} not found. Use `/gallery` to browse.")
            return
        increment_view(item.id)
        diff = "⭐" * (item.difficulty // 2)
        await _safe_reply(message, f"🎬 Rendering **{item.title}** {diff} ({item.category})...")
        await _send_animation(message, item.prompt, is_3d=item.is_3d)
        return

    # Try as category
    items = get_by_category(args)
    if items:
        lines = [f"📂 **{args}** ({len(items)} items)\n"]
        for item in items:
            diff = "⭐" * (item.difficulty // 2)
            lines.append(f"{item.id}. **{item.title}** {diff}")
        lines.append(f"\nUse `/gallery <number>` to render an item")
        await _safe_reply(message, "\n".join(lines))
        return

    # Try as search
    results = gallery_search(args)
    if results:
        lines = [f"🔍 **Search: {args}** ({len(results)} results)\n"]
        for item in results:
            diff = "⭐" * (item.difficulty // 2)
            lines.append(f"{item.id}. **{item.title}** {diff}")
            lines.append(f"   _{item.category}_")
        lines.append(f"\nUse `/gallery <number>` to render an item")
        await _safe_reply(message, "\n".join(lines))
        return

    await _safe_reply(message, f"No results for: {args}")



@dp.message(Command("debate"))
async def cmd_debate(message: types.Message) -> None:
    """Multi-agent debate: two LLMs generate code, critic picks the best."""
    prompt = (message.text or "").replace("/debate", "", 1).strip()
    if not prompt:
        await _safe_reply(message, "Usage: `/debate <description>`\n\nTwo AI agents compete to generate the best animation. Takes ~2× longer but produces higher quality.")
        return

    await _safe_reply(message, "⚔️ Starting debate: two AI agents generating independent solutions...")
    chat_id = message.chat.id
    user_quality = user_settings.get(chat_id, "quality") or MANIM_QUALITY
    user_theme = user_settings.get(chat_id, "theme") or "visual_math"
    theme = get_theme(user_theme)
    theme_prompt = build_theme_prompt(theme)

    # Run debate
    code, scores = await debate_generate(prompt, theme_prompt)
    if not code:
        await _safe_reply(message, "⚠️ Both debate agents failed. Try a simpler prompt.")
        return

    # Show scores
    score_text = f"⚔️ **Debate Results:**\n"
    if "winner" in scores:
        score_text += f"🏆 Agent {scores['winner']} won\n"
    if "agent_a" in scores and isinstance(scores["agent_a"], float):
        score_text += f"Agent A: {scores['agent_a']:.1f}/10 | Agent B: {scores['agent_b']:.1f}/10\n"
    score_text += f"\n🎬 Rendering winner's code..."
    await _safe_reply(message, score_text)

    is_3d = any(w in prompt.lower() for w in ("3d", "three-dimensional"))
    await _send_animation(
        message, prompt, is_3d=is_3d, quality=user_quality, theme_name=user_theme,
        pregenerated_code=code,
    )



@dp.message(Command("referral"))
async def cmd_referral(message: types.Message) -> None:
    """Show referral info and stats."""
    chat_id = message.chat.id
    info = get_user_referral_info(chat_id)

    lines = [
        "🎁 **Referral Program**\n",
        f"**Your code:** `{info['code']}`",
        f"**Bonus renders:** {info['bonus_renders']} free",
        f"**Friends referred:** {info['referrals_made']}",
        f"**Total renders:** {info['total_renders']}",
        "",
        "Share `/start " + info['code'] + "` with friends to earn +5 free renders each!",
        "They get +5 free renders too! 🎉",
    ]

    await _safe_reply(message, "\n".join(lines))



@dp.message(Command("teacher"))
async def cmd_teacher(message: types.Message) -> None:
    """Teacher dashboard — analytics for educators."""
    chat_id = message.chat.id
    dashboard = get_teacher_dashboard(chat_id)

    if not dashboard:
        # Register new teacher
        register_teacher(chat_id)
        await _safe_reply(message, (
            "👩‍🏫 **Welcome to Teacher Dashboard!**\n\n"
            "You've been registered as an educator.\n\n"
            "**Commands:**\n"
            "• `/teacher` — view your dashboard\n"
            "• `/class add <student_id>` — add a student\n"
            "• `/class stats` — engagement analytics"
        ))
        return

    engagement = get_engagement_stats(chat_id)

    lines = [
        f"👩‍🏫 **{dashboard['name']}**\n",
        f"**Students:** {engagement['students']}",
        f"**Total views:** {engagement['total_views']}",
        f"**Avg views/student:** {engagement['avg_views_per_student']:.1f}",
        f"**Engagement rate:** {engagement['engagement_rate']:.0f}%",
        f"**Registered:** {dashboard['registered_at']}",
    ]

    await _safe_reply(message, "\n".join(lines))


@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message) -> None:
    """Handle settings sent from Telegram WebApp."""
    try:
        data = json.loads(message.web_app_data.data)
        chat_id = message.chat.id

        # Validate and sanitize settings
        valid_voices = {v[0] for v in user_settings.AVAILABLE_VOICES}
        valid_themes = {t[0] for t in user_settings.AVAILABLE_THEMES}
        valid_qualities = {q[0] for q in user_settings.AVAILABLE_QUALITIES}

        updates = {}

        # Validate voice
        if "voice" in data:
            voice = data["voice"]
            if voice in valid_voices:
                updates["tts_voice"] = voice
            else:
                logger.warning(f"WebApp: invalid voice '{voice}' from chat_id={chat_id}")

        # Validate voiceover toggle
        if "voiceover" in data:
            updates["voiceover_enabled"] = data["voiceover"] in (True, "true", "on", 1, "1")

        # Validate TTS rate — accept "25", "+25", "-30", "25%", "+25%" and
        # normalize to edge-tts's required signed-percent form ("+25%"/"-30%").
        if "rate" in data:
            try:
                rate_val = int(float(str(data["rate"]).replace("%", "").strip()))
                if -50 <= rate_val <= 100:
                    updates["tts_rate"] = f"+{rate_val}%" if rate_val >= 0 else f"{rate_val}%"
                else:
                    logger.warning(f"WebApp: rate out of range '{data['rate']}' from chat_id={chat_id}")
            except ValueError:
                logger.warning(f"WebApp: invalid rate '{data['rate']}' from chat_id={chat_id}")

        # Validate theme
        if "theme" in data:
            theme = data["theme"]
            if theme in valid_themes:
                updates["theme"] = theme
            else:
                logger.warning(f"WebApp: invalid theme '{theme}' from chat_id={chat_id}")

        if updates:
            user_settings.set_many(chat_id, updates)
            await _safe_reply(message, f"✅ Settings updated: {', '.join(updates.keys())}")
        else:
            await _safe_reply(message, "⚠️ No valid settings found in data.")

    except json.JSONDecodeError:
        await _safe_reply(message, "⚠️ Invalid settings data format.")
    except Exception as e:
        logger.error(f"WebApp handler error: {e}", exc_info=True)
        await _safe_reply(message, f"⚠️ Couldn't save settings: {e}")


# ---------------------------------------------------------------------------
# Handlers — Photo (Vision)
# ---------------------------------------------------------------------------

@dp.message(F.photo)
async def handle_photo(message: types.Message) -> None:
    """Photo handler → vision analysis → animate if math/formula detected."""
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        image_data = file_bytes.read()
        caption = message.caption or ""

        user_provider = user_settings.get(message.chat.id, "provider")

        # Step 1: Analyze image with vision model
        analysis_prompt = (
            "Analyze this image. Is it a mathematical formula, equation, diagram, or "
            "scientific content? If yes, describe what concept it shows in 1-2 sentences "
            "and suggest an animation prompt. If no, just describe the image normally. "
            "Start your response with FORMULA: if it contains math, or CHAT: if not."
        )
        response = await chat_with_image(image_data, analysis_prompt, provider=user_provider)

        # Step 2: Check if it's formula content
        if response.startswith("FORMULA:") or "FORMULA:" in response:
            # Extract the animation suggestion
            formula_desc = response.replace("FORMULA:", "").strip()
            await _safe_reply(message, f"📐 Math detected!\n\n{formula_desc}\n\n🎬 Generating animation...")
            is_3d = any(w in formula_desc.lower() for w in ("3d", "three-dimensional"))
            await _send_animation(message, f"Animate: {formula_desc}", is_3d=is_3d)
        else:
            # Regular image description
            await _safe_reply(message, response)
    except TelegramBadRequest as e:
        logger.error(f"Photo handler Telegram error: {e}")
        await _safe_reply(message, f"⚠️ Couldn't process image: {e}")
    except Exception as e:
        logger.error(f"Photo handler error: {e}")
        await _safe_reply(message, "🖼️ Vision temporarily unavailable. Please try again later.")


# ---------------------------------------------------------------------------
# Handlers — Voice Message (STT → Animation)
# ---------------------------------------------------------------------------

@dp.message(F.voice)
async def handle_voice(message: types.Message) -> None:
    """Voice message handler — transcribe to text, then animate."""
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        from stt import transcribe_voice

        voice = message.voice
        file = await bot.get_file(voice.file_id)
        file_bytes = await bot.download_file(file.file_path)

        # Save to temp file for transcription
        temp_dir = Path("tmp") / "voice"
        temp_dir.mkdir(parents=True, exist_ok=True)
        ogg_path = temp_dir / f"voice_{message.chat.id}_{voice.file_unique_id}.ogg"
        ogg_path.write_bytes(file_bytes.read())

        await _safe_reply(message, "🎤 Transcribing voice message...")

        text = await transcribe_voice(ogg_path)
        ogg_path.unlink(missing_ok=True)

        if text:
            await _safe_reply(message, f"📝 Recognized: _\"{text}\"_\n\nGenerating animation...")
            is_3d = any(w in text.lower() for w in ("3d", "three-dimensional"))
            await _send_animation(message, text, is_3d=is_3d)
        else:
            await _safe_reply(message, "⚠️ Could not transcribe voice message. Please send text instead.")
    except ImportError:
        await _safe_reply(message, "⚠️ Speech-to-text not available. Please install: `pip install SpeechRecognition`")
    except TelegramBadRequest as e:
        logger.error(f"Voice handler Telegram error: {e}")
        await _safe_reply(message, f"⚠️ Couldn't process voice: {e}")
    except Exception as e:
        logger.error(f"Voice handler error: {e}")
        await _safe_reply(message, "🎤 Voice processing temporarily unavailable. Please send text instead.")


# ---------------------------------------------------------------------------
# Handlers — Callback Query (Inline Buttons)
# ---------------------------------------------------------------------------

@dp.callback_query(F.data.startswith("feedback:"))
async def handle_feedback_callback(callback: types.CallbackQuery) -> None:
    """Handle 👍/👎 feedback button clicks."""
    parts = callback.data.split(":")
    # feedback:up:task_id or feedback:down:task_id
    if len(parts) != 3:
        return

    direction = parts[1]
    task_id = parts[2]
    chat_id = callback.from_user.id

    # Look up task to get prompt
    task = render_queue.get_task(task_id)
    prompt = task.prompt if task else "unknown"

    if direction == "up":
        log_feedback(chat_id, prompt, task_id, "thumbs_up")
        await callback.answer("👍 Thanks for the feedback!", show_alert=False)
    else:
        log_feedback(chat_id, prompt, task_id, "thumbs_down")
        await callback.answer("👎 Thanks — we'll use this to improve quality!", show_alert=False)


@dp.callback_query(F.data.startswith("code:"))
async def handle_code_callback(callback: types.CallbackQuery) -> None:
    """Show the generated code for an animation."""
    task_id = callback.data.split(":", 1)[1]
    task = render_queue.get_task(task_id)
    if not task:
        await callback.answer("Task not found", show_alert=True)
        return

    # Try to get code from database first, then renderer
    code = get_last_generated_code(callback.from_user.id)
    if not code:
        await callback.answer("Code not available", show_alert=True)
        return

    if len(code) > 3800:
        code = code[:3800] + "\n\n# ... truncated"

    # Telegram alerts are capped at 200 chars — send the full code as a
    # formatted message instead of truncating it into a tiny toast.
    await callback.answer("🐍 Sending the code…", show_alert=False)
    await _safe_answer(callback.message, f"🐍 **Generated Code:**\n```python\n{code}\n```")


@dp.callback_query(F.data.startswith("edit:"))
async def handle_edit_callback(callback: types.CallbackQuery) -> None:
    """Prompt user to send edit instructions."""
    await callback.answer("Reply to this video with your changes (e.g. 'make it slower' or 'use blue theme')", show_alert=True)


# ---------------------------------------------------------------------------
# Handlers — Text (Intent Router)
# ---------------------------------------------------------------------------

@dp.message(F.text)
async def handle_text(message: types.Message) -> None:
    """Main text router: intent classification → ANIMATE or CHAT or EDIT."""
    text = message.text.strip()
    if not text:
        return

    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    chat_id = message.chat.id
    user_provider = user_settings.get(chat_id, "provider")

    # Check if this is a reply to a previous animation (follow-up edit)
    if message.reply_to_message and message.reply_to_message.video:
        # User replied to an animation with edit instructions
        last_render = db.get_last_render(chat_id)
        if last_render and last_render.get("code"):
            original_prompt = last_render.get("prompt", "")
            last_code = last_render.get("code", "")
            await _safe_reply(message, f"✏️ Editing animation: _\"{original_prompt[:60]}...\"_\n\nApplying: _\"{text[:80]}\"_")
            # Edit-by-diff: start from the prior code and apply only the change,
            # preserving the animation the user already liked.
            is_3d = any(w in (original_prompt + " " + text).lower() for w in ("3d", "three-dimensional"))
            await _send_animation(
                message, original_prompt, is_3d=is_3d,
                edit_base_code=last_code, edit_instruction=text,
            )
            return
        # No code available, treat as normal message
        logger.warning("Reply to video but no code in DB — treating as normal chat")

    intent = await _classify_intent(text, chat_id)

    if intent == "ANIMATE":
        is_3d = any(w in text.lower() for w in ("3d", "three-dimensional"))
        await _send_animation(message, text, is_3d=is_3d)
    else:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful AI assistant integrated into a Telegram bot. "
                    "Be concise, friendly, and helpful. Use Markdown for formatting. "
                    "If the user asks about animations or Manim, you can explain concepts "
                    "but remind them to send animation requests for me to generate videos."
                ),
            },
            {"role": "user", "content": text},
        ]
        try:
            response = await chat(messages, provider=user_provider)
            await _safe_reply(message, response)
        except Exception as e:
            logger.error(f"Chat handler error: {e}")
            await _safe_reply(message, f"⚠️ Chat temporarily unavailable: {e}")


# ---------------------------------------------------------------------------
# Startup

def _get_feedback_stats() -> dict:
    """Get feedback statistics for /stats display."""
    try:
        from feedback import get_feedback_stats as _get_stats
        return _get_stats()
    except Exception:
        return {"thumbs_up": 0, "thumbs_down": 0, "total": 0, "positive_rate": 0}


def _get_error_pattern_stats() -> dict:
    """Get error pattern statistics."""
    try:
        from error_learner import get_error_stats
        return get_error_stats()
    except Exception:
        return {"total_errors": 0, "by_category": {}}


# ---------------------------------------------------------------------------

async def _analytics_flush_loop():
    """Persist analytics to disk every 5 minutes."""
    try:
        while True:
            await asyncio.sleep(300)
            try:
                analytics.flush()
            except Exception:
                pass
    except asyncio.CancelledError:
        # Final flush on shutdown
        try:
            analytics.flush()
        except Exception:
            pass


async def main() -> None:
    await d1.init()
    logger.info("Starting Manim Animation Bot + AI Assistant…")
    logger.info(f"Code gen: {GPT_MODEL} (reasoning: {GPT_REASONING_EFFORT})")
    logger.info(f"Chat:    {CHAT_MODEL}")
    logger.info(f"Cloud:   D1 {'enabled' if D1_ENABLED else 'disabled (graceful fallback)'}")
    logger.info(f"TTS:     {'enabled' if VOICEOVER_ENABLED else 'disabled'} ({TTS_VOICE})")
    logger.info("Polling started — waiting for messages")

    # Start analytics flusher as background task (tracked for shutdown)
    _analytics_task = asyncio.create_task(_analytics_flush_loop())

    try:
        await dp.start_polling(bot)
    finally:
        _analytics_task.cancel()
        try:
            await _analytics_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
