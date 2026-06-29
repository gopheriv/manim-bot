"""Watermark overlay for rendered videos."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import imageio_ffmpeg

logger = logging.getLogger(__name__)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# Watermark text — can be customized
BOT_HANDLE = "@Manim_is_so_useful_bot"


async def add_watermark(video_path: Path, output_dir: Path | None = None) -> Path | None:
    """Add a semi-transparent watermark to the bottom-right corner.

    Uses ffmpeg drawtext filter with shadow for legibility.
    """
    output_dir = output_dir or video_path.parent
    watermarked_path = output_dir / f"{video_path.stem}_wm{video_path.suffix}"

    logger.info("Adding watermark to %s", video_path.name)

    # drawtext filter with semi-transparent text + shadow
    # Position: bottom-right corner, 10px padding
    cmd = [
        FFMPEG,
        "-y",
        "-i", str(video_path),
        "-vf", (
            f"drawtext="
            f"text='{BOT_HANDLE}':"
            f"fontcolor=white@0.6:"
            f"fontsize=h/40:"
            f"x=w-tw-10:"
            f"y=h-th-10:"
            f"shadowcolor=black@0.8:"
            f"shadowx=1:"
            f"shadowy=1"
        ),
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(watermarked_path),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=CREATE_NO_WINDOW,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            logger.error("Watermark ffmpeg failed: %s", stderr.decode(errors="replace")[-500:])
            return None

        logger.info("Watermarked: %s (%.1f MB)", watermarked_path.name, watermarked_path.stat().st_size / 1e6)
        return watermarked_path

    except asyncio.TimeoutError:
        logger.error("Watermark ffmpeg timed out — killing process")
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        try:
            await proc.wait()
        except Exception:
            pass
        return None
    except Exception:
        logger.error("Watermark failed", exc_info=True)
        return None
