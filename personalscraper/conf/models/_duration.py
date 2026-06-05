"""Humanized-duration parser for config models.

Converts strings like ``"72h"`` / ``"3d"`` to integer seconds at config-load
time. Used as a Pydantic field_validator on TrackerEconomyConfig seed-time fields.

Design: tracker-economy §Components.2.
"""

from __future__ import annotations

_UNIT_SECONDS: dict[str, int] = {"s": 1, "m": 60, "h": 3_600, "d": 86_400, "w": 604_800}


def parse_duration(value: str | int) -> int:
    """Parse humanized duration string or bare int to seconds.

    Args:
        value: ``"<int><unit>"`` (unit in s/m/h/d/w) or bare int (already seconds).

    Returns:
        Integer seconds.

    Raises:
        ValueError: Unknown unit, non-integer magnitude, or empty string.
    """
    if isinstance(value, int):
        return value
    raw = str(value).strip()
    if not raw:
        raise ValueError("duration string must not be empty")
    unit = raw[-1].lower()
    if unit not in _UNIT_SECONDS:
        raise ValueError(f"unknown duration unit {raw[-1]!r} in {raw!r}; valid: {', '.join(_UNIT_SECONDS)}")
    try:
        magnitude = int(raw[:-1])
    except ValueError:
        raise ValueError(f"non-integer magnitude {raw[:-1]!r} in duration {raw!r}") from None
    return magnitude * _UNIT_SECONDS[unit]


__all__ = ["parse_duration"]
