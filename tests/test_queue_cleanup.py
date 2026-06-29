"""Regression: RenderQueue.cleanup_old_tasks must TERMINATE and not hang.

In practice the queue is write-only — submit_task puts IDs in but nothing calls
get_next_task to drain them, so task IDs accumulate. cleanup_old_tasks used to
re-queue still-valid IDs into the SAME queue while draining it, so the moment any
valid ID was present `queue.empty()` never became true and the call spun forever,
hanging the whole event loop (reachable via the /clean admin command).
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta

from queue_manager import RenderQueue, RenderTask, TaskStatus


def _queue_with(ids_in_queue, tasks):
    q = RenderQueue(max_concurrent=1)
    q.tasks = dict(tasks)
    for tid in ids_in_queue:
        q.queue.put_nowait(tid)
    return q


def _run_with_timeout(fn, timeout=5.0):
    """Run fn in a daemon thread; return True if it finished within `timeout`."""
    done = threading.Event()
    box: dict = {}

    def _target():
        try:
            fn()
        except Exception as e:  # noqa: BLE001 — surface to the assertion
            box["err"] = e
        finally:
            done.set()

    threading.Thread(target=_target, daemon=True).start()
    return done.wait(timeout), box.get("err")


def _task(task_id):
    return RenderTask(task_id=task_id, chat_id=1, prompt="p", is_3d=False, quality="-qm")


def test_cleanup_terminates_with_valid_queued_ids():
    # A single still-valid, still-queued task is the exact infinite-loop trigger.
    q = _queue_with(["task_1"], {"task_1": _task("task_1")})

    finished, err = _run_with_timeout(q.cleanup_old_tasks)

    assert finished, "cleanup_old_tasks hung — infinite re-queue loop regressed"
    assert err is None
    assert q.queue.qsize() == 1
    assert q.queue.get_nowait() == "task_1"  # valid id preserved


def test_cleanup_drains_only_stale_ids_preserving_order():
    # 'ghost' has no backing task → drained; 'a','b' survive in FIFO order.
    q = _queue_with(["a", "ghost", "b"], {"a": _task("a"), "b": _task("b")})

    finished, err = _run_with_timeout(q.cleanup_old_tasks)
    assert finished and err is None

    survivors = []
    while not q.queue.empty():
        survivors.append(q.queue.get_nowait())
    assert survivors == ["a", "b"]


def test_cleanup_removes_aged_completed_tasks():
    old = _task("old")
    old.status = TaskStatus.COMPLETED
    old.completed_at = datetime.now() - timedelta(hours=48)
    young = _task("young")
    young.status = TaskStatus.COMPLETED
    young.completed_at = datetime.now()
    q = _queue_with([], {"old": old, "young": young})

    q.cleanup_old_tasks(max_age_hours=24)

    assert "old" not in q.tasks
    assert "young" in q.tasks
