"""Cloud render dispatch layer — fully mocked (no live gh/repo, no async plugin)."""
import asyncio
import base64
import gzip
import json
import shutil
import tempfile
from pathlib import Path

import cloud_render as cr


def run(coro):
    return asyncio.run(coro)


def test_encode_decode_roundtrip():
    code = "from manim import *\nclass GenScene(Scene):\n    def construct(self): pass\n"
    assert cr.decode_code(cr.encode_code(code)) == code


def test_worker_decode_matches_encode():
    # The CI worker decodes with plain gzip+base64; must match encode_code output.
    code = "x = 'omega-unicode'\n"
    blob = cr.encode_code(code)
    assert gzip.decompress(base64.b64decode(blob)).decode("utf-8") == code


class FakeGh:
    """Stateful async stand-in for `gh`."""
    def __init__(self, job_id, conclusion="success", status_seq=("completed",), with_mp4=True):
        self.job_id = job_id
        self.conclusion = conclusion
        self.status_seq = list(status_seq)
        self.with_mp4 = with_mp4
        self.calls = []
        self._views = 0

    async def __call__(self, *args, timeout=60):
        self.calls.append(args)
        a = list(args)
        if a[0] == "api":
            # ensure_worker_current: GET returns our local copy (already in sync,
            # so no push); PUT (if ever reached) just succeeds.
            if "-X" in a and a[a.index("-X") + 1] == "PUT":
                return 0, json.dumps({"commit": {"sha": "deadbeef"}}), ""
            content = base64.b64encode(cr._LOCAL_CI_RENDER.read_bytes()).decode("ascii")
            return 0, json.dumps({"content": content, "sha": "remote-sha"}), ""
        if a[:2] == ["workflow", "run"]:
            return 0, "", ""
        if a[:2] == ["run", "list"]:
            runs = [{"databaseId": 4242, "displayTitle": f"render {self.job_id}",
                     "status": "completed", "conclusion": self.conclusion}]
            return 0, json.dumps(runs), ""
        if a[:2] == ["run", "view"]:
            st = self.status_seq[min(self._views, len(self.status_seq) - 1)]
            self._views += 1
            return 0, json.dumps({"status": st, "conclusion": self.conclusion}), ""
        if a[:2] == ["run", "download"]:
            d = Path(a[a.index("-D") + 1])
            if self.with_mp4:
                d.mkdir(parents=True, exist_ok=True)
                (d / "render.mp4").write_bytes(b"\x00" * 4096)
            return 0, "", ""
        return 0, "", ""


def _cfg(monkeypatch):
    monkeypatch.setattr(cr, "CLOUD_RENDER_REPO", "owner/worker")
    monkeypatch.setattr(cr, "CLOUD_RENDER_POLL", 0)
    monkeypatch.setattr(cr, "CLOUD_RENDER_TIMEOUT", 5)
    monkeypatch.setattr(cr, "_worker_synced", False)  # reset per-process sync cache


def test_dispatch_requires_repo(monkeypatch):
    monkeypatch.setattr(cr, "CLOUD_RENDER_REPO", "")
    assert run(cr.dispatch_render("code", job_id="j1")) is None
    assert "REPO" in cr.cloud_render_last_error


def test_dispatch_success(monkeypatch):
    _cfg(monkeypatch)
    fake = FakeGh("j2")
    monkeypatch.setattr(cr, "_gh", fake)
    jid = run(cr.dispatch_render(
        "from manim import *\nclass GenScene(Scene):\n def construct(self):pass",
        quality="-qh", fps=60, job_id="j2"))
    assert jid == "j2"
    # Worker sync runs first, then the dispatch.
    assert fake.calls[0][0] == "api"
    assert any(c[:2] == ("workflow", "run") for c in fake.calls)


def test_full_cloud_render(monkeypatch):
    _cfg(monkeypatch)
    fake = FakeGh("j3", status_seq=("queued", "in_progress", "completed"))
    monkeypatch.setattr(cr, "_gh", fake)
    d = Path(tempfile.mkdtemp())
    try:
        out = run(cr.cloud_render("class GenScene(Scene):\n def construct(self):pass",
                                  dest_dir=d, job_id="j3"))
        assert out is not None and out.exists() and out.suffix == ".mp4"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_download_into_reused_dest_no_collision(monkeypatch):
    # Regression: a chat's dest_dir already holds render.mp4 from a prior render.
    # gh run download refuses to overwrite existing files, so the download must
    # land in a fresh per-job subdir, not clobber/collide with the root file.
    _cfg(monkeypatch)
    d = Path(tempfile.mkdtemp())
    try:
        (d / "render.mp4").write_bytes(b"\x00" * 4096)  # leftover from a prior render
        fake = FakeGh("jReuse")
        monkeypatch.setattr(cr, "_gh", fake)
        out = run(cr.await_render("jReuse", d))
        assert out is not None and out.exists()
        assert out.parent != d  # isolated in its own per-job subdir
        assert out.parent.name == "render-jReuse"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_download_purges_stale_leftovers(monkeypatch):
    # A reused chat dir holds a legacy root render.mp4 (from pre-fix code) and an
    # old per-job subdir. The new download must isolate cleanly AND purge both.
    _cfg(monkeypatch)
    d = Path(tempfile.mkdtemp())
    try:
        (d / "render.mp4").write_bytes(b"\x00" * 4096)        # legacy leftover
        old = d / "render-OLDJOB"
        old.mkdir()
        (old / "render.mp4").write_bytes(b"\x00" * 4096)      # stale prior job
        fake = FakeGh("jNew")
        monkeypatch.setattr(cr, "_gh", fake)
        out = run(cr.await_render("jNew", d))
        assert out is not None and out.exists()
        assert out.parent.name == "render-jNew"
        assert not (d / "render.mp4").exists(), "legacy root render.mp4 not purged"
        assert not old.exists(), "stale prior job dir not purged"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_failed_conclusion(monkeypatch):
    _cfg(monkeypatch)
    fake = FakeGh("j4", conclusion="failure")
    monkeypatch.setattr(cr, "_gh", fake)
    d = Path(tempfile.mkdtemp())
    try:
        out = run(cr.await_render("j4", d))
        assert out is None
        assert "failure" in cr.cloud_render_last_error
    finally:
        shutil.rmtree(d, ignore_errors=True)


class SyncGh:
    """Async `gh` stand-in that records PUTs and serves a configurable GET."""
    def __init__(self, get_rc=0, get_content=None, get_sha="remote-sha"):
        self.get_rc = get_rc
        self.get_content = get_content
        self.get_sha = get_sha
        self.puts = []

    async def __call__(self, *args, timeout=60):
        a = list(args)
        if a[0] == "api" and "-X" in a and a[a.index("-X") + 1] == "PUT":
            self.puts.append(a)
            return 0, json.dumps({"commit": {"sha": "newsha"}}), ""
        if a[0] == "api":  # GET contents
            if self.get_rc != 0:
                return self.get_rc, "", "Not Found"
            body = {"sha": self.get_sha}
            if self.get_content is not None:
                body["content"] = base64.b64encode(self.get_content).decode("ascii")
            return 0, json.dumps(body), ""
        return 0, "", ""


def test_ensure_worker_current_noop_when_in_sync(monkeypatch):
    _cfg(monkeypatch)
    fake = SyncGh(get_content=cr._LOCAL_CI_RENDER.read_bytes())
    monkeypatch.setattr(cr, "_gh", fake)
    assert run(cr.ensure_worker_current()) is True
    assert fake.puts == []  # identical content → no push


def test_ensure_worker_current_pushes_on_drift(monkeypatch):
    _cfg(monkeypatch)
    fake = SyncGh(get_content=b"# stale worker copy\n")
    monkeypatch.setattr(cr, "_gh", fake)
    assert run(cr.ensure_worker_current()) is True
    assert len(fake.puts) == 1
    assert "sha=remote-sha" in fake.puts[0]  # update carries the blob sha


def test_ensure_worker_current_creates_when_missing(monkeypatch):
    _cfg(monkeypatch)
    fake = SyncGh(get_rc=1)  # 404 → file absent on worker
    monkeypatch.setattr(cr, "_gh", fake)
    assert run(cr.ensure_worker_current()) is True
    assert len(fake.puts) == 1
    assert not any(x.startswith("sha=") for x in fake.puts[0])  # create, no sha


def test_ensure_worker_current_cached(monkeypatch):
    _cfg(monkeypatch)
    fake = SyncGh(get_content=cr._LOCAL_CI_RENDER.read_bytes())
    monkeypatch.setattr(cr, "_gh", fake)
    assert run(cr.ensure_worker_current()) is True
    fake2 = SyncGh(get_content=b"different")
    monkeypatch.setattr(cr, "_gh", fake2)
    assert run(cr.ensure_worker_current()) is True  # cached → skips re-check
    assert fake2.puts == []


def test_find_run_id(monkeypatch):
    _cfg(monkeypatch)
    fake = FakeGh("abc123")
    monkeypatch.setattr(cr, "_gh", fake)
    assert run(cr.find_run_id("abc123")) == 4242
    assert run(cr.find_run_id("nomatch")) is None
