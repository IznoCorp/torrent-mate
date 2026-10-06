"""Acquisition lobe — home of the RP5b orchestrator (future) and the RP5c injection handle.

This package is a peer of ``ingest``, ``sorter``, ``dispatch``, and ``indexer``.
At RP5c it contains only the injection context (``AcquireContext``) and the
``AcquireStore`` Protocol seam.  No behaviour is implemented here yet.

Import direction: ``acquire/`` may import downward only (``api/``, ``core/``,
``conf/``, ``events/``). It must never import the triage packages (``ingest``,
``sort``, ``sorter``, ``process``, ``scraper``, ``dispatch``, ``indexer``,
``enforce``, ``verify``, ``insights``, ``maintenance``, ``reports``,
``trailers``, ``pipeline``, ``pipeline_steps``, ``commands``).
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from personalscraper.acquire.context import AcquireContext

if TYPE_CHECKING:
    from personalscraper.acquire._factory import build_acquire_context as build_acquire_context

#: Public name -> the module that defines it, imported on first access: the factory pulls the store, the
#: tracker registry and the delete authority, which an eager import would load with every ``import``.
_LAZY: dict[str, str] = {"build_acquire_context": "personalscraper.acquire._factory"}

__all__ = ["AcquireContext", "build_acquire_context"]


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
