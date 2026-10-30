"""A session's device, as its holder recognises it: the browser and the system its user agent names.

A user agent is the browser's own claim, never a proof: the label serves the account's reading of
its sessions and its sign-in notices, nothing decides on it. It carries proper names only (a
browser's, a system's) — no sentence, so it needs no translation.
"""

from __future__ import annotations

import re
from typing import Final

#: The browsers, most specific first: Edge and Opera carry « Chrome », Chrome carries « Safari ».
_BROWSERS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("Edge", re.compile(r"\bEdg(?:e|A|iOS)?/")),
    ("Opera", re.compile(r"\b(?:OPR|Opera)/")),
    ("Firefox", re.compile(r"\b(?:Firefox|FxiOS)/")),
    ("Chrome", re.compile(r"\b(?:Chrome|CriOS)/")),
    ("Safari", re.compile(r"\bSafari/")),
)

#: The systems, most specific first: an iPhone's agent says « like Mac OS X », Android's says « Linux ».
_SYSTEMS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("iOS", re.compile(r"\b(?:iPhone|iPad|iPod)\b")),
    ("Android", re.compile(r"\bAndroid\b")),
    ("Windows", re.compile(r"\bWindows\b")),
    ("macOS", re.compile(r"\bMac OS X\b|\bMacintosh\b")),
    ("ChromeOS", re.compile(r"\bCrOS\b")),
    ("Linux", re.compile(r"\bLinux\b")),
)

#: Between the browser and the system: a sign, not a word.
_SEPARATOR: Final = " · "


def _first(user_agent: str, table: tuple[tuple[str, re.Pattern[str]], ...]) -> str | None:
    """The first name of a table whose pattern the user agent matches.

    Args:
        user_agent: The user agent.
        table: Names and their patterns, most specific first.

    Returns:
        The name, or ``None`` when no pattern matches.
    """
    return next((name for name, pattern in table if pattern.search(user_agent)), None)


def device_label(user_agent: str | None) -> str | None:
    """The device a user agent names: « Firefox · macOS », or either half alone.

    Args:
        user_agent: The browser's user agent, as the session kept it.

    Returns:
        The browser and the system it names; ``None`` when it names neither, or there is none.
    """
    if not user_agent:
        return None
    found = [name for name in (_first(user_agent, _BROWSERS), _first(user_agent, _SYSTEMS)) if name]
    return _SEPARATOR.join(found) or None
