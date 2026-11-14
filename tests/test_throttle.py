from addon.throttle import Throttle


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_window_counts_down_then_opens() -> None:
    clock = Clock()
    throttle = Throttle(clock)
    assert throttle.retry_after("power", 30) is None
    assert throttle.retry_after("power", 30) is None  # asking never starts a window
    throttle.mark("power")
    assert throttle.retry_after("power", 30) == 30
    clock.now += 29.5
    assert throttle.retry_after("power", 30) == 1
    clock.now += 0.5
    assert throttle.retry_after("power", 30) is None


def test_keys_are_independent() -> None:
    throttle = Throttle(Clock())
    throttle.mark("power")
    assert throttle.retry_after("backup", 30) is None
