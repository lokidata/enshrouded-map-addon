import math
import time
from collections.abc import Callable


class Throttle:
    """Per-key cooldown: `mark` starts a window, `retry_after` only reads it."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._last: dict[str, float] = {}

    def retry_after(self, key: str, seconds: float) -> int | None:
        if key not in self._last:
            return None
        left = seconds - (self._clock() - self._last[key])
        return max(1, math.ceil(left)) if left > 0 else None

    def mark(self, key: str) -> None:
        self._last[key] = self._clock()
