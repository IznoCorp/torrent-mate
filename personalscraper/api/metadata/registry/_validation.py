"""Boot validation for the provider registry (DESIGN §7.2).

Implements the six ``ConfigIssue.code`` families as independent check
functions, collected into a single list by ``validate_config()``. No
check raises individually — the user must see ALL problems at once.
"""

from __future__ import annotations

import difflib
import os
from typing import TYPE_CHECKING

from personalscraper.api.metadata.registry import ConfigIssue, RegistryProviderName
from personalscraper.api.metadata.registry._semantics import (
    CAPABILITY_KEYS,
    CHAIN_CAPABILITIES,
    LOCKED_CAPABILITIES,
)

if TYPE_CHECKING:
    from personalscraper.conf.models.providers import ProvidersConfig
    from personalscraper.config import Settings

# ---------------------------------------------------------------------------
# Credential mapping — provider name → (attribute_on_settings | None, env_var)
#
# ``None`` attribute means the credential is *not* a Settings field and must
# be read from ``os.environ`` directly (OMDB/Trakt credentials live in
# ``_activation.py`` but not in the pydantic-settings model).
# ---------------------------------------------------------------------------

_CRED_MAP: dict[str, tuple[str | None, str]] = {
    "tmdb": ("tmdb_api_key", "TMDB_API_KEY"),
    "tvdb": ("tvdb_api_key", "TVDB_API_KEY"),
    "imdb": (None, "OMDB_API_KEY"),
    "omdb": (None, "OMDB_API_KEY"),
    "rotten_tomatoes": (None, "OMDB_API_KEY"),
    "trakt": (None, "TRAKT_CLIENT_ID"),
}


def _credential_value(name: str, settings: Settings) -> str:
    """Return the credential string for *name*, possibly empty.

    Args:
        name: Provider name key.
        settings: The pipeline ``Settings`` instance.

    Returns:
        The credential value, or ``""`` if missing.
    """
    if name not in _CRED_MAP:
        return ""
    attr, env = _CRED_MAP[name]
    if attr is not None:
        return getattr(settings, attr, "")
    return os.environ.get(env, "")


# ---------------------------------------------------------------------------
# 1 — missing_credentials
# ---------------------------------------------------------------------------


def _check_missing_credentials(
    providers_config: ProvidersConfig,
    settings: Settings,
) -> list[ConfigIssue]:
    """Check that every provider listed in any section has its credential set.

    Providers with no credential entry in ``_CRED_MAP`` are skipped
    (they do not require credentials).
    """
    issues: list[ConfigIssue] = []
    seen: set[str] = set()
    for section_name, section in providers_config.model_dump().items():
        for name in section:
            if name in seen:
                continue
            seen.add(name)
            if name not in _CRED_MAP:
                continue
            if not _credential_value(name, settings):
                _, env = _CRED_MAP[name]
                issues.append(
                    ConfigIssue(
                        code="missing_credentials",
                        section=section_name,
                        provider=RegistryProviderName(name),
                        message=f"Required credential {env} is not set",
                    )
                )
    return issues


# ---------------------------------------------------------------------------
# 2 — protocol_mismatch
# ---------------------------------------------------------------------------


def _check_protocol_mismatch(
    providers_config: ProvidersConfig,
    providers: dict[str, object],
) -> list[ConfigIssue]:
    """Verify every listed provider implements the Protocol of its section.

    Uses ``CAPABILITY_KEYS`` to map section name → Protocol class, then
    ``isinstance()`` (Protocols are ``@runtime_checkable``).
    """
    issues: list[ConfigIssue] = []
    for section_name, section in providers_config.model_dump().items():
        protocol = CAPABILITY_KEYS.get(section_name)
        if protocol is None:
            continue
        for name in section:
            if name not in providers:
                continue  # reported by _check_unknown_providers
            instance = providers[name]
            if not isinstance(instance, protocol):
                class_name = type(instance).__name__
                issues.append(
                    ConfigIssue(
                        code="protocol_mismatch",
                        section=section_name,
                        provider=RegistryProviderName(name),
                        message=f"{class_name} does not implement {section_name}",
                    )
                )
    return issues


# ---------------------------------------------------------------------------
# 3 — unknown_provider
# ---------------------------------------------------------------------------


def _check_unknown_providers(
    providers_config: ProvidersConfig,
    providers: dict[str, object],
) -> list[ConfigIssue]:
    """Detect provider names in config that have no instantiated instance.

    Includes a ``difflib.get_close_matches`` suggestion when a plausible
    typo is found.
    """
    issues: list[ConfigIssue] = []
    known = list(providers.keys())
    seen: dict[str, str] = {}  # name → first section it appears in
    for section_name, section in providers_config.model_dump().items():
        for name in section:
            if name not in seen:
                seen[name] = section_name

    for name, first_section in seen.items():
        if name not in providers:
            suggestion = ""
            matches = difflib.get_close_matches(name, known, n=1, cutoff=0.7)
            if matches:
                suggestion = f" (did you mean {matches[0]!r}?)"
            issues.append(
                ConfigIssue(
                    code="unknown_provider",
                    section=first_section,
                    provider=RegistryProviderName(name),
                    message=f"Provider {name!r} is not configured{suggestion}",
                )
            )
    return issues


# ---------------------------------------------------------------------------
# 4 — empty_chain_section
# ---------------------------------------------------------------------------


def _check_empty_chain_sections(
    providers_config: ProvidersConfig,
) -> list[ConfigIssue]:
    """Ensure every chain-capability section has at least one provider.

    An empty chain capability means no fallback can ever fire, which is
    almost certainly a misconfiguration (DESIGN §7.2).
    """
    issues: list[ConfigIssue] = []
    for section_name, section in providers_config.model_dump().items():
        protocol = CAPABILITY_KEYS.get(section_name)
        if protocol is not None and protocol in CHAIN_CAPABILITIES:
            if not section:
                issues.append(
                    ConfigIssue(
                        code="empty_chain_section",
                        section=section_name,
                        provider=None,
                        message=f"Chain capability {section_name!r} has no providers — at least one required",
                    )
                )
    return issues


# ---------------------------------------------------------------------------
# 5 — locked_capability_orphan
# ---------------------------------------------------------------------------


def _check_locked_capability_orphans(
    providers_config: ProvidersConfig,
    providers: dict[str, object],
) -> list[ConfigIssue]:
    """Check that every chain-capability provider can reach every non-empty locked section.

    Rule (relaxed, per sub-phase 0.3 spec): a chain provider P is an
    orphan for locked section L if **all** of these hold:

    - L is non-empty (no orphan issue on intentionally-empty sections)
    - P is not in L itself
    - P is not in the IDCrossRef section (so no translation path exists)

    The conservative rule is sufficient for the current flat IDCrossRef
    model. A full implementation would require explicit edge declarations
    between IDCrossRef providers.
    """
    issues: list[ConfigIssue] = []
    # Collect the set of chain providers (from any chain-capability section)
    chain_providers: set[str] = set()
    for section_name, section in providers_config.model_dump().items():
        protocol = CAPABILITY_KEYS.get(section_name)
        if protocol is not None and protocol in CHAIN_CAPABILITIES:
            chain_providers.update(section.keys())

    idcrossref_providers: set[str] = set(providers_config.model_dump().get("IDCrossRef", {}).keys())

    for section_name, section in providers_config.model_dump().items():
        protocol = CAPABILITY_KEYS.get(section_name)
        if protocol is None or protocol not in LOCKED_CAPABILITIES:
            continue
        if not section:  # empty locked section — intentionally unused
            continue
        locked_providers = set(section.keys())
        for p_name in chain_providers:
            if p_name in locked_providers:
                continue
            if p_name in idcrossref_providers:
                continue
            issues.append(
                ConfigIssue(
                    code="locked_capability_orphan",
                    section=section_name,
                    provider=RegistryProviderName(p_name),
                    message=(
                        f"Provider {p_name!r} appears in a chain section but is "
                        f"neither in locked section {section_name!r} nor in "
                        f"IDCrossRef — no translation path to a locked provider"
                    ),
                )
            )
    return issues


# ---------------------------------------------------------------------------
# 6 — idcrossref_cycle
# ---------------------------------------------------------------------------


def _check_idcrossref_cycles(
    providers_config: ProvidersConfig,
    providers: dict[str, object],
) -> list[ConfigIssue]:
    """DFS cycle detection on the IDCrossRef graph.

    The IDCrossRef section is a flat list of providers that can translate
    between each other's ID spaces. Implicit bidirectional edges exist
    between every pair of IDCrossRef providers (every provider can be
    translated to every other in the section).

    In the current minimal model:
    - 0 or 1 IDCrossRef providers → no possible cycle
    - 2 providers → one bidirectional edge, no cycle (no self-loop)
    - ≥ 3 providers → fully connected graph; cycles exist but are inherent

    This implementation is **conservative**: it will rarely fire. A real
    cycle-detection implementation would require explicit per-provider
    edge declarations in the config model.
    """
    issues: list[ConfigIssue] = []
    section = providers_config.model_dump().get("IDCrossRef", {})
    xref_names = list(section.keys())
    if len(xref_names) < 2:
        return issues  # no possible cycle with 0 or 1 nodes

    # Build adjacency: fully connected bidirectional graph among IDCrossRef
    # providers that are actually instantiated.
    nodes = [n for n in xref_names if n in providers]
    adj: dict[str, set[str]] = {}
    for n in nodes:
        adj[n] = set(nodes) - {n}

    visited_all: set[str] = set()

    def _dfs(current: str, parent: str | None, path: list[str]) -> list[str] | None:
        """Return the cycle path if one is found, else None.

        ``parent`` is tracked so the immediate-parent edge (bidirectional
        implicit edge between two providers) is not flagged as a cycle.
        """
        if current in path:
            idx = path.index(current)
            return path[idx:] + [current]
        if current in visited_all:
            return None
        visited_all.add(current)
        path.append(current)
        for neighbor in sorted(adj.get(current, set())):
            if neighbor == parent:
                continue
            result = _dfs(neighbor, current, path)
            if result is not None:
                return result
        path.pop()
        return None

    for start in sorted(nodes):
        if start in visited_all:
            continue
        cycle = _dfs(start, None, [])
        if cycle is not None:
            cycle_str = " → ".join(cycle)
            issues.append(
                ConfigIssue(
                    code="idcrossref_cycle",
                    section="IDCrossRef",
                    provider=RegistryProviderName(start),
                    message=f"IDCrossRef cycle detected: {cycle_str}",
                )
            )
            break  # one cycle is enough to diagnose

    return issues


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_config(
    providers_config: ProvidersConfig,
    providers: dict[str, object],
    settings: Settings,
) -> list[ConfigIssue]:
    """Aggregate all six ``ConfigIssue`` families into a single list.

    **Never raises directly** — the caller (registry ``__init__``) wraps
    with ``try/finally`` + cleanup and raises ``RegistryConfigError``
    only after all checks complete (DESIGN §7.2 C11).

    Args:
        providers_config: The parsed ``ProvidersConfig`` model.
        providers: ``{name: instance}`` dict from ``build_providers()``.
        settings: The pipeline ``Settings`` instance for credential checks.

    Returns:
        A list of ``ConfigIssue`` entries, possibly empty.
    """
    issues: list[ConfigIssue] = []
    issues.extend(_check_missing_credentials(providers_config, settings))
    issues.extend(_check_protocol_mismatch(providers_config, providers))
    issues.extend(_check_unknown_providers(providers_config, providers))
    issues.extend(_check_empty_chain_sections(providers_config))
    issues.extend(_check_locked_capability_orphans(providers_config, providers))
    issues.extend(_check_idcrossref_cycles(providers_config, providers))
    return issues
