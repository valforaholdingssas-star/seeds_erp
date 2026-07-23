from __future__ import annotations

import logging
import time
from typing import Any

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

SENSITIVE_HEADER_KEYS = {
    "authorization",
    "x-seeds-signature",
    "x-wc-webhook-signature",
    "api-key",
    "x-api-key",
}


def scrub_headers(headers: dict[str, Any] | None) -> dict[str, Any]:
    if not headers:
        return {}
    cleaned = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADER_KEYS:
            cleaned[key] = "***REDACTED***"
        else:
            cleaned[key] = value
    return cleaned


class TokenBucketRateLimiter:
    """Redis token-bucket. concurrency=1 pattern for Envia/Alegra."""

    def __init__(self, name: str, rate_per_second: float = 0.8, capacity: int = 1):
        self.name = name
        self.rate = rate_per_second
        self.capacity = capacity
        self.key = f"seeds:ratelimit:{name}"

    def _client(self):
        return redis.from_url(settings.REDIS_URL)

    def acquire(self, timeout: float = 30.0) -> bool:
        client = self._client()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            now = time.time()
            pipe = client.pipeline()
            pipe.hget(self.key, "tokens")
            pipe.hget(self.key, "ts")
            tokens_raw, ts_raw = pipe.execute()
            tokens = float(tokens_raw) if tokens_raw else float(self.capacity)
            ts = float(ts_raw) if ts_raw else now
            tokens = min(self.capacity, tokens + (now - ts) * self.rate)
            if tokens >= 1:
                tokens -= 1
                pipe = client.pipeline()
                pipe.hset(self.key, mapping={"tokens": tokens, "ts": now})
                pipe.expire(self.key, 3600)
                pipe.execute()
                return True
            sleep_for = max(0.05, (1 - tokens) / self.rate)
            time.sleep(min(sleep_for, 0.5))
        logger.warning("Rate limiter timeout for %s", self.name)
        return False
