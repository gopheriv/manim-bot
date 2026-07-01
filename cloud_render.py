"""Cloud render farm — dispatch Manim renders to a GitHub Actions worker.

Heavy / HD / best-of-N renders run on a free GitHub Actions runner (16 GB on a
public worker repo, unlimited minutes) instead of the RAM-starved laptop. The
bot stays private; only a minimal public *worker* repo holds the workflow.

Everything talks to GitHub through `_gh()` — a single mockable seam — so the
dispatch/await logic is unit-testable without a live repo.
"""

from __future__ import annotations

import asyncio
import base64
import gzip
import json
import logging
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from common import subprocess_creation_flags
from config import (
    CLOUD_RENDER_REPO,
    CLOUD_RENDER_WORKFLOW,
    CLOUD_RENDER_BRANCH,
    CLOUD_RENDER_TIMEOUT,
    CLOUD_RENDER_POLL,
)

logger = logging.getLogger("cloud_render")

# Last error (parallels renderer.render._last_error for uniform error surfacing)
cloud_render_last_error = ""


def get_last_error() -> str:
    """Accessor mirroring renderer.get_last_error() — uniform error surfacing."""
    return cloud_render_last_error

# The render harness AND the workflow definition live here AND in the public
# worker repo (which can't read this private repo at run time).
# `ensure_worker_current` keeps the worker copies in lock-step so they can never
# silently go stale. Checked once per process.
CI_RENDER_PATH = "deploy/ci_render.py"
WORKFLOW_PATH = ".github/workflows/render.yml"
_LOCAL_CI_RENDER = Path(__file__).parent / "deploy" / "ci_render.py"
_LOCAL_WORKFLOW = Path(__file__).parent / ".github" / "workflows" / "render.yml"
# Files this repo owns as the single source of truth and mirrors onto the worker.
# render.yml is synced too so action-version bumps (e.g. the Node 20→24 actions
# upgrade) actually reach the worker — otherwise the worker keeps running its old
# checkout@v4 / setup-python@v5 and the deprecation warning never goes away.
_WORKER_FILES: "list[tuple[Path, str]]" = [
    (_LOCAL_CI_RENDER, CI_RENDER_PATH),
    (_LOCAL_WORKFLOW, WORKFLOW_PATH),
]
# Re-verify the worker copy periodically rather than trusting "synced once,
# synced forever": if the remote worker repo is changed externally, the local
# process picks that up within the TTL instead of only on restart.
_WORKER_SYNC_TTL_S = 600  # 10 minutes
_worker_synced_at = 0.0


def _set_error(msg: str) -> None:
    global cloud_render_last_error
    cloud_render_last_error = msg
    logger.warning("cloud render: %s", msg)


async def _gh(*args: str, timeout: int = 60) -> tuple[int, str, str]:
    """Run a `gh` CLI command. Single seam — tests monkeypatch this.

    Returns (returncode, stdout, stderr).
    """
    proc = await asyncio.create_subprocess_exec(
        "gh", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=subprocess_creation_flags(),  # no console-window flash on Windows
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        return 124, "", f"gh timed out after {timeout}s"
    return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


def encode_code(code: str) -> str:
    """gzip + base64 the Manim code for a compact workflow_dispatch input."""
    return base64.b64encode(gzip.compress(code.encode("utf-8"))).decode("ascii")


def decode_code(blob: str) -> str:
    """Inverse of encode_code (used by the CI worker script)."""
    return gzip.decompress(base64.b64decode(blob)).decode("utf-8")


def new_job_id() -> str:
    return uuid.uuid4().hex[:16]


async def _sync_worker_file(repo: str, local_path: Path, remote_path: str) -> bool:
    """Push one local file to the worker repo if its copy has drifted.

    Compares the worker's copy against ours and pushes (create or update) on a
    difference — making this repo the single source of truth without storing any
    token in the public repo. Best-effort: a read/check/push failure is logged
    and returns False (the caller decides whether that blocks caching). Returns
    True when the worker copy is known-current.
    """
    try:
        local = local_path.read_bytes()
    except OSError as e:  # noqa: BLE001
        logger.warning("worker sync: cannot read %s: %s", local_path, e)
        return False

    remote_sha: str | None = None
    rc, out, _ = await _gh("api", f"repos/{repo}/contents/{remote_path}")
    if rc == 0:
        try:
            meta = json.loads(out or "{}")
            remote_sha = meta.get("sha")
            remote = base64.b64decode((meta.get("content") or "").replace("\n", ""))
            if remote == local:
                return True  # already in sync — no push needed
        except (json.JSONDecodeError, ValueError, TypeError):
            pass  # unparseable → fall through and overwrite
    # rc != 0 usually means 404 (file absent) → create it below.

    put = ["api", "-X", "PUT", f"repos/{repo}/contents/{remote_path}",
           "-f", f"message=chore: sync {remote_path} from manim-bot (auto)",
           "-f", f"content={base64.b64encode(local).decode('ascii')}"]
    if remote_sha:
        put += ["-f", f"sha={remote_sha}"]
    rc, out, err = await _gh(*put)
    if rc != 0:
        logger.warning("worker sync push failed for %s (rc=%s): %s", remote_path, rc, (err or out).strip())
        return False
    logger.info("Synced %s to worker %s", remote_path, repo)
    return True


async def ensure_worker_current(repo: str | None = None, force: bool = False) -> bool:
    """Keep the worker repo's copies of our render harness + workflow in lock-step.

    The worker is a *separate public* repo with its own copies of ci_render.py
    and .github/workflows/render.yml; when those lag behind this repo, renders
    fail in confusing ways (wrong output filename) or run deprecated actions.
    Before dispatching we push any file that has drifted.

    Best-effort and cached per process: failures are logged but never block the
    render (a truly stale worker still surfaces a clear error from the render
    itself). The per-process cache is only set once EVERY tracked file is
    confirmed current, so a transient push failure is retried next dispatch.
    Returns True if the whole worker is known-current.
    """
    global _worker_synced_at
    if not force and _worker_synced_at and (time.monotonic() - _worker_synced_at) < _WORKER_SYNC_TTL_S:
        return True
    repo = repo or CLOUD_RENDER_REPO
    if not repo:
        return False

    all_current = True
    for local_path, remote_path in _WORKER_FILES:
        if not await _sync_worker_file(repo, local_path, remote_path):
            all_current = False

    if all_current:
        _worker_synced_at = time.monotonic()
    return all_current


async def dispatch_render(
    code: str,
    quality: str = "-qh",
    fps: int = 60,
    job_id: str | None = None,
    repo: str | None = None,
) -> str | None:
    """Trigger the worker workflow. Returns the job_id on success, else None."""
    repo = repo or CLOUD_RENDER_REPO
    if not repo:
        _set_error("CLOUD_RENDER_REPO is not configured")
        return None
    job_id = job_id or new_job_id()
    # Keep the worker's render harness in lock-step before dispatching. Best
    # effort: never blocks a render, just prevents the silent-drift failure.
    await ensure_worker_current(repo)
    rc, out, err = await _gh(
        "workflow", "run", CLOUD_RENDER_WORKFLOW,
        "--repo", repo, "--ref", CLOUD_RENDER_BRANCH,
        "-f", f"code_gz={encode_code(code)}",
        "-f", f"quality={quality}",
        "-f", f"fps={fps}",
        "-f", f"job_id={job_id}",
    )
    if rc != 0:
        _set_error(f"dispatch failed (rc={rc}): {err.strip() or out.strip()}")
        return None
    logger.info("Dispatched cloud render job %s to %s", job_id, repo)
    return job_id


async def find_run_id(job_id: str, repo: str | None = None) -> int | None:
    """Find the workflow run whose name carries this job_id (set via run-name)."""
    repo = repo or CLOUD_RENDER_REPO
    rc, out, err = await _gh(
        "run", "list", "--repo", repo, "--workflow", CLOUD_RENDER_WORKFLOW,
        "-L", "30", "--json", "databaseId,displayTitle,status,conclusion",
    )
    if rc != 0:
        _set_error(f"run list failed (rc={rc}): {err.strip()}")
        return None
    try:
        runs = json.loads(out or "[]")
    except json.JSONDecodeError:
        _set_error("could not parse `gh run list` JSON")
        return None
    for run in runs:
        if job_id in (run.get("displayTitle") or ""):
            return int(run["databaseId"])
    return None


async def await_render(
    job_id: str,
    dest_dir: Path,
    repo: str | None = None,
    timeout: int | None = None,
    poll: int | None = None,
) -> Path | None:
    """Poll until the run for job_id completes, download its mp4 artifact."""
    repo = repo or CLOUD_RENDER_REPO
    timeout = timeout or CLOUD_RENDER_TIMEOUT
    poll = poll or CLOUD_RENDER_POLL
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    run_id: int | None = None

    while loop.time() < deadline:
        if run_id is None:
            run_id = await find_run_id(job_id, repo)
            if run_id is None:
                await asyncio.sleep(poll)
                continue
        rc, out, err = await _gh(
            "run", "view", str(run_id), "--repo", repo,
            "--json", "status,conclusion",
        )
        if rc != 0:
            _set_error(f"run view failed (rc={rc}): {err.strip()}")
            await asyncio.sleep(poll)
            continue
        try:
            info = json.loads(out or "{}")
        except json.JSONDecodeError:
            info = {}
        if info.get("status") == "completed":
            if info.get("conclusion") != "success":
                _set_error(f"cloud render concluded '{info.get('conclusion')}'")
                return None
            return await _download_artifact(run_id, job_id, dest_dir, repo)
        await asyncio.sleep(poll)

    _set_error(f"cloud render timed out after {timeout}s (job {job_id})")
    return None


async def _download_artifact(run_id: int, job_id: str, dest_dir: Path, repo: str) -> Path | None:
    # `gh run download` REFUSES to overwrite an existing file ("The file exists").
    # The bulletproof cure: extract into a BRAND-NEW empty directory every time.
    # An empty target makes that failure physically impossible — no matter what
    # leftovers are on disk, whether the chat's dest_dir is reused, or whether an
    # old bot process wrote render.mp4 straight into dest_dir.
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Self-clean the reused chat dir: drop prior per-job subdirs and any legacy
    # top-level render.mp4 (the exact pre-fix file behind "The file exists"). The
    # previous render's video is already uploaded by the time we download next.
    for stale in dest_dir.glob("render-*"):
        if stale.is_dir():
            shutil.rmtree(stale, ignore_errors=True)
    (dest_dir / "render.mp4").unlink(missing_ok=True)

    # Retry transient failures (network blips, GH rate limits, timeouts, a not-
    # yet-available artifact), not just the historical "file exists" case. Each
    # attempt extracts into a brand-new empty dir, so a retry is always safe.
    _MAX_ATTEMPTS = 3
    rc, err = 1, ""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        # tempfile.mkdtemp() creates a fresh, guaranteed-unique EMPTY directory.
        job_dir = Path(tempfile.mkdtemp(prefix=f"render-{job_id}-", dir=dest_dir))
        rc, out, err = await _gh(
            "run", "download", str(run_id), "--repo", repo,
            "-n", f"render-{job_id}", "-D", str(job_dir),
            timeout=180,
        )
        if rc == 0:
            mp4s = sorted(job_dir.rglob("*.mp4"), key=lambda p: p.stat().st_size, reverse=True)
            if not mp4s:
                _set_error("no .mp4 found in downloaded artifact")
                return None
            logger.info("Cloud render %s downloaded: %s", job_id, mp4s[0])
            return mp4s[0]
        shutil.rmtree(job_dir, ignore_errors=True)
        if attempt < _MAX_ATTEMPTS:
            logger.warning(
                "artifact download attempt %d/%d failed (rc=%s): %s — retrying",
                attempt, _MAX_ATTEMPTS, rc, (err or out).strip()[:200],
            )
            await asyncio.sleep(min(5 * attempt, 15))  # linear backoff

    _set_error(f"artifact download failed after {_MAX_ATTEMPTS} attempts (rc={rc}): {err.strip()}")
    return None


async def cloud_render(
    code: str,
    quality: str = "-qh",
    fps: int = 60,
    dest_dir: Path | str = "tmp/cloud",
    job_id: str | None = None,
    repo: str | None = None,
) -> Path | None:
    """High-level: dispatch a render to the cloud and return the resulting mp4."""
    global cloud_render_last_error
    cloud_render_last_error = ""
    job_id = job_id or new_job_id()
    if await dispatch_render(code, quality=quality, fps=fps, job_id=job_id, repo=repo) is None:
        return None
    return await await_render(job_id, Path(dest_dir), repo=repo)
