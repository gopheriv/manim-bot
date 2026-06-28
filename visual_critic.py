"""Visual critic — render → SEE the pixels → critique → regenerate guidance.

Every other reviewer in this bot reads the *source code* as text. A visual
medium's quality (overlap, cropping, readability, clutter/"AI slop",
composition, colour harmony, dead frames) can only be judged by looking at the
rendered image. This module extracts keyframes from the finished video and has a
vision model score the actual frames, returning concrete guidance the generator
can act on.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import imageio_ffmpeg

from config import VISION_PROVIDER, VISUAL_CRITIC_KEYFRAMES
from llm import chat_with_images
from voiceover import _get_duration  # reuse the ffprobe/ffmpeg duration helper

logger = logging.getLogger("visual_critic")

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
CREATE_NO_WINDOW = 0x08000000


@dataclass
class VisualVerdict:
    passed: bool
    score: float
    issues: list[str] = field(default_factory=list)
    regenerate_guidance: str = ""


VISUAL_CRITIC_PROMPT = """You are a strict art director reviewing FRAMES (in time order) from a rendered Manim math animation.

Judge ONLY what you can SEE in the images. Look hard for these defects:
- Overlapping objects, or text drawn on top of other text/shapes
- A label/text panel drawn ON TOP OF or crossing into the main figure
- Doubled / ghosted outlines — a shape drawn twice as an offset duplicate (looks broken)
- Objects or labels cut off at the edges of the frame (off-screen)
- A box/rectangle whose edge clips, touches, or crosses the text inside it
- Muddy or clashing translucent fills (e.g. a warm/yellow fill over a cool/blue object → brown)
- Inconsistent colours on one structure (e.g. grid lines that are part cyan, part yellow)
- A lone moving dot / marker with no visible trail or purpose, or one that ends on top of text
- Unreadable text: too small, too low-contrast against the background, or crowded
- Clutter / messy "AI slop" — disorganised composition, random-looking placement
- Poor use of the frame (everything cramped in the centre, or large empty dead zones)
- A frame that looks frozen/empty (no meaningful content)

Score the overall VISUAL quality from 0-10 (10 = clean, balanced, readable, professional).
Be strict: any doubled outline, muddy fill, panel-over-figure overlap, or stray marker caps the score at 6.

Return ONLY valid JSON, no markdown fences:
{"score": N, "pass": true/false, "issues": ["specific visible problem", ...], "regenerate_guidance": "concrete, actionable fixes the code author should make (positions, font sizes, spacing, fade-outs, colours)"}

Set "pass" to true ONLY if score >= 7 AND there is no overlap, no doubled outline, no cropping, no muddy fill, and all text is readable.
"""


def _grab_frame(video_path: str, t: float) -> bytes | None:
    """Grab a single JPEG frame at time t (seconds) via ffmpeg, returned as bytes."""
    try:
        proc = subprocess.run(
            [
                FFMPEG, "-nostdin", "-ss", f"{t:.2f}", "-i", video_path,
                "-frames:v", "1", "-vf", "scale=720:-1",
                "-f", "image2pipe", "-vcodec", "mjpeg", "-",
            ],
            capture_output=True, timeout=25, creationflags=CREATE_NO_WINDOW,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
        logger.warning("ffmpeg frame grab at %.2fs returned no data (rc=%s)", t, proc.returncode)
    except Exception as e:
        logger.warning("Keyframe grab failed at %.2fs: %s", t, e)
    return None


async def extract_keyframes(video_path: Path | str, n: int | None = None) -> list[bytes]:
    """Extract N evenly-spaced keyframes (as JPEG bytes) across the video."""
    n = n or VISUAL_CRITIC_KEYFRAMES
    video_path = Path(video_path)
    dur = await _get_duration(video_path)
    if dur <= 0:
        dur = 12.0
    frames: list[bytes] = []
    for i in range(n):
        t = dur * (i + 0.5) / n  # sample frame centres, avoid the very first/last frame
        data = await asyncio.to_thread(_grab_frame, str(video_path), t)
        if data:
            frames.append(data)
    return frames


def _parse_json(raw: str) -> dict | None:
    if not raw:
        return None
    text = re.sub(r"^```[a-z]*\n?", "", raw.strip(), flags=re.MULTILINE)
    text = re.sub(r"\n?```$", "", text.strip(), flags=re.MULTILINE)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to salvage the first JSON object in the text
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
        return None


async def critique_render(video_path: Path | str, prompt: str, code: str = "") -> VisualVerdict | None:
    """Extract frames and have a vision model critique the actual rendered pixels.

    Returns a VisualVerdict, or None if frames couldn't be extracted / parsed
    (the caller treats None as "skip" — non-fatal).
    """
    frames = await extract_keyframes(video_path)
    if not frames:
        logger.warning("Visual critic: no frames extracted, skipping")
        return None

    caption = (
        f"{VISUAL_CRITIC_PROMPT}\n\nThe animation was requested as: \"{prompt}\".\n"
        f"Here are {len(frames)} frames in chronological order. Return the JSON verdict."
    )
    try:
        raw = await chat_with_images(frames, caption, provider=VISION_PROVIDER)
    except Exception as e:
        logger.warning("Visual critic vision call failed (non-fatal): %s", e)
        return None

    data = _parse_json(raw)
    if not data:
        logger.warning("Visual critic returned unparseable verdict: %s", (raw or "")[:200])
        return None

    try:
        score = float(data.get("score", 5))
    except (TypeError, ValueError):
        score = 5.0
    issues = [str(i) for i in (data.get("issues") or [])]
    guidance = str(data.get("regenerate_guidance", "") or "")
    passed = bool(data.get("pass", score >= 7 and not issues))

    verdict = VisualVerdict(passed=passed, score=score, issues=issues, regenerate_guidance=guidance)
    logger.info(
        "Visual critic verdict: score=%.1f passed=%s issues=%d", score, passed, len(issues)
    )
    return verdict
