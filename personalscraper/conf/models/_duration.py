"""Humanized-duration parser for config models.

Converts strings like ``"72h"`` / ``"3d"`` to integer seconds at config-load
time. Used as a Pydantic field_validator on TrackerEconomyConfig seed-time fields.

Design: docs/features/tracker-economy/DESIGN.md ("Components → Duration parser").
"""

from __future__ import annotations

import re

_UNIT_SECONDS: dict[str, int] = {"s": 1, "m": 60, "h": 3_600, "d": 86_400, "w": 604_800}

# ASCII digits only: rejects interior whitespace ("72 h"), signs ("+5h"),
# PEP-515 underscores ("1_0h"), and unicode digits that ``int()`` would accept.
_MAGNITUDE_RE = re.compile(r"[0-9]+")


def parse_duration(value: str | int) -> int:
    """Parse humanized duration string or bare int to seconds.

    Args:
        value: ``"<int><unit>"`` (unit in s/m/h/d/w) or bare int (already seconds).

    Returns:
        Integer seconds.

    Raises:
        ValueError: ``bool`` or any non-``int`` type, unknown unit, non-integer
            magnitude (including interior whitespace, ``+``/``-`` signs, PEP-515
            underscores, or unicode digits), or empty string.
    """
    # ``bool`` is an ``int`` subclass, so reject it explicitly and first to keep
    # ``True``/``False`` from silently passing through as ``1``/``0`` seconds.
    if isinstance(value, bool):
        raise ValueError(f"duration must be an int or string, got bool {value!r}")
    if isinstance(value, int):
        return value
    raw = str(value).strip()
    if not raw:
        raise ValueError("duration string must not be empty")
    unit = raw[-1].lower()
    if unit not in _UNIT_SECONDS:
        raise ValueError(f"unknown duration unit {raw[-1]!r} in {raw!r}; valid: {', '.join(_UNIT_SECONDS)}")
    magnitude_str = raw[:-1]
    # Validate the magnitude slice against ASCII digits only BEFORE calling
    # ``int()``, which would otherwise accept signs, underscores, and surrounding
    # whitespace (the strip() above only trims the outer edges, not interior).
    if not _MAGNITUDE_RE.fullmatch(magnitude_str):
        raise ValueError(f"non-integer magnitude {magnitude_str!r} in duration {raw!r}")
    return int(magnitude_str) * _UNIT_SECONDS[unit]


__all__ = ["parse_duration"]
