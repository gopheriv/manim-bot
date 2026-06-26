"""
Rate limiting system to protect against API spam and abuse.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("rate_limiter")


class RateLimiter:
    """Rate limiter for API calls per user."""
    
    def __init__(self):
        # Track requests per user per action type
        self._requests: dict[str, dict[int, list[datetime]]] = defaultdict(lambda: defaultdict(list))
        
        # Default limits
        self.limits = {
            "animate": (10, 3600),      # 10 renders per hour
            "chat": (60, 3600),         # 60 chat messages per hour
            "edit": (20, 3600),         # 20 edits per hour
            "settings": (30, 3600),     # 30 settings changes per hour
        }
    
    def check_rate_limit(self, user_id: int, action: str) -> tuple[bool, Optional[int]]:
        """
        Check if user can perform action.
        
        Returns:
            (allowed, retry_after_seconds)
            - allowed: True if request is allowed
            - retry_after_seconds: Seconds to wait if not allowed, None if allowed
        """
        if action not in self.limits:
            return True, None
        
        max_requests, window_seconds = self.limits[action]
        now = datetime.now()
        window_start = now - timedelta(seconds=window_seconds)
        
        # Clean old requests
        self._requests[action][user_id] = [
            t for t in self._requests[action][user_id]
            if t > window_start
        ]
        
        # Check limit
        current_count = len(self._requests[action][user_id])
        
        if current_count >= max_requests:
            # Calculate retry time
            oldest_request = self._requests[action][user_id][0]
            retry_after = int((oldest_request + timedelta(seconds=window_seconds) - now).total_seconds())
            logger.warning(f"Rate limit exceeded for user {user_id} on action {action}")
            return False, max(1, retry_after)
        
        # Allow and record
        self._requests[action][user_id].append(now)
        return True, None
    
    def get_remaining(self, user_id: int, action: str) -> tuple[int, int]:
        """
        Get remaining requests and window reset time.
        
        Returns:
            (remaining_requests, seconds_until_reset)
        """
        if action not in self.limits:
            return 999, 0
        
        max_requests, window_seconds = self.limits[action]
        now = datetime.now()
        window_start = now - timedelta(seconds=window_seconds)
        
        # Clean old requests
        self._requests[action][user_id] = [
            t for t in self._requests[action][user_id]
            if t > window_start
        ]
        
        current_count = len(self._requests[action][user_id])
        remaining = max(0, max_requests - current_count)
        
        # Calculate reset time
        if self._requests[action][user_id]:
            oldest_request = self._requests[action][user_id][0]
            reset_time = int((oldest_request + timedelta(seconds=window_seconds) - now).total_seconds())
        else:
            reset_time = 0
        
        return remaining, max(0, reset_time)
    
    def set_limit(self, action: str, max_requests: int, window_seconds: int):
        """Set custom rate limit for an action."""
        self.limits[action] = (max_requests, window_seconds)
        logger.info(f"Rate limit for {action} set to {max_requests}/{window_seconds}s")
    
    def reset_user(self, user_id: int, action: Optional[str] = None):
        """Reset rate limit for a user (all actions or specific one)."""
        if action:
            self._requests[action][user_id] = []
            logger.info(f"Rate limit reset for user {user_id} on action {action}")
        else:
            for act in self._requests:
                self._requests[act][user_id] = []
            logger.info(f"Rate limit reset for user {user_id} on all actions")


# Global rate limiter instance
rate_limiter = RateLimiter()
