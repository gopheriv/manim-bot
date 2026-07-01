"""Async Manim renderer with real-time progress streaming,
timeout, process-tree cleanup, heavy scene detection,
memory-guarded rendering, and LLM-friendly diagnostics."""

import asyncio
import gc
import logging
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import psutil

from common import CREATE_NO_WINDOW, extract_python_code
from code_safety import validate_code_safety
from render_tier import Tier, get_tier

logger = logging.getLogger(__name__)

RENDER_TIMEOUT = 600  # 10 minutes

# RAM guard rails. The pre-check (before starting) is stricter than the in-flight
# kill threshold ON PURPOSE: we refuse to *start* a render once memory is already
# elevated, but tolerate a render that climbs higher mid-flight before killing it
# (a kill wastes the work already done). Keep PRECHECK < KILL so a render that
# barely passes the gate still has headroom before the in-flight guard trips.
RAM_PRECHECK_PCT = 85   # refuse to start a new render above this
RAM_KILL_PCT = 92       # kill an in-flight render above this

# OS temp dir — portable across machines/users (was a hardcoded C:/Users/... path).
RENDER_DIR = Path(tempfile.gettempdir()) / "manim_render"
SCENE_DIR = RENDER_DIR
RENDER_DIR.mkdir(parents=True, exist_ok=True)

# Progress callback type: (pct: int, animation_name: str)
ProgressCallback = Callable[[int, str], None]


@dataclass
class SceneWeight:
    """Estimated computational cost of a Manim scene."""
    score: int
    is_heavy: bool
    mitigations: list[str]


def _estimate_scene_weight(code: str, tier: Tier | None = None) -> SceneWeight:
    """Analyze Manim code to estimate render weight and suggest mitigations.

    The "heavy" threshold scales with the active render tier: a scene that is
    heavy on the 8 GB laptop (constrained, threshold 40) is comfortably light on
    a cinematic box (threshold 120). Only when the score exceeds the tier
    threshold do we downgrade/limit.
    """
    tier = tier or get_tier()
    score = 0
    mitigations: list[str] = []

    # Counters
    updater_count = len(re.findall(r"always_redraw|add_updater", code))
    traced_path_count = len(re.findall(r"TracedPath", code))
    surface_count = len(re.findall(r"Surface|ParametricSurface", code))
    threed_count = len(re.findall(r"ThreeDScene|ThreeDAxes|Sphere", code))
    play_count = len(re.findall(r"self\.play\b", code))
    lagged_count = len(re.findall(r"LaggedStart", code))
    glow_count = len(re.findall(r"set_stroke.*width=\s*([8-9]\d|[2-9]\d\d)", code))
    copy_count = len(re.findall(r"\.copy\(\)", code))
    transform_count = len(re.findall(r"Transform|ReplacementTransform", code))
    # Estimate total frames (each self.play with multiple animations = more frames)
    estimated_frames = play_count * 30 + lagged_count * 15

    # Scoring
    score += updater_count * 8       # Updaters run every frame — most expensive
    score += traced_path_count * 8   # TracedPath accumulates points over time (raised from 6)
    score += surface_count * 30      # Surface rendering is extremely heavy (raised from 25)
    score += threed_count * 12       # 3D adds projection math per frame
    score += play_count * 2          # Each self.play adds render work
    score += lagged_count * 4        # LaggedStart multiplies animations
    score += glow_count * 3          # Thick glow strokes add draw calls
    score += copy_count * 2          # Copies add memory pressure
    score += transform_count * 3     # Morphing adds intermediate frames
    score += max(0, estimated_frames - 200)  # Penalize >200 frames

    threshold = tier.weight_threshold
    is_heavy = score >= threshold
    if is_heavy:
        mitigations = [
            f"HEAVY scene (score {score}, tier {tier.name} threshold {threshold}): "
            f"downgrading to {tier.downgrade_quality} @ {tier.downgrade_fps}fps",
            "Disabling caching to prevent memory buildup",
        ]
        if tier.below_normal_priority:
            mitigations.append("Setting process to BELOW_NORMAL priority")
    elif score > threshold * 0.5:
        mitigations = [f"MEDIUM scene (score {score}, tier {tier.name}): keeping quality"]
    else:
        mitigations = [f"LIGHT scene (score {score}, tier {tier.name}): no mitigation needed"]

    return SceneWeight(
        score=score,
        is_heavy=is_heavy,
        mitigations=mitigations,
    )


def _kill_process_tree(pid: int) -> None:
    """Kill a process and all its children."""
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


# Regex to match Manim progress lines like:
# Animation 1: FadeIn:  45%|████▌     | 9/20 [00:00<00:00, 18.73it/s]
_MANIM_PROGRESS_RE = re.compile(
    r"Animation\s+\d+:\s+(?P<name>\w[^:]*?):\s+(?P<pct>\d+)%\|"
)


async def render(
    code: str,
    chat_id: int,
    timeout: int = RENDER_TIMEOUT,
    quality: str | None = None,
    tiktok_mode: bool = False,
    cancel_event: asyncio.Event | None = None,
    progress_cb: ProgressCallback | None = None,
    tier: Tier | None = None,
) -> Path | None:
    """Write Manim code to a temp file and render it.

    Args:
        progress_cb: Called with (pct, animation_name) as Manim renders.
        tier: Active render tier (defaults to the auto-detected tier).
    """
    # Safety gate (fail-closed): never execute LLM code that imports os/subprocess,
    # calls exec/eval, or reaches for sandbox-escape dunders. This runs the module,
    # so an injected payload would otherwise execute here.
    safe, safety_issues = validate_code_safety(code)
    if not safe:
        render._last_error = "Render blocked — unsafe code: " + "; ".join(safety_issues)
        logger.error(render._last_error)
        return None

    tier = tier or get_tier()
    mem = psutil.virtual_memory()
    if mem.percent > RAM_PRECHECK_PCT:
        render._last_error = (
            f"Render blocked: system RAM at {mem.percent:.0f}% "
            f"({mem.available / 1024**3:.1f} GB free). Close other apps and retry."
        )
        logger.warning(render._last_error)
        return None

    scene_file = _write_scene(code, chat_id)

    # ── Heavy scene detection + tier-aware auto-mitigation ──
    weight = _estimate_scene_weight(code, tier)
    for m in weight.mitigations:
        logger.info(f"[Scene weight] {m}")

    # Normal scenes render at the requested (or tier-default) quality + tier fps.
    quality_flag = quality or tier.default_quality
    fps_value = tier.fps
    if weight.is_heavy:
        # Downgrade toward the tier's heavy target (NOT always 480p — a cinematic
        # tier stays at 1080p, only constrained drops to 480p).
        if quality_flag != tier.downgrade_quality:
            logger.info(
                "Auto-downgraded quality from %s to %s (heavy scene, tier %s)",
                quality_flag, tier.downgrade_quality, tier.name,
            )
        quality_flag = tier.downgrade_quality
        fps_value = tier.downgrade_fps
        # Disable caching for heavy scenes — prevents memory buildup from cached frames
        disable_cache = True

        # Force garbage collection before heavy render
        gc.collect()
        mem_after = psutil.virtual_memory()
        logger.info(f"GC collected: RAM {mem.percent:.0f}% → {mem_after.percent:.0f}%")
    else:
        disable_cache = False

    validation_error = await _validate_python(scene_file)
    if validation_error:
        render._last_error = validation_error
        logger.warning("Generated scene failed Python validation")
        return None

    old_video_dir = RENDER_DIR / "media" / "videos" / f"scene_{chat_id}"
    if old_video_dir.exists():
        shutil.rmtree(old_video_dir, ignore_errors=True)
        logger.info(f"Cleaned old videos: {old_video_dir}")

    cmd_args = ["manim", quality_flag]
    if tiktok_mode:
        cmd_args.extend(["--pixel_width", "1080", "--pixel_height", "1920"])
        logger.info("TikTok mode enabled: 1080x1920 (9:16 portrait)")
    if disable_cache:
        cmd_args.append("--disable_caching")
        logger.info("Caching disabled for heavy scene (prevents memory buildup)")
    # Always pass an explicit fps so output is never silently 15fps — the value
    # comes from the tier (full fps for normal scenes, reduced only when heavy).
    cmd_args.extend(["--fps", str(fps_value)])
    logger.info(
        "Render fps=%d (tier %s%s)", fps_value, tier.name, ", heavy" if weight.is_heavy else ""
    )

    cmd_args.extend([
        "--media_dir", str(RENDER_DIR / "media"),
        str(scene_file), "GenScene"
    ])

    logger.info(f"Rendering: {' '.join(cmd_args)}")

    # Process flags: CREATE_NO_WINDOW always, BELOW_NORMAL for heavy scenes
    BELOW_NORMAL_PRIORITY = 0x00004000
    use_low_priority = weight.is_heavy and tier.below_normal_priority
    creation_flags = CREATE_NO_WINDOW | (BELOW_NORMAL_PRIORITY if use_low_priority else 0)

    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=creation_flags,
        )

        # Stream stderr line-by-line for real-time progress parsing
        stdout_buf = bytearray()
        stderr_buf = bytearray()
        last_pct = 0
        last_anim = ""
        loop_start = time.monotonic()

        while True:
            # Wall-clock timeout — kill a hung/stuck render that produces no more
            # output and never exits (e.g. an infinite loop in generated code).
            # Without this the loop would spin forever, holding the render
            # semaphore and the user's task open indefinitely.
            if time.monotonic() - loop_start > timeout:
                logger.error(f"Render exceeded {timeout}s — killing process tree (pid {proc.pid})")
                _kill_process_tree(proc.pid)
                render._last_error = (
                    f"Render timed out after {timeout}s. The scene is too heavy."
                )
                return None

            # Check cancellation
            if cancel_event and cancel_event.is_set():
                logger.info(f"Render cancelled — killing process tree (pid {proc.pid})")
                _kill_process_tree(proc.pid)
                render._last_error = "Render cancelled by user."
                return None

            # Memory guard — kill render if RAM goes critical mid-flight
            mem = psutil.virtual_memory()
            if mem.percent > RAM_KILL_PCT:
                logger.warning(f"RAM at {mem.percent:.0f}% during render — killing process")
                _kill_process_tree(proc.pid)
                render._last_error = (
                    f"Render killed: system RAM hit {mem.percent:.0f}% "
                    f"({mem.available / 1024**3:.1f} GB free). Simplify the scene."
                )
                # Let memory settle before the next render attempt
                await asyncio.sleep(5)
                gc.collect()
                gc.collect()  # second pass to catch resurrected refs
                mem_after = psutil.virtual_memory()
                logger.info(f"Post-kill GC: RAM {mem.percent:.0f}% → {mem_after.percent:.0f}%")
                return None

            # Read a line from stderr (progress output)
            try:
                line = await asyncio.wait_for(proc.stderr.readline(), timeout=0.5)
            except asyncio.TimeoutError:
                line = None

            # At EOF, readline() returns b"" immediately. If the process hasn't
            # set its returncode yet, looping without a pause would busy-spin the
            # CPU. Sleep briefly so we yield until the process actually exits.
            if line == b"" and proc.stderr.at_eof() and proc.returncode is None:
                await asyncio.sleep(0.1)

            if line:
                stderr_buf.extend(line)
                text = line.decode("utf-8", errors="replace")
                m = _MANIM_PROGRESS_RE.search(text)
                if m:
                    pct = int(m.group("pct"))
                    anim = m.group("name").strip()
                    if pct != last_pct or anim != last_anim:
                        last_pct = pct
                        last_anim = anim
                        if progress_cb:
                            try:
                                progress_cb(pct, anim)
                            except Exception:
                                pass
                        logger.debug(f"Manim progress: {pct}% — {anim}")

            # Check if process finished
            if proc.stdout.at_eof() and proc.stderr.at_eof():
                break

            # Timeout guard
            if proc.returncode is not None:
                break

        # Wait for process to fully exit (with timeout)
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            _kill_process_tree(proc.pid)

        # Read remaining stdout
        stdout_remaining = await proc.stdout.read()
        if stdout_remaining:
            stdout_buf.extend(stdout_remaining)

        stdout_text = bytes(stdout_buf).decode("utf-8", errors="replace")
        stderr_text = bytes(stderr_buf).decode("utf-8", errors="replace")

        # Global timeout check
        if proc.returncode is None:
            logger.error(f"Render timed out after {timeout}s — killing process tree")
            _kill_process_tree(proc.pid)
            render._last_error = (
                f"Render timed out after {timeout}s. The scene is too heavy."
            )
            return None

        if proc.returncode == 0:
            video, reason = _find_video(chat_id)
            if video:
                size_mb = video.stat().st_size / (1024 * 1024)
                logger.info(f"Render OK: {video} ({size_mb:.1f} MB)")
                render._last_error = ""
                return video
            if reason == "too_small":
                render._last_error = "Manim exited OK but produced an empty/truncated GenScene.mp4 (0 frames rendered?)."
            else:
                render._last_error = "Manim exited OK but GenScene.mp4 not found."
            logger.warning(render._last_error)
            return None

        diagnostic = _compact_manim_error(stdout_text, stderr_text)
        logger.warning(f"Manim render failed (exit {proc.returncode}): {diagnostic[:500]}")
        render._last_error = diagnostic
        return None

    except asyncio.CancelledError:
        if proc and proc.pid:
            _kill_process_tree(proc.pid)
        render._last_error = "Render task was cancelled."
        raise  # Re-raise so caller knows task was cancelled
    except Exception as e:
        logger.error(f"Render exception: {e}", exc_info=True)
        render._last_error = str(e)
        return None


render._last_error = ""


def get_last_error() -> str:
    """Accessor for the last render error.

    Callers should use this rather than reaching into the ``render._last_error``
    function attribute directly, so the storage detail stays encapsulated here
    (mirrors cloud_render.get_last_error()).
    """
    return getattr(render, "_last_error", "") or ""


async def _validate_python(scene_file: Path) -> str | None:
    """Validate Python syntax, Manim structure, and numpy compatibility before render."""
    code = scene_file.read_text(encoding="utf-8")
    if "class GenScene" not in code:
        return "Missing 'class GenScene(Scene)' — Manim requires GenScene class"
    if "def construct" not in code:
        return "Missing 'def construct(self)' — GenScene must have construct method"

    # Numpy 2.x compatibility — crash prevention
    numpy_bugs = {
        r"np\.math\.": "np.math.* is removed in numpy 2.x — use math.* instead (import math, then math.factorial, math.pi, etc.)",
        r"\bnp\.float\b(?!\d)": "np.float is removed in numpy 2.x — use float instead",
        r"\bnp\.int\b(?!\d)": "np.int is removed in numpy 2.x — use int instead",
        r"\bnp\.bool\b(?!\d)": "np.bool is removed in numpy 2.x — use bool instead",
        r"\bnp\.complex\b(?!\d)": "np.complex is removed in numpy 2.x — use complex instead",
        r"\bnp\.object\b(?!\d)": "np.object is removed in numpy 2.x — use object instead",
        r"\bnp\.str\b(?!\d)": "np.str is removed in numpy 2.x — use str instead",
    }
    for pattern, msg in numpy_bugs.items():
        if re.search(pattern, code):
            return f"Numpy 2.x incompatibility: {msg}"

    # Syntax validation via py_compile. Bounded by a timeout: py_compile only
    # parses (it never executes the module), but a hung subprocess must not block
    # the render pipeline forever.
    proc = await asyncio.create_subprocess_exec(
        "python", "-m", "py_compile", str(scene_file),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=CREATE_NO_WINDOW,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except asyncio.TimeoutError:
        if proc.pid:
            _kill_process_tree(proc.pid)
        logger.warning("py_compile validation timed out after 30s — skipping syntax gate")
        return None  # don't block the render on a stuck validator
    if proc.returncode == 0:
        return None
    output = (stderr or stdout).decode("utf-8", errors="replace")
    return f"Python validation failed:\n{output[-1800:]}"


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
            # Keep a generous tail so the code-repair model sees the real cause.
            return str(match)[-4000:]
    return combined[-4000:]


# Resource-failure markers — these come straight from the strings render() sets
# when it blocks/kills a render (see the `render._last_error = …` assignments
# above). They describe a SYSTEM condition (RAM/time), not a code bug, so the LLM
# code-repair path cannot fix them and must not be invoked for them.
_RESOURCE_ERROR_MARKERS = (
    "render blocked: system ram",
    "render killed: system ram",
    "timed out after",
    "the scene is too heavy",
    "memoryerror",
    "out of memory",
    "cannot allocate",
)


def classify_render_error(err: str | None) -> str:
    """Classify a render failure as "resource" (RAM/timeout — code can't fix it)
    or "code" (a genuine code defect the LLM self-heal should try to repair)."""
    if not err:
        return "code"
    low = err.lower()
    if any(marker in low for marker in _RESOURCE_ERROR_MARKERS):
        return "resource"
    return "code"


def _write_scene(code: str, chat_id: int) -> Path:
    SCENE_DIR.mkdir(parents=True, exist_ok=True)
    (RENDER_DIR / "media").mkdir(parents=True, exist_ok=True)
    scene_file = SCENE_DIR / f"scene_{chat_id}.py"
    # Final guard: strip any prose/markdown a model wrapped the code in before it
    # reaches the .py file. Generation already does this, but sanitising at the
    # write boundary makes a leaked preamble (the "I'll fix ...:" SyntaxError)
    # impossible regardless of which path produced `code`.
    scene_file.write_text(extract_python_code(code), encoding="utf-8")
    return scene_file


def _find_video(chat_id: int) -> tuple[Path | None, str]:
    """Locate the rendered mp4.

    Returns (path, reason). On success reason is "". On failure reason
    distinguishes the two cases the caller previously could not tell apart:
    "missing" (no output file at all) vs "too_small" (a file exists but is a
    truncated/empty render) — which point at different root causes.
    """
    search = RENDER_DIR / "media" / "videos" / f"scene_{chat_id}"
    if not search.exists():
        return None, "missing"
    found_tiny = False
    for mp4 in search.rglob("GenScene.mp4"):
        if mp4.stat().st_size > 1024:
            return mp4, ""
        found_tiny = True
        logger.warning(f"Skipping tiny video ({mp4.stat().st_size} bytes): {mp4}")
    return None, ("too_small" if found_tiny else "missing")


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
