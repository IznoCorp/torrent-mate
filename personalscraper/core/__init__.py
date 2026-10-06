"""Core layer: neutral contracts and machinery shared by every other package.

Public API (resolved lazily, so importing ``personalscraper.core`` pulls nothing):
  ApiError — the base of every provider-call failure
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from personalscraper.core._contracts import ApiError as ApiError

#: Public name -> the module that defines it, imported on first access: an eager import here would
#: pull that module's tree into every ``import`` of the package (``--help`` included).
_LAZY: dict[str, str] = {
    "ApiError": "personalscraper.core._contracts",
}

__all__ = [
    "ApiError",
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
