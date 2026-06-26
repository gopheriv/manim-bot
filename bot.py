"""Manim Animation Bot вЂ” Telegram bot with Qwen 3.7 Max code gen, Qwen 3.6 chat,
edge-tts voiceover, themes, queue management, rate limiting, and D1 caching."""

import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path

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
)
from database import db
from fallback_scene import build_fallback_scene
from llm import classify_intent, chat, chat_with_image, generate_manim_code, fix_manim_code, generate_scene_plan, repair_layout, strip_code_fences, fill_template_config
from scene_planner import parse_scene_plan, format_plan_for_prompt
from scene_validator import validate_layout, has_issues
from markdown_utils import strip_markdown
from queue_manager import render_queue, TaskStatus
from rate_limiter import rate_limiter
from renderer import render, cleanup, get_last_generated_code
import settings as user_settings
from themes import get_theme, next_theme, build_theme_prompt, THEME_ORDER
from voiceover import add_voiceover
from templates import get_registry

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
    """Send a text reply with Markdown safety вЂ” falls back to plain text on parse errors."""
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


async def _safe_edit(message: types.Message, text: str, **kwargs) -> None:
    """Edit a message with Markdown safety вЂ” falls back to plain text on parse errors."""
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
    return "в–€" * filled + "в–‘" * (width - filled)


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
    """Send periodic chat action updates while render/narration run in parallel.
    If status_message is provided, also update the text with a progress bar.
    """
    actions = [
        (ChatAction.RECORD_VIDEO, "рџЋ¬ Rendering animationвЂ¦"),
        (ChatAction.RECORD_VIDEO, "рџЋЁ Drawing framesвЂ¦"),
        (ChatAction.UPLOAD_VIDEO, "вЏі FinalizingвЂ¦"),
    ]
    idx = 0
    start_time = asyncio.get_running_loop().time()
    try:
        while not (render_task.done() and (narration_task is None or narration_task.done())):
            action, label = actions[idx % len(actions)]
            try:
                await bot.send_chat_action(chat_id, action)
            except Exception:
                pass

            # Update progress bar text every 30s
            if status_message and idx % 2 == 0:
                elapsed = int(asyncio.get_running_loop().time() - start_time)
                progress_bar = _render_progress_bar(elapsed)
                try:
                    await status_message.edit_text(progress_bar, parse_mode=ParseMode.MARKDOWN)
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
        logger.debug(f"LLM intent: '{cleaned}' в†’ {result}")
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
) -> None:
    """Full animation pipeline with queue, themes, self-healing, and caching."""
    chat_id = message.chat.id

    # Rate limiting
    allowed, retry_after = rate_limiter.check_rate_limit(chat_id, "animate")
    if not allowed:
        await _safe_reply(message, f"вЏі Rate limit reached. Try again in {retry_after}s.")
        return

    # Check for existing task
    existing = render_queue.get_user_task(chat_id)
    if existing:
        await _safe_reply(message, f"вЏі You already have a render in progress: `{existing.prompt[:50]}вЂ¦`")
        return

    # Get user settings
    user_quality = quality or user_settings.get(chat_id, "quality") or MANIM_QUALITY
    user_theme = theme_name or user_settings.get(chat_id, "theme") or "visual_math"
    user_voiceover = user_settings.get(chat_id, "voiceover_enabled")
    user_voice = user_settings.get(chat_id, "tts_voice") or TTS_VOICE
    user_rate = user_settings.get(chat_id, "tts_rate") or TTS_RATE
    theme = get_theme(user_theme)

    await bot.send_chat_action(chat_id, ChatAction.RECORD_VIDEO)

    # Submit to queue
    task = await render_queue.submit_task(chat_id, prompt, is_3d=is_3d, quality=user_quality)

    # D1 cache check
    try:
        cached_file_id = await d1.check_cache(chat_id, prompt)
        if cached_file_id:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            await message.reply_video(video=cached_file_id, caption="вљЎ Cached result")
            logger.info(f"Animation done вЂ” chat_id={chat_id}, cache HIT")
            return
    except Exception as e:
        logger.warning(f"Cache check failed (degraded): {e}")

    # Acquire semaphore (blocks if another render is running)
    async with render_queue.semaphore:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()

        try:
            # ── TEMPLATE MATCHING: try fast path before full code gen ──
            template_match = get_registry().match(prompt)
            code: str = ""

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
                    # Generate code from template (deterministic, no LLM)
                    code = template_match.template.generate_code(config)
                    logger.info(
                        "Template %s generated code (%d chars) in config-fill mode",
                        template_match.template.name, len(code),
                    )

            if not code:
                # Slow path: full LLM code generation
                await _safe_reply(message, (
                    f"🤖 Generating Manim code with **{GPT_MODEL}**…\n"
                    f"🎨 Theme: **{theme.name}** | Quality: `{user_quality}`"
                ))

                # Build theme-aware system prompt
                theme_prompt = build_theme_prompt(theme)

                # ── Scene Awareness: plan → generate → validate → repair ──
                # Step 1: Generate scene composition plan (non-fatal on failure)
                scene_plan_json: str = ""
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

                # Step 4: Layout repair вЂ” fix ONLY spatial/timing, preserve creative metaphor
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

            # в”Ђв”Ђ Parallel: render + narration generation в”Ђв”Ђ
            render_start = datetime.now()

            # Status message that gets updated with real Manim progress
            status_msg = await message.reply("рџЋ¬ Preparing renderвЂ¦")

            # Check scene weight before rendering (for user info)
            from renderer import _estimate_scene_weight
            weight = _estimate_scene_weight(code)
            if weight.is_heavy:
                await _safe_edit(status_msg, "вљ пёЏ Heavy scene detected вЂ” auto-optimizing for your hardwareвЂ¦")
                await asyncio.sleep(0.5)  # Let user see the warning
            _render_progress = {"pct": 0, "anim": ""}

            def _on_manim_progress(pct: int, anim_name: str) -> None:
                """Callback from renderer вЂ” updates Telegram status message."""
                _render_progress["pct"] = pct
                _render_progress["anim"] = anim_name
                bar = _build_progress_bar(pct)
                asyncio.create_task(
                    _safe_edit(status_msg, f"рџЋ¬ *RenderingвЂ¦*\n{bar} {pct}%\nрџЋћпёЏ `{anim_name[:40]}`")
                )

            render_coro = render(
                code, chat_id, timeout=MANIM_TIMEOUT, quality=user_quality,
                cancel_event=task.cancel_event, progress_cb=_on_manim_progress,
            )

            if user_voiceover and VOICEOVER_ENABLED:
                # Launch both in parallel вЂ” saves ~15-30s
                render_task = asyncio.create_task(render_coro)
                narration_task = asyncio.create_task(_generate_narration(prompt))

                # Periodic progress updates while waiting вЂ” edit bot's own message
                progress_task = asyncio.create_task(_progress_loop(chat_id, render_task, narration_task, status_msg))

                video_path = await render_task
                narration = await narration_task
                progress_task.cancel()
            else:
                # No voiceover вЂ” still show progress
                render_task = asyncio.create_task(render_coro)
                progress_task = asyncio.create_task(_progress_loop(chat_id, render_task, None, status_msg))
                video_path = await render_task
                progress_task.cancel()
                narration = None

            # Check if user cancelled
            if task.is_cancelled():
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                await _safe_reply(message, "вќЊ Render cancelled.")
                return

            # Self-healing: up to 2 retries with escalating simplification
            if video_path is None and render._last_error and MANIM_MAX_RETRIES > 0:
                error_msg = render._last_error
                if "cancelled" not in error_msg.lower():
                    for heal_attempt in range(1, MANIM_MAX_RETRIES + 1):
                        logger.info("Render failed вЂ” self-healing attempt %d/%d", heal_attempt, MANIM_MAX_RETRIES)
                        await _safe_reply(message, f"рџ”§ Render failed, asking Qwen 3.7 Max to fix the code (attempt {heal_attempt})вЂ¦")

                        try:
                            fixed_code = await fix_manim_code(prompt, error_msg, theme_prompt)
                            if fixed_code and fixed_code.strip():
                                fixed_code = strip_code_fences(fixed_code)
                                video_path = await render(
                                    fixed_code, chat_id, timeout=MANIM_TIMEOUT, quality=user_quality,
                                    cancel_event=task.cancel_event, progress_cb=_on_manim_progress,
                                )
                                if video_path:
                                    code = fixed_code
                                    break
                                # Second attempt: simplify if first repair also failed
                                if heal_attempt == 1:
                                    error_msg = render._last_error or error_msg
                                    await _safe_reply(message, "рџ”§ Still failing вЂ” trying a simpler versionвЂ¦")
                                    fixed_code = await fix_manim_code(
                                        prompt,
                                        f"Previous repair also failed. SIMPLIFY the scene: reduce object count, remove heavy updaters, fewer self.play() calls, shorter duration. Error: {error_msg}",
                                        theme_prompt,
                                    )
                                    if fixed_code and fixed_code.strip():
                                        fixed_code = strip_code_fences(fixed_code)
                                        video_path = await render(
                                            fixed_code, chat_id, timeout=MANIM_TIMEOUT, quality=user_quality,
                                            cancel_event=task.cancel_event, progress_cb=_on_manim_progress,
                                        )
                                        if video_path:
                                            code = fixed_code
                                            break
                        except Exception as e:
                            logger.error(f"Self-healing attempt {heal_attempt} failed: {e}")

            # Check cancellation again after self-heal
            if task.is_cancelled():
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                await _safe_reply(message, "вќЊ Render cancelled.")
                return

            # Deterministic fallback: never fail a user request just because generated code is brittle.
            if video_path is None:
                error_detail = render._last_error or "Unknown error"
                logger.warning("LLM render failed after repair; using deterministic fallback. Last error: %s", error_detail[:700])
                await _safe_reply(message, "рџ›џ Generated code was unstable, rendering a safe fallback animation insteadвЂ¦")
                fallback_code = build_fallback_scene(prompt, bg_color=theme.bg_color)
                video_path = await render(
                    fallback_code, chat_id, timeout=min(MANIM_TIMEOUT, 180), quality="-ql",
                    cancel_event=task.cancel_event, progress_cb=_on_manim_progress,
                )
                if video_path:
                    code = fallback_code
                else:
                    if task.is_cancelled():
                        task.status = TaskStatus.CANCELLED
                        task.completed_at = datetime.now()
                        await _safe_reply(message, "вќЊ Render cancelled.")
                        return
                    error_display = (render._last_error or error_detail or "Unknown error")[:500]
                    task.status = TaskStatus.FAILED
                    task.error_message = error_display
                    task.completed_at = datetime.now()
                    analytics.log_render_failure(chat_id, "render_failed")
                    await _safe_reply(message, (
                        f"вќЊ Animation failed after generated, repaired, and fallback attempts.\n\n"
                        f"**Error:**\n```\n{error_display}\n```"
                    ))
                    return

            # Record render success
            render_time = (datetime.now() - render_start).total_seconds()
            analytics.log_render_success(chat_id, render_time)

            # Voiceover merge (narration already generated in parallel)
            if narration and VOICEOVER_ENABLED:
                try:
                    await bot.send_chat_action(chat_id, ChatAction.RECORD_VOICE)
                    vo_dir = Path("tmp") / "voiceover" / str(chat_id)
                    narrated = await add_voiceover(
                        video_path, narration, vo_dir,
                        voice=user_voice, rate=user_rate,
                    )
                    if narrated:
                        video_path = narrated
                except Exception as e:
                    logger.warning(f"Voiceover merge failed (non-fatal): {e}")

            # Send result
            await bot.send_chat_action(chat_id, ChatAction.UPLOAD_VIDEO)
            reasoning_tag = f" | {GPT_REASONING_EFFORT} reasoning" if GPT_REASONING_EFFORT else ""
            video_file = FSInputFile(str(video_path))
            sent = await message.reply_video(
                video=video_file,
                caption=f"рџЋ¬ `{GPT_MODEL}` | {theme.name}{reasoning_tag}",
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

            # Save to D1 cache
            if telegram_file_id:
                asyncio.create_task(
                    d1.save_render(chat_id, prompt, code, telegram_file_id)
                )

            logger.info(f"Animation done вЂ” chat_id={chat_id}, prompt={prompt[:50]}вЂ¦")

        except Exception as e:
            logger.error(f"Animation pipeline error: {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.now()
            analytics.log_render_failure(chat_id, "pipeline_error")
            await _safe_reply(message, f"вљ пёЏ Animation failed: {e}")


async def _generate_narration(prompt: str) -> str:
    """Generate TTS narration text via Qwen."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a narrator for short mathematical animations. Given the animation "
                "description, write a tight 12-18 second narration script, maximum 45 words. "
                "Use vivid language, but do not over-explain. Match a 12-20 second video so "
                "the last frame is not frozen for extra audio. Output ONLY the narration text, "
                "no markdown or stage directions."
            ),
        },
        {"role": "user", "content": f"Animation: {prompt}"},
    ]
    try:
        text = await chat(messages)
        return text.strip() if text and not text.startswith("вљ пёЏ") else None
    except Exception as e:
        logger.warning(f"Narration generation failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Handlers вЂ” Commands
# ---------------------------------------------------------------------------

@dp.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    user_provider = user_settings.get(message.chat.id, "provider")
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
        "• `/cancel` → cancel current render\n\n"
        "Try: *Animate why matrix multiplication is function composition*"
    ))


@dp.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    await cmd_start(message)


@dp.message(Command("clean"))
async def cmd_clean(message: types.Message) -> None:
    cleanup()
    render_queue.cleanup_old_tasks()
    await _safe_answer(message, "рџ§№ Render cache cleaned.")


@dp.message(Command("history"))
async def cmd_history(message: types.Message) -> None:
    """Show last 10 animations for this user."""
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        records = db.get_user_history(message.chat.id, limit=10)
        if not records:
            await _safe_reply(message, "рџ“­ No animation history yet. Try `/animation rotating cube`!")
            return

        lines = ["рџ“њ **Your Recent Animations:**\n"]
        for i, rec in enumerate(records, 1):
            prompt = rec.get("prompt", "unknown")[:50]
            status = rec.get("status", "unknown")
            theme = rec.get("theme", "default")
            emoji = "вњ…" if status == "completed" else "вќЊ" if status == "failed" else "вЏі"
            lines.append(f"{i}. {emoji} `{prompt}` вЂ” _{theme}_")
        lines.append(f"\n**Total:** {len(records)} animation(s)")
        await _safe_reply(message, "\n".join(lines))
    except Exception as e:
        logger.error(f"History error: {e}")
        await _safe_reply(message, f"вљ пёЏ Couldn't fetch history: {e}")


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
            await _safe_reply(message, "рџ“­ No code available yet. Try `/animation rotating cube` first!")
            return

        if len(code) > 3800:
            code = code[:3800] + "\n\n# ... truncated"

        await _safe_answer(message, f"рџђЌ **Last Generated Code:**\n```python\n{code}\n```")
    except Exception as e:
        logger.error(f"Code fetch error: {e}")
        await _safe_reply(message, f"вљ пёЏ Couldn't fetch code: {e}")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message) -> None:
    """Show global and per-user statistics."""
    try:
        global_stats = db.get_stats()
        user_stats = analytics.get_user_stats(message.chat.id)
        render_stats = analytics.get_render_stats()
        top_errors = analytics.get_top_errors(limit=5)

        lines = [
            "рџ“Љ **Bot Statistics**\n",
            f"**Global:** {global_stats['total']} renders | "
            f"{global_stats['completed']} вњ… | {global_stats['failed']} вќЊ | "
            f"{global_stats['unique_users']} users",
            f"**You:** {user_stats['renders']} renders | "
            f"{user_stats['success']} вњ… | {user_stats['failed']} вќЊ",
            f"**Avg render time:** {render_stats['avg_render_time']:.1f}s",
            f"**Success rate:** {render_stats['success_rate']:.1f}%",
        ]

        if top_errors:
            lines.append("\n**Top Errors (24h):**")
            for err_type, count in top_errors:
                lines.append(f"  вЂў `{err_type}`: {count}")

        await _safe_reply(message, "\n".join(lines))
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await _safe_reply(message, f"вљ пёЏ Couldn't fetch stats: {e}")


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
    await _safe_reply(message, f"рџЋЁ Theme set to **{theme.name}**\n\n_{theme.palette_desc[:100]}вЂ¦_")


@dp.message(Command("settings"))
async def cmd_settings(message: types.Message) -> None:
    """Show current per-user settings."""
    try:
        s = user_settings.get_all(message.chat.id)
        theme = get_theme(s.get("theme", "visual_math"))
        provider_name = "Claude Opus 4.8" if s.get("provider") == "claude" else "Qwen 3.6 Plus"
        lines = [
            "вљ™пёЏ **Your Settings**\n",
            f"**Theme:** {theme.name}",
            f"**Style:** visual intuition в†’ transformation в†’ insight в†’ recap",
            f"**Quality:** `{s.get('quality', MANIM_QUALITY)}`",
            f"**Chat LLM:** {provider_name}",
            f"**Voiceover:** {'вњ… enabled' if s.get('voiceover_enabled') else 'вќЊ disabled'}",
            f"**TTS Voice:** `{s.get('tts_voice', TTS_VOICE)}`",
            f"**TTS Rate:** `{s.get('tts_rate', TTS_RATE)}`",
            "",
            "**Commands:**",
            "вЂў `/theme` вЂ” cycle visual theme",
            "вЂў `/provider qwen|claude` вЂ” switch chat LLM",
            "вЂў `/voice on|off` вЂ” toggle voiceover",
            "вЂў `/quality -ql|-qm|-qh` вЂ” set render quality",
            "вЂў `/reset` вЂ” revert to defaults",
        ]
        await _safe_reply(message, "\n".join(lines))
    except Exception as e:
        logger.error(f"Settings error: {e}")
        await _safe_reply(message, f"вљ пёЏ Couldn't load settings: {e}")


@dp.message(Command("voice"))
async def cmd_voice(message: types.Message) -> None:
    """Toggle voiceover on/off."""
    args = (message.text or "").replace("/voice", "", 1).strip().lower()
    if args in ("on", "1", "yes", "true"):
        user_settings.set(message.chat.id, "voiceover_enabled", True)
        await _safe_reply(message, "рџ”Љ Voiceover **enabled**")
    elif args in ("off", "0", "no", "false"):
        user_settings.set(message.chat.id, "voiceover_enabled", False)
        await _safe_reply(message, "рџ”‡ Voiceover **disabled**")
    else:
        current = user_settings.get(message.chat.id, "voiceover_enabled")
        await _safe_reply(message, f"Voiceover is currently {'**enabled**' if current else '**disabled**'}.\n\nUsage: `/voice on` or `/voice off`")


@dp.message(Command("quality"))
async def cmd_quality(message: types.Message) -> None:
    """Set render quality."""
    args = (message.text or "").replace("/quality", "", 1).strip()
    valid = {"-l": "вљЎ Preview", "-ql": "рџљЂ Fast", "-qm": "вњ… Standard", "-qh": "рџЋ¬ High"}
    if args in valid:
        user_settings.set(message.chat.id, "quality", args)
        await _safe_reply(message, f"Quality set to **{valid[args]}** (`{args}`)")
    else:
        await _safe_reply(message, "Usage: `/quality -ql` or `-qm` or `-qh`\n\n" +
                          "\n".join(f"  `{k}` вЂ” {v}" for k, v in valid.items()))


@dp.message(Command("provider"))
async def cmd_provider_cmd(message: types.Message) -> None:
    """Switch LLM provider per-user: qwen or claude."""
    args = (message.text or "").replace("/provider", "", 1).strip().lower()
    chat_id = message.chat.id
    current = user_settings.get(chat_id, "provider")
    if args in ("claude", "opus"):
        user_settings.set(chat_id, "provider", "claude")
        await _safe_reply(message, "рџ§  Your LLM switched to **Claude Opus 4.8**")
    elif args in ("qwen", "qwen3"):
        user_settings.set(chat_id, "provider", "qwen")
        await _safe_reply(message, "рџ§  Your LLM switched to **Qwen 3.6 Plus**")
    else:
        await _safe_reply(message,
            f"Your current LLM: **{current.upper()}**\n\n"
            f"Usage: `/provider qwen` or `/provider claude`\n\n"
            f"вЂў `qwen` вЂ” Qwen 3.6 Plus (fast, DashScope)\n"
            f"вЂў `claude` вЂ” Claude Opus 4.8 (high reasoning, Anthropic)"
        )


@dp.message(Command("reset"))
async def cmd_reset(message: types.Message) -> None:
    """Reset per-user settings to defaults."""
    user_settings.reset(message.chat.id)
    await _safe_reply(message, "вљ™пёЏ Settings reset to defaults.")


@dp.message(Command("examples"))
async def cmd_examples(message: types.Message) -> None:
    """Show example animation prompts."""
    examples = get_all_examples()
    lines = ["рџ“љ **Example Animations**\n"]
    current_cat = None
    for i, ex in enumerate(examples):
        if ex.get("category") != current_cat:
            current_cat = ex.get("category")
            lines.append(f"\n**{current_cat}:**")
        dim = "рџЋІ" if ex.get("is_3d") else "рџ“ђ"
        lines.append(f"  {i+1}. {dim} **{ex['name']}** вЂ” _{ex.get('description', '')}_")

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
        await _safe_reply(message, "рџ“­ Example not found. Use `/examples` to see available demos.")
        return

    await _safe_reply(message, f"рџ“ђ Rendering **{example['name']}** in Visual Math styleвЂ¦")
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
            await _safe_reply(message, f"вќЊ Cancelled: `{task.prompt[:50]}вЂ¦`")
            analytics.log_render_cancelled(message.chat.id)
        else:
            await _safe_reply(message, "вљ пёЏ Could not cancel task.")
    else:
        await _safe_reply(message, "рџ“­ No active render task.")


# ---------------------------------------------------------------------------
# Handlers вЂ” WebApp Data (Settings)
# ---------------------------------------------------------------------------

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

        # Validate TTS rate
        if "rate" in data:
            try:
                rate_val = float(str(data["rate"]).replace("%", "").replace("+", "").replace("-", ""))
                if -50 <= rate_val <= 100:
                    updates["tts_rate"] = f"+{data['rate']}" if not str(data["rate"]).startswith("-") else str(data["rate"])
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
            await _safe_reply(message, f"вњ… Settings updated: {', '.join(updates.keys())}")
        else:
            await _safe_reply(message, "вљ пёЏ No valid settings found in data.")

    except json.JSONDecodeError:
        await _safe_reply(message, "вљ пёЏ Invalid settings data format.")
    except Exception as e:
        logger.error(f"WebApp handler error: {e}", exc_info=True)
        await _safe_reply(message, f"вљ пёЏ Couldn't save settings: {e}")


# ---------------------------------------------------------------------------
# Handlers вЂ” Photo (Vision)
# ---------------------------------------------------------------------------

@dp.message(F.photo)
async def handle_photo(message: types.Message) -> None:
    """Photo handler в†’ Qwen vision (multimodal)."""
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)
        image_data = file_bytes.read()
        caption = message.caption or ""

        user_provider = user_settings.get(message.chat.id, "provider")
        response = await chat_with_image(image_data, caption, provider=user_provider)
        await _safe_reply(message, response)
    except TelegramBadRequest as e:
        logger.error(f"Photo handler Telegram error: {e}")
        await _safe_reply(message, f"вљ пёЏ Couldn't process image: {e}")
    except Exception as e:
        logger.error(f"Photo handler error: {e}")
        await _safe_reply(message, "рџ–јпёЏ Vision temporarily unavailable. Please try again later.")


# ---------------------------------------------------------------------------
# Handlers вЂ” Text (Intent Router)
# ---------------------------------------------------------------------------

@dp.message(F.text)
async def handle_text(message: types.Message) -> None:
    """Main text router: intent classification в†’ ANIMATE or CHAT."""
    text = message.text.strip()
    if not text:
        return

    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    chat_id = message.chat.id
    user_provider = user_settings.get(chat_id, "provider")
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
            await _safe_reply(message, f"вљ пёЏ Chat temporarily unavailable: {e}")


# ---------------------------------------------------------------------------
# Startup
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
    logger.info("Starting Manim Animation Bot + AI AssistantвЂ¦")
    logger.info(f"Qwen 3.7 Max: {GPT_MODEL} (reasoning: {GPT_REASONING_EFFORT})")
    logger.info(f"Chat:    {CHAT_MODEL}")
    logger.info(f"Cloud:   D1 {'enabled' if D1_ENABLED else 'disabled (graceful fallback)'}")
    logger.info(f"TTS:     {'enabled' if VOICEOVER_ENABLED else 'disabled'} ({TTS_VOICE})")
    logger.info("Polling started вЂ” waiting for messages")

    # Start analytics flusher as background task
    asyncio.create_task(_analytics_flush_loop())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
