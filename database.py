"""
Persistent storage using SQLite for render history and user data.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("database")

DB_PATH = Path(__file__).parent / "data" / "manim_bot.db"


class Database:
    """SQLite database manager for persistent storage."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(str(self.db_path))
    
    def _init_db(self):
        """Initialize database tables."""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS render_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    task_id TEXT UNIQUE NOT NULL,
                    prompt TEXT NOT NULL,
                    is_3d INTEGER NOT NULL DEFAULT 0,
                    quality TEXT NOT NULL,
                    theme TEXT NOT NULL,
                    status TEXT NOT NULL,
                    code TEXT,
                    video_path TEXT,
                    video_file_id TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_chat_id ON render_history(chat_id);
                CREATE INDEX IF NOT EXISTS idx_task_id ON render_history(task_id);
                CREATE INDEX IF NOT EXISTS idx_status ON render_history(status);
                CREATE INDEX IF NOT EXISTS idx_created_at ON render_history(created_at);
                CREATE INDEX IF NOT EXISTS idx_chat_created ON render_history(chat_id, created_at);
            """)
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
        finally:
            conn.close()
    
    def save_render(
        self,
        chat_id: int,
        task_id: str,
        prompt: str,
        is_3d: bool,
        quality: str,
        theme: str,
        status: str,
        code: Optional[str] = None,
        video_path: Optional[str] = None,
        video_file_id: Optional[str] = None,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ):
        """Save or update render in history."""
        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO render_history
                (chat_id, task_id, prompt, is_3d, quality, theme, status,
                 code, video_path, video_file_id, error_message,
                 created_at, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    task_id,
                    prompt,
                    1 if is_3d else 0,
                    quality,
                    theme,
                    status,
                    code,
                    video_path,
                    video_file_id,
                    error_message,
                    datetime.now().isoformat(),
                    started_at.isoformat() if started_at else None,
                    completed_at.isoformat() if completed_at else None,
                )
            )
            conn.commit()
            logger.debug(f"Saved render {task_id} for chat {chat_id}")
        finally:
            conn.close()
    
    def get_user_history(self, chat_id: int, limit: int = 10) -> list[dict]:
        """Get render history for a user."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                SELECT task_id, prompt, is_3d, quality, theme, status,
                       created_at, completed_at
                FROM render_history
                WHERE chat_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (chat_id, limit)
            )
            rows = cursor.fetchall()
            return [
                {
                    "task_id": row[0],
                    "prompt": row[1],
                    "is_3d": bool(row[2]),
                    "quality": row[3],
                    "theme": row[4],
                    "status": row[5],
                    "created_at": row[6],
                    "completed_at": row[7],
                }
                for row in rows
            ]
        finally:
            conn.close()
    
    def get_last_render(self, chat_id: int) -> Optional[dict]:
        """Get last successful render for a user."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                SELECT task_id, prompt, is_3d, quality, theme, code,
                       video_path, video_file_id, created_at, completed_at
                FROM render_history
                WHERE chat_id = ? AND status = 'completed'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (chat_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                "task_id": row[0],
                "prompt": row[1],
                "is_3d": bool(row[2]),
                "quality": row[3],
                "theme": row[4],
                "code": row[5],
                "video_path": row[6],
                "video_file_id": row[7],
                "created_at": row[8],
                "completed_at": row[9],
            }
        finally:
            conn.close()
    
    def get_render_by_file_id(self, chat_id: int, video_file_id: str) -> Optional[dict]:
        """Get the render whose result video matches a given telegram file_id.

        Lets 'reply to a video and edit it' target the EXACT video replied to,
        rather than always the user's most recent render.
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                SELECT task_id, prompt, is_3d, quality, theme, code,
                       video_path, video_file_id, created_at, completed_at
                FROM render_history
                WHERE chat_id = ? AND video_file_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (chat_id, video_file_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "task_id": row[0],
                "prompt": row[1],
                "is_3d": bool(row[2]),
                "quality": row[3],
                "theme": row[4],
                "code": row[5],
                "video_path": row[6],
                "video_file_id": row[7],
                "created_at": row[8],
                "completed_at": row[9],
            }
        finally:
            conn.close()

    def get_render_by_task_id(self, task_id: str) -> Optional[dict]:
        """Get render by task ID."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                SELECT chat_id, task_id, prompt, is_3d, quality, theme, status,
                       code, video_path, video_file_id, error_message,
                       created_at, started_at, completed_at
                FROM render_history
                WHERE task_id = ?
                """,
                (task_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                "chat_id": row[0],
                "task_id": row[1],
                "prompt": row[2],
                "is_3d": bool(row[3]),
                "quality": row[4],
                "theme": row[5],
                "status": row[6],
                "code": row[7],
                "video_path": row[8],
                "video_file_id": row[9],
                "error_message": row[10],
                "created_at": row[11],
                "started_at": row[12],
                "completed_at": row[13],
            }
        finally:
            conn.close()
    
    def get_stats(self) -> dict:
        """Get global statistics."""
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                    SUM(CASE WHEN is_3d = 1 THEN 1 ELSE 0 END) as renders_3d,
                    COUNT(DISTINCT chat_id) as unique_users
                FROM render_history
            """)
            row = cursor.fetchone()
            
            return {
                "total": row[0] or 0,
                "completed": row[1] or 0,
                "failed": row[2] or 0,
                "cancelled": row[3] or 0,
                "renders_3d": row[4] or 0,
                "unique_users": row[5] or 0,
            }
        finally:
            conn.close()
    
    def cleanup_old_renders(self, max_age_days: int = 30):
        """Remove old render history entries."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """
                DELETE FROM render_history
                WHERE created_at < datetime('now', ? || ' days')
                AND status IN ('completed', 'failed', 'cancelled')
                """,
                (-max_age_days,)
            )
            conn.commit()
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old render history entries")
        finally:
            conn.close()


# Global database instance
db = Database()
