"""Public API of the metadata family.

The concrete clients and façades — :class:`IMDbClient`,
:class:`OMDbAdapter`,
:class:`RottenTomatoesClient`, :class:`TMDBClient`, :class:`TVDBClient`
— live in their own modules. They are *not* re-exported here to avoid
a circular import :  ``api._helpers`` references
``api.metadata._base.Notations`` at import time, and re-exporting the
façades from this package would cause Python to load
``api.metadata.imdb`` (which in turn imports
``api._helpers.ProviderFeatureUnavailable``) before ``_helpers`` has
finished initialising.

Consumers should import from the full module path :

.. code-block:: python

    from personalscraper.api.metadata.imdb import IMDbClient
    from personalscraper.api.metadata.omdb import OMDbAdapter
    from personalscraper.api.metadata.rotten_tomatoes import RottenTomatoesClient

:class:`MediaDetails` is the exception: it is the one name re-exported here, resolved lazily on first
access, so importing the package still loads no client.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from personalscraper.api.metadata._base import MediaDetails as MediaDetails

#: Public name -> the module that defines it, imported on first access.
_LAZY: dict[str, str] = {"MediaDetails": "personalscraper.api.metadata._base"}

__all__ = ["MediaDetails"]


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
