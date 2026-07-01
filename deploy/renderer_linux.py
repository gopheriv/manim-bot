"""Production Manim renderer — Linux-compatible with memory guard,
process-tree cleanup, and LLM-friendly diagnostics for self-healing.

Deployed on Oracle Cloud Free Tier (Ubuntu 24.04, ARM Ampere).
"""

import asyncio
import logging
import os
import platform
import re
import shutil
import tempfile
from pathlib import Path

import psutil

# Detect platform — use appropriate defaults
IS_LINUX = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"

# Default quality for server deployment (720p good balance)
DEFAULT_QUALITY = os.getenv("MANIM_QUALITY", "-qm")

# Render directory — /tmp on Linux, AppData on Windows
if IS_LINUX:
    RENDER_DIR = Path(os.getenv("RENDER_DIR", "/tmp/manim_render"))
else:
    RENDER_DIR = Path(os.getenv("RENDER_DIR", str(Path(tempfile.gettempdir()) / "manim_render")))

SCENE_DIR = RENDER_DIR
RENDER_DIR.mkdir(parents=True, exist_ok=True)

# Memory guard threshold — kill render if RAM usage exceeds this
MEMORY_THRESHOLD_PCT = float(os.getenv("MEMORY_THRESHOLD_PCT", "85"))

logger = logging.getLogger(__name__)


def _get_proc_kwargs():
    """Return platform-specific subprocess kwargs."""
    if IS_WINDOWS:
        return {"creationflags": 0x08000000}  # CREATE_NO_WINDOW
    return {}  # Linux: no special flags needed


def _kill_process_tree(pid: int) -> None:
    """Kill a process and all its children (cross-platform)."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        psutil.wait_procs(children, timeout=3)
        try:
            parent.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    except psutil.NoSuchProcess:
        pass


def _check_memory() -> tuple[bool, float]:
    """Check if system RAM usage is below threshold.
    Returns (is_safe, current_usage_pct).
    """
    try:
        mem = psutil.virtual_memory()
        usage_pct = mem.percent
        return usage_pct < MEMORY_THRESHOLD_PCT, usage_pct
    except Exception:
        return True, 0.0  # If check fails, allow render


async def render(
    code: str,
    chat_id: int,
    timeout: int = 300,  # 5 min on server (faster CPU)
    quality: str | None = None,
) -> Path | None:
    """Write Manim code to a temp file and render it. Returns mp4 path or None."""
    # Memory guard — reject if RAM too high
    is_safe, usage_pct = _check_memory()
    if not is_safe:
        render._last_error = (
            f"System memory too high ({usage_pct:.0f}% > {MEMORY_THRESHOLD_PCT:.0f}%). "
            f"Please try again in a few minutes."
        )
        logger.warning(f"Memory guard blocking render: {usage_pct:.0f}%")
        return None

    scene_file = _write_scene(code, chat_id)
    quality_flag = quality or DEFAULT_QUALITY

    validation_error = await _validate_python(scene_file)
    if validation_error:
        render._last_error = validation_error
        logger.warning("Generated scene failed Python validation")
        return None

    # Clean old videos for this chat_id BEFORE rendering to avoid stale file pickup
    old_video_dir = RENDER_DIR / "media" / "videos" / f"scene_{chat_id}"
    if old_video_dir.exists():
        shutil.rmtree(old_video_dir, ignore_errors=True)
        logger.info(f"Cleaned old videos: {old_video_dir}")

    manim_cmd = ["manim", quality_flag, "--media_dir", str(RENDER_DIR / "media"),
                 str(scene_file), "GenScene"]
    logger.info(f"Rendering: {' '.join(manim_cmd)}")

    proc = None
    proc_kwargs = _get_proc_kwargs()
    try:
        proc = await asyncio.create_subprocess_exec(
            *manim_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **proc_kwargs,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""

        if proc.returncode == 0:
            video = _find_video(chat_id)
            if video:
                size_mb = video.stat().st_size / (1024 * 1024)
                logger.info(f"Render OK: {video} ({size_mb:.1f} MB)")
                render._last_error = ""
                return video
            render._last_error = "Manim exited successfully but GenScene.mp4 was not found."
            logger.warning(render._last_error)
            return None

        diagnostic = _compact_manim_error(stdout_text, stderr_text)
        logger.warning(f"Manim render failed (exit {proc.returncode}): {diagnostic[:500]}")
        render._last_error = diagnostic
        return None

    except asyncio.TimeoutError:
        logger.error(f"Render timed out after {timeout}s — killing process tree")
        if proc and proc.pid:
            _kill_process_tree(proc.pid)
        render._last_error = (
            f"Render timed out after {timeout} seconds. The scene is too heavy: reduce duration, "
            "remove expensive updaters/TracedPath objects, lower sample counts, and simplify 3D/surface work."
        )
        return None
    except Exception as e:
        logger.error(f"Render exception: {e}", exc_info=True)
        render._last_error = str(e)
        return None


render._last_error = ""


async def _validate_python(scene_file: Path) -> str | None:
    """Validate Python syntax and Manim structure before expensive render."""
    code = scene_file.read_text(encoding="utf-8")

    # Check GenScene class
    if "class GenScene" not in code:
        return "Missing 'class GenScene(Scene)' — Manim requires GenScene class"

    # Check construct method
    if "def construct" not in code:
        return "Missing 'def construct(self)' — GenScene must have construct method"

    # Syntax validation via py_compile
    proc_kwargs = _get_proc_kwargs()
    proc = await asyncio.create_subprocess_exec(
        "python3", "-m", "py_compile", str(scene_file),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **proc_kwargs,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode == 0:
        return None
    output = (stderr or stdout).decode("utf-8", errors="replace")
    return f"Python syntax/import validation failed:\n{output[-1800:]}"


def _compact_manim_error(stdout: str, stderr: str) -> str:
    combined = "\n".join(part for part in (stdout, stderr) if part).strip()
    if not combined:
        return "Manim failed without stdout/stderr."

    patterns = (
        r"Traceback \(most recent call last\):[\s\S]*",
        r"(?:TypeError|ValueError|NameError|AttributeError|ImportError|ModuleNotFoundError|Exception):[\s\S]*",
        r"\[.*?\]\s+ERROR\s+[\s\S]*",
    )
    for pattern in patterns:
        matches = re.findall(pattern, combined)
        if matches:
            match = matches[-1]
            if isinstance(match, tuple):
                match = " ".join(match)
            return str(match)[-2200:]

    return combined[-2200:]


# Inlined twin of common.extract_python_code — this deploy module is intentionally
# dependency-free so it can ship on a minimal Linux worker. Keep in sync.
_FENCED_BLOCK_RE = re.compile(r"```[^\S\r\n]*[A-Za-z0-9_+-]*[^\S\r\n]*\r?\n(.*?)```", re.DOTALL)
_OPEN_FENCE_RE = re.compile(r"(?m)^[^\S\r\n]*```[^\S\r\n]*[A-Za-z0-9_+-]*[^\S\r\n]*\r?\n")
_STRAY_FENCE_LINE_RE = re.compile(r"(?m)^[^\S\r\n]*```.*\r?\n?")
_CODE_LINE_RE = re.compile(
    r'^[^\S\r\n]*(?:from\s+[.\w]|import\s+\w|#|@\w|class\s+\w|(?:async\s+)?def\s+\w|"""|\'\'\')'
)


def _extract_python_code(text: str) -> str:
    """Strip any LLM prose/markdown wrapping so only runnable Python is written."""
    if not text:
        return ""
    s = text.strip()
    blocks = _FENCED_BLOCK_RE.findall(s)
    if blocks:
        return max(blocks, key=lambda b: (any(k in b for k in ("import ", "class ", "def ")), len(b))).strip("\r\n")
    open_fence = _OPEN_FENCE_RE.search(s)
    if open_fence:
        s = s[open_fence.end():]
    else:
        lines = s.splitlines()
        for i, line in enumerate(lines):
            if _CODE_LINE_RE.match(line):
                s = "\n".join(lines[i:])
                break
    return _STRAY_FENCE_LINE_RE.sub("", s).strip("\r\n")


def _write_scene(code: str, chat_id: int) -> Path:
    SCENE_DIR.mkdir(parents=True, exist_ok=True)
    (RENDER_DIR / "media").mkdir(parents=True, exist_ok=True)
    scene_file = SCENE_DIR / f"scene_{chat_id}.py"
    scene_file.write_text(_extract_python_code(code), encoding="utf-8")
    return scene_file


def _find_video(chat_id: int) -> Path | None:
    """Manim outputs to videos/<script_name>/<quality>/<SceneName>.mp4"""
    search = RENDER_DIR / "media" / "videos" / f"scene_{chat_id}"
    if not search.exists():
        return None
    for mp4 in search.rglob("GenScene.mp4"):
        if mp4.stat().st_size > 1024:  # at least 1 KB
            return mp4
        logger.warning(f"Skipping tiny video ({mp4.stat().st_size} bytes): {mp4}")
    return None


def get_last_generated_code(chat_id: int) -> str | None:
    scene_file = SCENE_DIR / f"scene_{chat_id}.py"
    if scene_file.exists():
        return scene_file.read_text(encoding="utf-8")
    return None


def cleanup():
    try:
        shutil.rmtree(RENDER_DIR, ignore_errors=True)
        RENDER_DIR.mkdir(parents=True, exist_ok=True)
        (RENDER_DIR / "media").mkdir(parents=True, exist_ok=True)
        logger.info("Render cache cleaned")
    except Exception as e:
        logger.warning(f"Cleanup error: {e}")
