"""Tiny polite limiter for registry requests."""

import time


class RateLimiter:
    def __init__(self, per_second: float):
        self.min_interval = 0 if per_second <= 0 else 1 / per_second
        self._last = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        now = time.monotonic()
        delay = self.min_interval - (now - self._last)
        if delay > 0:
            time.sleep(delay)
        self._last = time.monotonic()
