import time
import logging
from collections import defaultdict
from typing import Optional
from fastapi import Request, HTTPException, status

logger = logging.getLogger("app.core.rate_limit")


class SlidingWindowRateLimiter:
    """
    Sliding window in-memory rate limiter with Redis-readiness.
    Enforces strict rate limits on sensitive authentication and heavy compute endpoints.
    """

    def __init__(self):
        # key -> list of timestamp floats
        self._history = defaultdict(list)

    def is_rate_limited(self, key: str, max_requests: int, window_seconds: int = 60) -> bool:
        now = time.time()
        window_start = now - window_seconds
        
        # Prune old timestamps
        timestamps = [ts for ts in self._history[key] if ts > window_start]
        self._history[key] = timestamps

        if len(timestamps) >= max_requests:
            return True

        self._history[key].append(now)
        return False


limiter = SlidingWindowRateLimiter()


def check_rate_limit(
    request: Request,
    max_requests: int,
    window_seconds: int = 60,
    identifier: Optional[str] = None,
):
    """
    Dependency or helper to assert rate limiting.
    Raises HTTPException(429) if exceeded.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    key = f"{request.url.path}:{identifier or client_ip}"

    if limiter.is_rate_limited(key=key, max_requests=max_requests, window_seconds=window_seconds):
        logger.warning(f"Rate limit exceeded for {key} ({max_requests} req / {window_seconds}s)")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Rate limit is {max_requests} per {window_seconds} seconds.",
            headers={"Retry-After": str(window_seconds)},
        )
