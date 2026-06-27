"""Speech-to-text for Telegram voice messages.

Uses the speech_recognition library with Google's free Whisper backend.
Falls back to sending the voice text as-is if transcription fails.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import imageio_ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

logger = logging.getLogger(__name__)

try:
    import speech_recognition as sr
    _SR_AVAILABLE = True
except ImportError:
    logger.warning("speech_recognition not installed — voice messages will use fallback")
    _SR_AVAILABLE = False


async def transcribe_voice(ogg_path: Path) -> str | None:
    """Transcribe a Telegram voice message (OGG Opus) to text.

    Converts OGG → WAV first, then uses speech_recognition.
    Returns transcribed text or None on failure.
    """
    if not _SR_AVAILABLE:
        logger.warning("STT not available — voice message will be skipped")
        return None

    try:
        import subprocess

        # Convert OGG Opus → WAV for speech_recognition
        wav_path = ogg_path.with_suffix(".wav")
        cmd = [
            FFMPEG, "-y",
            "-i", str(ogg_path),
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(wav_path),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=0x08000000,
        )
        await proc.communicate()
        if proc.returncode != 0:
            logger.warning("OGG→WAV conversion failed")
            return None

        # Transcribe using Google's free Whisper via speech_recognition
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _recognize, wav_path)

        # Cleanup
        wav_path.unlink(missing_ok=True)
        return result

    except Exception as e:
        logger.error(f"STT transcription failed: {e}")
        return None


def _recognize(wav_path: Path) -> str | None:
    """Synchronous speech recognition."""
    r = sr.Recognizer()
    with sr.AudioFile(str(wav_path)) as source:
        audio = r.record(source)
    try:
        # Google's free Whisper via speech_recognition
        text = r.recognize_google(audio)
        logger.info(f"STT result: {text[:100]}")
        return text
    except sr.UnknownValueError:
        logger.warning("STT could not understand audio")
        return None
    except sr.RequestError as e:
        logger.warning(f"STT service error: {e}")
        return None
