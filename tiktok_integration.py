"""TikTok mode integration for Manim bot.

Usage:
1. User sends message with TikTok keywords
2. Bot detects TikTok mode automatically
3. Uses TikTok-optimized prompt and renders in 9:16 format

Integration points:
- Detect TikTok mode in message handler
- Pass tiktok_mode=True to renderer
- Use prompt_builder_tiktok for code generation
"""

def detect_tiktok_mode(user_message: str) -> bool:
    """Detect if user wants TikTok format video.
    
    Keywords:
    - tiktok, TikTok, tt
    - vertical, portrait, 9:16
    - reels, shorts (Instagram/YouTube shorts use same 9:16 format)
    - mobile
    """
    message_lower = user_message.lower()
    
    tiktok_keywords = [
        "tiktok", "tikotk", "tt",
        "vertical", "portrait", "9:16", "9/16",
        "reels", "shorts", "reel", "short",
        "mobile", "phone", "smartphone"
    ]
    
    return any(keyword in message_lower for keyword in tiktok_keywords)


# ============================================================================
# PATCH INSTRUCTIONS FOR bot.py
# ============================================================================

"""
1. Add import at top of bot.py:
   
   from prompt_builder_tiktok import get_tiktok_prompt

2. In the main message handler (around line 400-500), detect TikTok mode:
   
   # Detect format
   tiktok_mode = detect_tiktok_mode(user_text)
   if tiktok_mode:
       await message.reply("🎬 TikTok mode activated! Generating vertical video (9:16)...")
   
3. When generating code, use TikTok prompt if enabled:
   
   if tiktok_mode:
       from prompt_builder_tiktok import get_tiktok_prompt
       prompt = get_tiktok_prompt(user_text)
   else:
       from prompt_builder import build_prompt
       prompt = build_prompt(user_text, theme_context)
   
   code = await generate_manim_code(prompt, chat_id, ...)
   
4. Pass tiktok_mode to renderer:
   
   video_path = await render(
       code=code,
       chat_id=chat_id,
       timeout=MANIM_TIMEOUT,
       tiktok_mode=tiktok_mode  # <-- ADD THIS
   )
   
5. Update progress messages:
   
   if tiktok_mode:
       status_text = "🎬 Rendering TikTok video (1080x1920)..."
   else:
       status_text = "🎬 Rendering animation..."
"""

# ============================================================================
# EXAMPLE: Complete integration in message handler
# ============================================================================

"""
@dp.message(F.text)
async def handle_message(message: types.Message):
    user_text = message.text.strip()
    chat_id = message.chat.id
    
    # 1. Detect TikTok mode
    tiktok_mode = detect_tiktok_mode(user_text)
    
    # 2. Notify user
    if tiktok_mode:
        await message.reply("🎬 TikTok mode activated! Vertical format (9:16)")
    
    # 3. Generate code with appropriate prompt
    if tiktok_mode:
        from prompt_builder_tiktok import get_tiktok_prompt
        prompt = get_tiktok_prompt(user_text)
    else:
        from prompt_builder import build_prompt
        theme = get_theme(chat_id)
        prompt = build_prompt(user_text, build_theme_prompt(theme))
    
    code = await generate_manim_code(
        prompt=prompt,
        chat_id=chat_id,
        ...
    )
    
    # 4. Render with TikTok flag
    video_path = await render(
        code=code,
        chat_id=chat_id,
        timeout=MANIM_TIMEOUT,
        tiktok_mode=tiktok_mode  # PASS FLAG HERE
    )
    
    # 5. Send video with format info
    caption = "✅ Animation ready!"
    if tiktok_mode:
        caption += "\\n📱 TikTok format (9:16, 1080x1920)"
    
    await message.answer_video(
        video=FSInputFile(video_path),
        caption=caption
    )
"""
