"""Tests for the shared API contracts in ``personalscraper.api._contracts``.

Covers the structural protocols and dataclasses that every API family
(metadata, tracker, torrent, notify) depends on. Sub-phase 1.1 of the
``provider-ids`` feature adds :class:`HasName`, asserted here via
:func:`isinstance` against ad-hoc duck-typed objects.
"""

from __future__ import annotations

from personalscraper.api._contracts import HasName


class _ProviderWithName:
    """Stub with the canonical ``provider_name`` attribute."""

    provider_name = "tmdb"


class _ProviderWithoutName:
    """Stub missing ``provider_name`` to confirm rejection."""


def test_has_name_protocol_isinstance_check() -> None:
    """``HasName`` is runtime-checkable and matches duck-typed objects.

    A class exposing a ``provider_name`` attribute satisfies the protocol
    without inheriting from it (structural subtyping). A class lacking the
    attribute is rejected.
    """
    assert isinstance(_ProviderWithName(), HasName)
    assert not isinstance(_ProviderWithoutName(), HasName)
