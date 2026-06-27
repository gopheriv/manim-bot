"""
Voiceover engine — TTS via edge-tts, audio/video merge via ffmpeg.

Produces a narrated .mp4 from a silent Manim render + narration text.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

import edge_tts
import imageio_ffmpeg

from config import TTS_VOICE, TTS_RATE

logger = logging.getLogger("voiceover")

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def _get_duration_sync(path: Path) -> float:
    """Get media duration using ffprobe (fast, no decode)."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=5,
            creationflags=0x08000000,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass
    # Fallback: ffmpeg -i (slower but works)
    result = subprocess.run(
        [FFMPEG, "-i", str(path), "-hide_banner"],
        capture_output=True, text=True, creationflags=0x08000000,
    )
    for line in result.stderr.splitlines():
        if "Duration:" in line:
            time_str = line.split("Duration:")[1].split(",")[0].strip()
            parts = time_str.split(":")
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return 0.0


async def _get_duration(path: Path) -> float:
    """Get media duration asynchronously."""
    return await asyncio.to_thread(_get_duration_sync, path)


def _parse_rate(rate_str: str | None) -> int:
    """Parse an edge-tts rate string like '+10%' / '-20%' into an int percent."""
    try:
        return int(str(rate_str).replace("%", "").replace("+", "").strip())
    except (ValueError, TypeError):
        return 0


def _format_rate(pct: int) -> str:
    """Format an int percent back into an edge-tts rate string."""
    return f"+{pct}%" if pct >= 0 else f"{pct}%"


async def synthesize(text: str, output_path: Path, voice: str | None = None, rate: str | None = None) -> Path | None:
    """Convert text to speech using edge-tts and save as MP3."""
    tts_voice = voice or TTS_VOICE
    tts_rate = rate or TTS_RATE
    logger.info("Synthesizing speech (%d chars, voice=%s, rate=%s)…", len(text), tts_voice, tts_rate)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        communicate = edge_tts.Communicate(text, tts_voice, rate=tts_rate)
        await communicate.save(str(output_path))
        logger.info("TTS saved: %s (%.1f KB)", output_path, output_path.stat().st_size / 1024)
        return output_path
    except Exception:
        logger.error("TTS synthesis failed", exc_info=True)
        return None


async def merge(video_path: Path, audio_path: Path, output_path: Path) -> Path | None:
    """Merge video + audio into a single narrated .mp4.

    If audio is longer than video, pads the video with its last frame.
    If video is longer than audio, the video plays with silence at the end.
    
    Logs warnings for synchronization issues.
    """
    logger.info("Merging %s + %s → %s", video_path.name, audio_path.name, output_path.name)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    video_dur = await _get_duration(video_path)
    audio_dur = await _get_duration(audio_path)
    logger.info("Video: %.1fs, Audio: %.1fs", video_dur, audio_dur)
    
    # Check for synchronization issues
    duration_diff = abs(video_dur - audio_dur)
    if duration_diff > 2.0:
        if audio_dur > video_dur:
            logger.warning(
                f"⚠️ Narration ({audio_dur:.1f}s) is longer than video "
                f"({video_dur:.1f}s) by {duration_diff:.1f}s. "
                f"Video will be padded with frozen last frame."
            )
        else:
            logger.warning(
                f"⚠️ Video ({video_dur:.1f}s) is longer than narration "
                f"({audio_dur:.1f}s) by {duration_diff:.1f}s. "
                f"Video will have silence at the end."
            )

    try:
        if audio_dur > video_dur and video_dur > 0:
            # Pad video to match audio length using tpad filter
            # Use ultrafast preset for 3-4x faster encoding on i5-1155G7
            cmd = [
                FFMPEG,
                "-y",
                "-i", str(video_path),
                "-i", str(audio_path),
                "-filter_complex",
                f"[0:v]tpad=stop_mode=clone:stop_duration={audio_dur - video_dur:.2f}[v]",
                "-map", "[v]",
                "-map", "1:a",
                "-c:v", "libx264",
                "-preset", "ultrafast",  # 3-4x faster than fast
                "-crf", "28",  # slightly lower quality but much faster
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                "-movflags", "+faststart",
                str(output_path),
            ]
        else:
            # Audio <= video: play the FULL video with the narration over the
            # start and trailing silence after. We deliberately omit "-shortest"
            # here — with shorter audio it would cut the video at the audio's end
            # and chop off the animation's closing beats.
            cmd = [
                FFMPEG,
                "-y",
                "-i", str(video_path),
                "-i", str(audio_path),
                "-c:v", "copy",  # BITSTREAM COPY — no re-encode
                "-c:a", "aac",
                "-b:a", "128k",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-movflags", "+faststart",
                str(output_path),
            ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            logger.error("ffmpeg merge failed: %s", stderr.decode(errors="replace")[-500:])
            return None

        logger.info("Merged: %s (%.1f MB)", output_path, output_path.stat().st_size / 1e6)
        return output_path

    except asyncio.TimeoutError:
        logger.error("ffmpeg merge timed out — killing process")
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
        logger.error("ffmpeg merge failed", exc_info=True)
        return None


async def strip_audio(video_path: Path, output_dir: Path) -> Path | None:
    """Remove audio track from video, returning a silent .mp4."""
    silent_path = output_dir / f"{video_path.stem}_silent.mp4"
    silent_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Stripping audio: %s → %s", video_path.name, silent_path.name)

    cmd = [
        FFMPEG,
        "-y",
        "-i", str(video_path),
        "-c:v", "copy",
        "-an",
        "-movflags", "+faststart",
        str(silent_path),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=0x08000000,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

        if proc.returncode != 0:
            logger.error("ffmpeg strip failed: %s", stderr.decode(errors="replace")[-500:])
            return None

        logger.info("Silent video: %s (%.1f MB)", silent_path, silent_path.stat().st_size / 1e6)
        return silent_path

    except asyncio.TimeoutError:
        logger.error("ffmpeg strip timed out — killing process")
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
        logger.error("ffmpeg strip failed", exc_info=True)
        return None


async def video_to_gif(video_path: Path, output_dir: Path) -> Path | None:
    """Convert video to animated GIF."""
    gif_path = output_dir / f"{video_path.stem}.gif"
    gif_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Converting to GIF: %s → %s", video_path.name, gif_path.name)

    # Use ffmpeg with palette generation for better quality
    cmd = [
        FFMPEG,
        "-y",
        "-i", str(video_path),
        "-vf", "fps=10,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
        "-loop", "0",
        str(gif_path),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=0x08000000,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            logger.error("ffmpeg GIF conversion failed: %s", stderr.decode(errors="replace")[-500:])
            return None

        logger.info("GIF created: %s (%.1f MB)", gif_path, gif_path.stat().st_size / 1e6)
        return gif_path

    except asyncio.TimeoutError:
        logger.error("ffmpeg GIF conversion timed out — killing process")
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
        logger.error("ffmpeg GIF conversion failed", exc_info=True)
        return None


async def add_voiceover(
    video_path: Path,
    narration_text: str,
    output_dir: Path,
    voice: str | None = None,
    rate: str | None = None,
    fit_to_video: bool = False,
) -> Path | None:
    """Full pipeline: text → TTS → merge with video → narrated .mp4.

    Returns the path to the narrated video, or None on failure.

    Args:
        voice: Override TTS voice (default: config TTS_VOICE)
        rate: Override TTS rate (default: config TTS_RATE)
        fit_to_video: When True, measure the rendered video and (if the narration
            is much longer/shorter) re-synthesize once at an adjusted speaking
            rate so the audio tracks the animation — instead of forcing a frozen
            tail frame to pad the video to the audio.
    """
    audio_path = output_dir / f"{video_path.stem}_narration.mp3"
    narrated_path = output_dir / f"{video_path.stem}_narrated.mp4"

    tts_voice = voice or TTS_VOICE
    tts_rate = rate or TTS_RATE

    # Step 1: Synthesize speech at the base rate
    audio = await synthesize(narration_text, audio_path, voice=tts_voice, rate=tts_rate)
    if audio is None:
        return None

    # Step 1b: Fit the narration to the video length by adjusting the rate once.
    if fit_to_video:
        try:
            video_dur = await _get_duration(video_path)
            audio_dur = await _get_duration(audio_path)
            if video_dur > 0.5 and audio_dur > 0.5:
                ratio = audio_dur / video_dur
                # Only adjust on a meaningful mismatch (>10% long or >15% short).
                if ratio > 1.10 or ratio < 0.85:
                    base_pct = _parse_rate(tts_rate)
                    delta = round((ratio - 1.0) * 100)  # speak faster if long, slower if short
                    new_pct = max(-40, min(80, base_pct + delta))
                    new_rate = _format_rate(new_pct)
                    if new_rate != tts_rate:
                        logger.info(
                            "Fitting narration to video: audio %.1fs vs video %.1fs "
                            "(ratio %.2f) → rate %s", audio_dur, video_dur, ratio, new_rate,
                        )
                        refit = await synthesize(narration_text, audio_path, voice=tts_voice, rate=new_rate)
                        if refit is not None:
                            audio = refit
        except Exception as e:
            logger.warning("Narration fit-to-video failed (using base rate): %s", e)

    # Step 2: Merge audio + video
    result = await merge(video_path, audio, narrated_path)

    # Clean up temp audio
    try:
        audio_path.unlink(missing_ok=True)
    except Exception:
        pass

    return result
