"""Property-based fuzzing of the untrusted-JSON guard: it may refuse input, never crash."""

import contextlib

from hypothesis import given
from hypothesis import strategies as st

from addon.jsonsafe import safe_loads


@given(st.one_of(st.text(), st.binary()))
def test_safe_loads_only_raises_valueerror(data: str | bytes) -> None:
    with contextlib.suppress(ValueError):
        safe_loads(data)
