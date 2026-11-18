"""Public API of the HTTP transport.

Names are resolved lazily so importing the package pulls neither ``requests`` nor ``tenacity``.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from personalscraper.api.transport._http import HttpTransport as HttpTransport
    from personalscraper.api.transport._policy import CircuitPolicy as CircuitPolicy
    from personalscraper.api.transport._policy import RetryPolicy as RetryPolicy

#: Public name -> the module that defines it, imported on first access: an eager import here would
#: pull that module's tree into every ``import`` of the package (``--help`` included).
_LAZY: dict[str, str] = {
    "CircuitPolicy": "personalscraper.api.transport._policy",
    "HttpTransport": "personalscraper.api.transport._http",
    "RetryPolicy": "personalscraper.api.transport._policy",
}

__all__ = [
    "CircuitPolicy",
    "HttpTransport",
    "RetryPolicy",
]


def __getattr__(name: str) -> Any:
    """Resolve a public name on first access (PEP 562).

    Args:
        name: The attribute looked up on the package.

    Returns:
        The object the name stands for.

    Raises:
        AttributeError: ``name`` is not one of this package's public names.
    """
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(module), name)
