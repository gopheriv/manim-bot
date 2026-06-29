"""
Render Queue Manager — manages concurrent rendering tasks with cancellation support.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from config import MAX_CONCURRENT_RENDERS

logger = logging.getLogger("queue_manager")


class TaskStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RenderTask:
    """Represents a single render task."""
    task_id: str
    chat_id: int
    prompt: str
    is_3d: bool
    quality: str
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.QUEUED
    progress: int = 0  # 0-100
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    result_path: Optional[str] = None
    error_message: Optional[str] = None
    
    def cancel(self) -> bool:
        """Request cancellation of this task."""
        if self.status in [TaskStatus.QUEUED, TaskStatus.RUNNING]:
            self.cancel_event.set()
            self.status = TaskStatus.CANCELLED
            self.completed_at = datetime.now()
            logger.info(f"Task {self.task_id} cancelled")
            return True
        return False
    
    def is_cancelled(self) -> bool:
        """Check if task was cancelled."""
        return self.cancel_event.is_set()


class RenderQueue:
    """Manages render queue with concurrency control."""
    
    def __init__(self, max_concurrent: int = 1):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.tasks: dict[str, RenderTask] = {}
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.max_concurrent = max_concurrent
        self._task_counter = 0
        
    def generate_task_id(self) -> str:
        """Generate unique task ID."""
        self._task_counter += 1
        return f"task_{self._task_counter}_{int(datetime.now().timestamp())}"
    
    async def submit_task(
        self,
        chat_id: int,
        prompt: str,
        is_3d: bool = False,
        quality: str = "-qm"
    ) -> RenderTask:
        """Submit a new render task to the queue."""
        task_id = self.generate_task_id()
        task = RenderTask(
            task_id=task_id,
            chat_id=chat_id,
            prompt=prompt,
            is_3d=is_3d,
            quality=quality
        )
        self.tasks[task_id] = task
        await self.queue.put(task_id)
        logger.info(f"Task {task_id} submitted to queue (queue size: {self.queue.qsize()})")
        return task
    
    async def get_next_task(self) -> Optional[RenderTask]:
        """Get next task from queue."""
        try:
            task_id = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            task = self.tasks.get(task_id)
            if task and task.status == TaskStatus.QUEUED:
                return task
            return None
        except asyncio.TimeoutError:
            return None
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a specific task."""
        task = self.tasks.get(task_id)
        if task:
            return task.cancel()
        return False
    
    def get_task(self, task_id: str) -> Optional[RenderTask]:
        """Get task by ID."""
        return self.tasks.get(task_id)
    
    def get_user_task(self, chat_id: int) -> Optional[RenderTask]:
        """Get active task for a user."""
        for task in self.tasks.values():
            if task.chat_id == chat_id and task.status in [TaskStatus.QUEUED, TaskStatus.RUNNING]:
                return task
        return None
    
    def get_queue_size(self) -> int:
        """Get current queue size."""
        return self.queue.qsize()
    
    def get_stats(self) -> dict:
        """Get queue statistics."""
        queued = sum(1 for t in self.tasks.values() if t.status == TaskStatus.QUEUED)
        running = sum(1 for t in self.tasks.values() if t.status == TaskStatus.RUNNING)
        completed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED)
        cancelled = sum(1 for t in self.tasks.values() if t.status == TaskStatus.CANCELLED)
        
        return {
            "queued": queued,
            "running": running,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
            "total": len(self.tasks),
            "max_concurrent": self.max_concurrent
        }
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Remove old completed/failed tasks."""
        now = datetime.now()
        to_remove = []
        for task_id, task in self.tasks.items():
            if task.completed_at:
                age = (now - task.completed_at).total_seconds() / 3600
                if age > max_age_hours:
                    to_remove.append(task_id)

        for task_id in to_remove:
            del self.tasks[task_id]

        # Drain stale task IDs from the queue that no longer exist in self.tasks
        drained = 0
        while not self.queue.empty():
            try:
                task_id = self.queue.get_nowait()
                if task_id in self.tasks:
                    self.queue.put_nowait(task_id)  # Re-queue valid task
                else:
                    drained += 1  # Skip deleted task
            except Exception:
                break
        if drained:
            logger.info(f"Drained {drained} stale IDs from queue during cleanup")

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tasks")


# Global queue instance — concurrency limit from config
render_queue = RenderQueue(max_concurrent=MAX_CONCURRENT_RENDERS)
