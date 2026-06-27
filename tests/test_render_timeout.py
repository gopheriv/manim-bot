"""Regression test: render() must enforce its wall-clock timeout and not hang
forever on a manim subprocess that produces no output and never exits."""
import asyncio
import time

import renderer


class _HangingStream:
    """stderr/stdout stub: readline blocks (caller wraps it in wait_for), never EOF."""
    async def readline(self):
        await asyncio.sleep(60)
        return b""

    def at_eof(self):
        return False

    async def read(self):
        return b""


class _HangingProc:
    def __init__(self):
        self.pid = 999999
        self.returncode = None          # never finishes
        self.stdout = _HangingStream()
        self.stderr = _HangingStream()

    async def wait(self):
        await asyncio.sleep(60)


def test_render_enforces_timeout(monkeypatch):
    killed = {"pid": None}

    async def _fake_validate(_scene_file):
        return None  # skip real py_compile subprocess

    async def _fake_exec(*args, **kwargs):
        return _HangingProc()

    class _Mem:
        percent = 50.0
        available = 8 * 1024 ** 3

    monkeypatch.setattr(renderer, "_validate_python", _fake_validate)
    monkeypatch.setattr(renderer.asyncio, "create_subprocess_exec", _fake_exec)
    monkeypatch.setattr(renderer.psutil, "virtual_memory", lambda: _Mem())
    monkeypatch.setattr(renderer, "_kill_process_tree", lambda pid: killed.__setitem__("pid", pid))

    code = "from manim import *\nclass GenScene(Scene):\n    def construct(self):\n        self.wait(1)\n"

    start = time.monotonic()
    result = asyncio.run(renderer.render(code, chat_id=777, timeout=1))
    elapsed = time.monotonic() - start

    assert result is None
    assert elapsed < 5, f"render did not time out promptly (took {elapsed:.1f}s)"
    assert "timed out" in (renderer.render._last_error or "").lower()
    assert killed["pid"] == 999999, "hung process tree was not killed"
