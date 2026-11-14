"""JSON loading that cannot crash the interpreter.

`json.loads` on a few ten thousand nested brackets overflows the C stack (a segfault on some
Pythons and stack sizes, `RecursionError` is not a reliable guard). The nesting depth is
measured first, iteratively, and a too deep document is refused before any parsing.
"""

import json
from typing import Any

MAX_DEPTH = 40  # the documents of this add-on are at most 4 levels deep


def _peak_depth(data: bytes) -> int:
    depth = peak = 0
    in_str = esc = False
    for b in data:
        if in_str:
            if esc:
                esc = False
            elif b == 0x5C:  # backslash
                esc = True
            elif b == 0x22:  # closing quote
                in_str = False
        elif b == 0x22:
            in_str = True
        elif b in (0x5B, 0x7B):  # [ {
            depth += 1
            peak = max(peak, depth)
        elif b in (0x5D, 0x7D):  # ] }
            depth -= 1
    return peak


def safe_loads(data: str | bytes) -> Any:
    raw = data if isinstance(data, bytes) else data.encode("utf-8", "surrogatepass")
    if _peak_depth(raw) > MAX_DEPTH:
        raise ValueError("document trop imbriqué")
    return json.loads(data)
