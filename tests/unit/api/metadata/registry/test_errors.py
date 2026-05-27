"""Unit tests for the registry error hierarchy (``_errors.py``).

Focused on the structured attributes carried by registry exceptions —
in particular ``ProviderExhausted.last_exception`` which is required by
the chain-exhaustion ACC-13 contract (DESIGN §6.2 + §10): the
immediate caller of a raising chain iterator must be able to recover
the original provider exception message and surface it in
``result.error``.
"""

from __future__ import annotations

from personalscraper.api.metadata._contracts import Searchable
from personalscraper.api.metadata.registry import AttemptOutcome, RegistryProviderName
from personalscraper.api.metadata.registry._errors import ProviderExhausted


def test_provider_exhausted_default_last_exception_is_none() -> None:
    """``ProviderExhausted`` without ``last_exception`` defaults to ``None``.

    Backward-compatibility guard: callers that already raised
    ``ProviderExhausted(capability, attempted)`` (no ``last_exception``
    kwarg) still produce a well-formed instance.
    """
    attempted = [AttemptOutcome(provider=RegistryProviderName("tmdb"), reason="network")]
    exc = ProviderExhausted(Searchable, attempted)

    assert exc.last_exception is None
    assert exc.capability is Searchable
    assert exc.attempted == attempted
    assert exc.item_context is None


def test_provider_exhausted_str_carries_last_exception_message() -> None:
    """``str(ProviderExhausted)`` includes the original exception's message.

    DESIGN §6.2 says the chain's OnFailure is ``raise ProviderExhausted``;
    DESIGN §10 says the caller catches and surfaces a legacy-shape
    ``result.error``. ACC-13 (``test_legacy_fallback_snapshot.py``)
    asserts ``"API down" in result.error``, which is only possible if
    the chain attaches the original exception to ``ProviderExhausted``.
    """
    original = ConnectionError("API down")
    attempted = [AttemptOutcome(provider=RegistryProviderName("tmdb"), reason="network")]

    exc = ProviderExhausted(
        capability=Searchable,
        attempted=attempted,
        item_context={"title": "Bad Movie", "year": 2024},
        last_exception=original,
    )

    assert exc.last_exception is original
    assert "API down" in str(exc)
    assert "Searchable" in str(exc)
    assert "tmdb" in str(exc)


def test_provider_exhausted_item_context_preserved() -> None:
    """``item_context`` is stored verbatim for diagnostics consumers."""
    ctx = {"title": "Movie", "year": 2023, "media_type": "movie"}
    exc = ProviderExhausted(
        capability=Searchable,
        attempted=[],
        item_context=ctx,
        last_exception=ValueError("boom"),
    )

    assert exc.item_context == ctx
