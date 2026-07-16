"""One registry-chain iterator shared by every scraper match/details site.

Before this module the scraper carried **four** hand-synchronised copies of the
same ``registry.chain(Capability)`` loop (SCRAPER-01): movie match, movie
details, TV match (the ``tv_service_episodes`` helper) and TV details. Each
re-implemented the identical per-provider ``try/except`` classification
(``circuit_open`` / ``network`` / ``other`` / ``empty_result``),
:class:`AttemptOutcome` accumulation, :class:`ProviderFallbackTriggered`
emission, and the terminal :class:`ProviderExhaustedEvent` + raise. Keeping the
copies in step was a standing liability.

:func:`run_chain` owns that boilerplate **once**. It does **not** reinvent
registry semantics: the provider ORDER (and the settled TVDB-primary /
TMDB-fallback rule for TV) comes from ``registry.chain(capability)``; event
emission is delegated to the registry's fail-soft
:meth:`~personalscraper.api.metadata.registry.ProviderRegistry.emit_provider_fallback`
/ ``emit_provider_exhausted`` helpers (so the bus wiring, throttling and
error-swallowing stay in one place). ``run_chain`` only owns *who* iterates and
*how* failures are classified.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

import requests

from personalscraper.api._contracts import ApiError, CircuitOpenError
from personalscraper.api.metadata.registry import AttemptOutcome, RegistryProviderName
from personalscraper.api.metadata.registry._errors import ProviderExhausted
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from personalscraper.api.metadata.registry import ProviderRegistry

log = get_logger("scraper")

T = TypeVar("T")

# Reasons that mean "the chain actually broke" (as opposed to a provider that
# simply had nothing to offer). Only these trigger the terminal
# ``ProviderExhausted`` raise — a chain that returned nothing but never errored
# is the legacy "no confident match" path and returns ``None`` quietly.
_ERROR_REASONS = frozenset({"circuit_open", "network", "other"})


def run_chain(
    registry: ProviderRegistry,
    capability: type,
    attempt: Callable[[Any], T | None],
    *,
    item_context: dict[str, Any],
    source_filter: Callable[[Any], bool] | None = None,
) -> T | None:
    """Iterate a capability chain, returning the first usable result.

    Walks ``registry.chain(capability)`` in the registry's configured order and
    calls ``attempt(provider)`` on each eligible provider. Per-provider failures
    are classified and surfaced as :class:`ProviderFallbackTriggered` events
    (via the registry's emit helpers); when every attempted provider *errored*
    and none produced a usable result, a :class:`ProviderExhaustedEvent` is
    emitted and :class:`ProviderExhausted` is raised.

    Failure classification (closed list — DESIGN §6.2):

    - ``circuit_open`` — :class:`CircuitOpenError`; record, emit fallback,
      continue.
    - ``network`` — :class:`ApiError`, :class:`requests.RequestException` or
      :class:`OSError`; record with ``exc_type``, emit fallback, continue.
    - ``other`` — any other exception (DESIGN §6.2 fallback-on-unknown-failure);
      record with ``exc_type``, emit fallback, continue.
    - ``empty_result`` — ``attempt`` returned ``None`` (the provider had no
      candidates); emit fallback, continue. This is *not* an error reason, so an
      all-empty chain returns ``None`` without raising.

    Args:
        registry: The provider registry that owns the chain order and the
            event-bus emit helpers.
        capability: The chain capability Protocol (e.g.
            ``MovieDetailsProvider`` / ``TvDetailsProvider``).
        attempt: Per-provider operation. Returns the usable result ``T`` on
            success, or ``None`` to signal an empty result (roll forward to the
            next provider). Raising is classified into a fallback reason.
        item_context: Diagnostic context (title/year/media_type/…) carried on
            every emitted event.
        source_filter: Optional predicate; when supplied, providers for which it
            returns ``False`` are skipped silently (no attempt, no event). Used
            by the details sites to honour the source-of-match invariant (only
            consult the provider that produced the :class:`MatchResult`).

    Returns:
        The first non-``None`` result from ``attempt``, or ``None`` when no
        provider was eligible / matched the filter, or every provider returned
        an empty result without erroring.

    Raises:
        ProviderExhausted: When at least one provider raised a classified error
            (``circuit_open`` / ``network`` / ``other``) and no provider
            returned a usable result. The last underlying exception is carried
            on :attr:`ProviderExhausted.last_exception` so the caller can
            preserve the ACC-13 fail-soft ``result.error`` shape.
    """
    capability_name = capability.__name__
    attempted: list[AttemptOutcome] = []
    last_exception: Exception | None = None

    for provider in registry.chain(capability):
        if source_filter is not None and not source_filter(provider):
            continue
        provider_name = getattr(provider, "provider_name", "?")
        try:
            outcome = attempt(provider)
        except CircuitOpenError as exc:
            last_exception = exc
            attempted.append(AttemptOutcome(provider=RegistryProviderName(provider_name), reason="circuit_open"))
            log.debug(
                "registry_provider_skip",
                provider=provider_name,
                capability=capability_name,
                reason="circuit_open",
            )
            registry.emit_provider_fallback(
                capability=capability_name,
                from_provider=provider_name,
                reason="circuit_open",
                item=item_context,
            )
            continue
        except (ApiError, requests.RequestException, OSError) as exc:
            last_exception = exc
            attempted.append(
                AttemptOutcome(
                    provider=RegistryProviderName(provider_name),
                    reason="network",
                    detail=type(exc).__name__,
                )
            )
            log.warning(
                "registry_provider_fail",
                provider=provider_name,
                capability=capability_name,
                exc_type=type(exc).__name__,
            )
            registry.emit_provider_fallback(
                capability=capability_name,
                from_provider=provider_name,
                reason="network",
                exc_type=type(exc).__name__,
                item=item_context,
            )
            continue
        except Exception as exc:  # noqa: BLE001 — DESIGN §6.2 fallback on unclassified
            # Unclassified provider failure — DESIGN §6.2 promises chain
            # fallback ("first provider that returns a usable result wins"),
            # so record the attempt, emit a ``reason="other"`` fallback for
            # observers, and continue rather than short-circuiting.
            last_exception = exc
            attempted.append(
                AttemptOutcome(
                    provider=RegistryProviderName(provider_name),
                    reason="other",
                    detail=type(exc).__name__,
                )
            )
            log.warning(
                "registry_provider_fail",
                provider=provider_name,
                capability=capability_name,
                exc_type=type(exc).__name__,
            )
            registry.emit_provider_fallback(
                capability=capability_name,
                from_provider=provider_name,
                reason="other",
                exc_type=type(exc).__name__,
                item=item_context,
            )
            continue

        if outcome is None:
            attempted.append(AttemptOutcome(provider=RegistryProviderName(provider_name), reason="empty_result"))
            log.debug(
                "registry_provider_skip",
                provider=provider_name,
                capability=capability_name,
                reason="empty_result",
            )
            registry.emit_provider_fallback(
                capability=capability_name,
                from_provider=provider_name,
                reason="empty_result",
                item=item_context,
            )
            continue

        return outcome

    # Every eligible provider was attempted and none produced a usable result.
    if attempted and any(a.reason in _ERROR_REASONS for a in attempted):
        # At least one attempt errored (the chain actually broke). Emit the
        # exhausted event for observers, then RAISE ``ProviderExhausted`` per
        # DESIGN §6.2. The immediate caller surfaces the original exception's
        # detail in ``result.error`` (ACC-13 contract).
        registry.emit_provider_exhausted(
            capability=capability_name,
            attempted=attempted,
            item=item_context,
        )
        log.error(
            "registry_chain_exhausted",
            capability=capability_name,
            attempted=[(a.provider, a.reason) for a in attempted],
            item=item_context,
        )
        raise ProviderExhausted(
            capability=capability,
            attempted=attempted,
            item_context=item_context,
            last_exception=last_exception,
        )
    # Empty chain, all providers filtered out, or every attempt was an
    # ``empty_result`` → legacy "no confident match" path. The caller branches
    # on the ``None`` return.
    return None
