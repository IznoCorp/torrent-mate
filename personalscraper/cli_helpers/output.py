"""Format-aware output helper consumed by CLI commands.

Provides :func:`emit` as the single dispatch point for format-aware output
(rich, plain, or json) based on the global ``state["format"]`` value set
by the top-level ``--format`` callback.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from personalscraper.cli_state import state


def emit(
    payload: dict[str, Any] | str,
    *,
    rich_renderer: Callable[[], None] | None = None,
) -> None:
    """Print *payload* according to the global ``--format`` choice.

    Args:
        payload: A dict (structured data) or a plain string.
        rich_renderer: Optional Rich rendering callback, called when
            ``--format rich``.  When not provided, Rich mode falls back
            to ``console.print(payload)``.

    - ``rich`` → call *rich_renderer* (or ``console.print(payload)``).
    - ``plain`` → ``print(str(payload))`` for strings, or ``key: value``
      lines for dicts.
    - ``json`` → ``print(json.dumps(payload, default=str, indent=2))``.
    """
    fmt: str = state["format"]

    if fmt == "json":
        print(json.dumps(payload, default=str, indent=2))
    elif fmt == "rich":
        if rich_renderer is not None:
            rich_renderer()
        else:
            state["console"].print(payload)  # type: ignore[literal-required]
    else:  # plain
        if isinstance(payload, str):
            print(payload)
        else:
            for key, value in payload.items():
                print(f"{key}: {value}")
