"""Render tier — quality scales with available hardware.

Replaces the old "one global 8 GB-laptop budget" with a tier that is detected
from RAM/CPU (or forced via RENDER_TIER). The tier governs:
  - default render quality + fps
  - the scene-weight threshold above which we mitigate (downgrade/limit)
  - whether heavy operations (Surface, 3D, many updaters) are allowed
  - the downgrade target + process priority for heavy scenes

On a capable box this unlocks 1080p/60fps, Surfaces and richer motion; on the
8 GB laptop it keeps today's protective behavior.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, replace

import psutil

from config import RENDER_TIER, MANIM_FPS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Tier:
    name: str
    default_quality: str       # manim flag for normal scenes, e.g. "-qh"
    fps: int                   # explicit fps for normal scenes
    weight_threshold: int      # scene-weight score above which we mitigate
    allow_surface: bool        # Surface/ParametricSurface allowed in prompt
    allow_3d: bool             # ThreeDScene allowed in prompt
    max_updaters: int          # budget for always_redraw/add_updater
    point_budget: int          # total "point" budget surfaced to the prompt
    downgrade_quality: str     # quality used when a scene is judged heavy
    downgrade_fps: int         # fps used when a scene is judged heavy
    below_normal_priority: bool  # run heavy renders at low CPU priority


# ── Tier definitions ─────────────────────────────────────────────────────────

CINEMATIC = Tier(
    name="cinematic",
    default_quality="-qh",      # 1080p
    fps=60,
    weight_threshold=120,
    allow_surface=True,
    allow_3d=True,
    max_updaters=6,
    point_budget=120,
    downgrade_quality="-qh",    # never drop resolution on capable hardware
    downgrade_fps=30,
    below_normal_priority=False,
)

STANDARD = Tier(
    name="standard",
    default_quality="-qh",      # 1080p (e.g. 12 GB cloud box)
    fps=30,
    weight_threshold=70,
    allow_surface=True,
    allow_3d=True,
    max_updaters=4,
    point_budget=70,
    downgrade_quality="-qm",    # 720p if heavy
    downgrade_fps=30,
    below_normal_priority=True,
)

CONSTRAINED = Tier(
    name="constrained",
    default_quality="-qm",      # 720p — today's laptop behavior
    fps=30,
    weight_threshold=40,
    allow_surface=False,
    allow_3d=True,              # allowed, but heavy → downgrade kicks in
    max_updaters=2,
    point_budget=40,
    downgrade_quality="-ql",    # 480p
    downgrade_fps=15,
    below_normal_priority=True,
)

# Cloud cinematic — dispatched to GitHub Actions worker (16 GB, 4 vCPU).
# Used when CLOUD_RENDER_ENABLED=True. The local machine renders a low-res
# preview first, then the cloud worker produces the HD version.
CLOUD_CINEMATIC = Tier(
    name="cloud_cinematic",
    default_quality="-qh",      # 1080p (cloud renders at this)
    fps=60,
    weight_threshold=200,       # cloud has headroom — very generous budget
    allow_surface=True,
    allow_3d=True,
    max_updaters=8,
    point_budget=200,
    downgrade_quality="-qh",    # never drop on cloud
    downgrade_fps=60,
    below_normal_priority=False,
)

_TIERS = {
    "cinematic": CINEMATIC,
    "standard": STANDARD,
    "constrained": CONSTRAINED,
    "cloud_cinematic": CLOUD_CINEMATIC,
}


def _apply_fps_override(tier: Tier) -> Tier:
    """Honor an explicit MANIM_FPS override (0 = use the tier's fps)."""
    if MANIM_FPS and MANIM_FPS > 0:
        return replace(tier, fps=MANIM_FPS, downgrade_fps=min(MANIM_FPS, tier.downgrade_fps))
    return tier


def detect_tier() -> Tier:
    """Pick a tier from RENDER_TIER override or auto-detect RAM/CPU."""
    forced = RENDER_TIER
    if forced in _TIERS:
        logger.info("Render tier forced via RENDER_TIER=%s", forced)
        return _apply_fps_override(_TIERS[forced])

    try:
        total_gb = psutil.virtual_memory().total / 1024 ** 3
    except Exception:
        total_gb = 8.0
    cpu = os.cpu_count() or 2

    if total_gb >= 16 and cpu >= 6:
        tier = CINEMATIC
    elif total_gb >= 10:
        tier = STANDARD
    else:
        tier = CONSTRAINED

    logger.info(
        "Render tier auto-detected: %s (RAM=%.1f GB, CPU=%d)", tier.name, total_gb, cpu
    )
    return _apply_fps_override(tier)


_active_tier: Tier | None = None


def get_tier() -> Tier:
    """Return the cached active tier (detected once per process)."""
    global _active_tier
    if _active_tier is None:
        _active_tier = detect_tier()
    return _active_tier


def cloud_available() -> bool:
    """Check if cloud render farm is enabled and configured."""
    from config import CLOUD_RENDER_ENABLED, CLOUD_RENDER_REPO
    return bool(CLOUD_RENDER_ENABLED and CLOUD_RENDER_REPO)


def get_cloud_quality() -> str:
    """Return the quality for cloud renders (always 1080p)."""
    return "-qh"


def get_cloud_fps() -> int:
    """Return the fps for cloud renders (60fps)."""
    return 60
