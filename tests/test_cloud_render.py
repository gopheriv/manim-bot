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
    assert fake.calls[0][:2] == ("workflow", "run")


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


def test_find_run_id(monkeypatch):
    _cfg(monkeypatch)
    fake = FakeGh("abc123")
    monkeypatch.setattr(cr, "_gh", fake)
    assert run(cr.find_run_id("abc123")) == 4242
    assert run(cr.find_run_id("nomatch")) is None
