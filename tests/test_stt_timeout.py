"""Regression: stt.transcribe_voice must bound the OGG->WAV ffmpeg conversion.

A malformed/huge voice note can make ffmpeg block on input; without a timeout the
voice-message handler would hang forever. The fix wraps proc.communicate() in
asyncio.wait_for and kills the process on timeout.
"""
from __future__ import annotations

import asyncio

import stt


class _HangingProc:
    def __init__(self):
        self.returncode = None
        self.killed = False

    async def communicate(self):
        await asyncio.sleep(60)  # never returns within the test

    def kill(self):
        self.killed = True

    async def wait(self):
        return 0


def test_conversion_timeout_kills_ffmpeg_and_returns_none(monkeypatch, tmp_path):
    proc = _HangingProc()

    async def _fake_exec(*args, **kwargs):
        return proc

    async def _fake_wait_for(coro, timeout):
        coro.close()  # avoid "coroutine was never awaited" warning
        raise asyncio.TimeoutError

    monkeypatch.setattr(stt, "_SR_AVAILABLE", True)
    monkeypatch.setattr(stt.asyncio, "create_subprocess_exec", _fake_exec)
    monkeypatch.setattr(stt.asyncio, "wait_for", _fake_wait_for)

    ogg = tmp_path / "voice.ogg"
    ogg.write_bytes(b"not really ogg")

    result = asyncio.run(stt.transcribe_voice(ogg))

    assert result is None
    assert proc.killed, "ffmpeg was not killed on conversion timeout"
