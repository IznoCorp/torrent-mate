"""Unit tests for ``_validation.validate_config()`` (DESIGN §7.2, §8.2).

The validator function is implemented in sub-phase 0.3 and is exercised
directly — no ``ProviderRegistry`` construction needed for 8 of these
10 tests. The remaining 2 tests (``test_partial_boot_no_operation_callable``
and ``test_boot_cleanup_on_validation_failure``) hit the registry
``__init__`` cleanup path and are xfail-decorated until 0.5c lands.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from personalscraper.api.metadata.registry._errors import RegistryConfigError
from personalscraper.api.metadata.registry._validation import (
    validate_config,
)
from personalscraper.conf.models.providers import ProvidersConfig

from .conftest import (
    FakeMultiCapability,
    FakeSearchable,
    config_with_all_five_families,
    config_with_empty_chain_section,
    config_with_locked_orphan,
    config_with_unknown_provider,
)


def _settings_with_keys() -> Any:
    """Return a SimpleNamespace Settings stub with non-empty credentials."""
    return SimpleNamespace(
        tmdb_api_key="x",
        tvdb_api_key="y",
    )


def _settings_without_tmdb() -> Any:
    """Return a SimpleNamespace Settings stub with TMDB key empty."""
    return SimpleNamespace(
        tmdb_api_key="",
        tvdb_api_key="y",
    )


# ---------------------------------------------------------------------------
# 1 — missing_credentials
# ---------------------------------------------------------------------------


def test_missing_credentials_issue() -> None:
    """A provider listed in config but lacking its credential produces ``missing_credentials``."""
    config = ProvidersConfig(Searchable={"tmdb": 1})
    providers = {"tmdb": FakeSearchable(provider_name="tmdb")}
    issues = validate_config(config, providers, _settings_without_tmdb())
    codes = {i.code for i in issues}
    assert "missing_credentials" in codes


# ---------------------------------------------------------------------------
# 2 — protocol_mismatch
# ---------------------------------------------------------------------------


def test_protocol_mismatch_issue() -> None:
    """A provider listed in a section it doesn't implement produces ``protocol_mismatch``."""
    # FakeSearchable implements Searchable but NOT MovieDetailsProvider.
    config = ProvidersConfig(MovieDetailsProvider={"x": 1})
    providers = {"x": FakeSearchable(provider_name="x")}
    issues = validate_config(config, providers, _settings_with_keys())
    codes = {i.code for i in issues}
    assert "protocol_mismatch" in codes


# ---------------------------------------------------------------------------
# 3 — unknown_provider
# ---------------------------------------------------------------------------


def test_unknown_provider_issue() -> None:
    """A provider name in config that wasn't instantiated produces ``unknown_provider``."""
    config = config_with_unknown_provider()
    # Only "tmdb" is instantiated; "tmdbb" is the typo.
    providers = {"tmdb": FakeSearchable(provider_name="tmdb")}
    issues = validate_config(config, providers, _settings_with_keys())
    codes = {i.code for i in issues}
    assert "unknown_provider" in codes


def test_unknown_provider_includes_did_you_mean_suggestion() -> None:
    """The ``unknown_provider`` message contains a ``difflib.get_close_matches`` suggestion."""
    config = config_with_unknown_provider()
    providers = {"tmdb": FakeSearchable(provider_name="tmdb")}
    issues = validate_config(config, providers, _settings_with_keys())
    typo_issues = [i for i in issues if i.code == "unknown_provider" and i.provider == "tmdbb"]
    assert typo_issues, "expected an unknown_provider issue for 'tmdbb'"
    assert "did you mean" in typo_issues[0].message.lower()


# ---------------------------------------------------------------------------
# 4 — empty_chain_section
# ---------------------------------------------------------------------------


def test_empty_chain_section_issue() -> None:
    """An empty chain capability section produces ``empty_chain_section``."""
    config = config_with_empty_chain_section()
    providers = {"tmdb": FakeSearchable(provider_name="tmdb")}
    issues = validate_config(config, providers, _settings_with_keys())
    codes = {i.code for i in issues}
    assert "empty_chain_section" in codes


# ---------------------------------------------------------------------------
# 5 — locked_capability_orphan
# ---------------------------------------------------------------------------


def test_locked_capability_orphan_issue() -> None:
    """A chain provider absent from a non-empty locked section triggers the orphan code."""
    config = config_with_locked_orphan()
    # tvdb is in chain but not in the artwork locked section.
    providers = {
        "tvdb": FakeSearchable(provider_name="tvdb"),
        "tmdb": FakeSearchable(provider_name="tmdb"),
    }
    issues = validate_config(config, providers, _settings_with_keys())
    codes = {i.code for i in issues}
    assert "locked_capability_orphan" in codes


# ---------------------------------------------------------------------------
# Aggregation — fail-fast is FORBIDDEN (DESIGN §7.2 / C11)
# ---------------------------------------------------------------------------


def test_all_five_issue_families_in_one_error() -> None:
    """Validation must aggregate ALL issues — never raise on the first one.

    The user must learn every problem in one shot (DESIGN §7.2 / C11).
    A fail-fast implementation will fail this test. There are five
    ``ConfigIssue`` families since the cross-ref cycle check was removed
    with the cross-ref machinery (API-TRANSPORT-03).
    """
    config = config_with_all_five_families()
    # "tmdb" is routed through a FakeSearchable that has no
    # MovieDetailsProvider/EpisodeFetcher/ArtworkProvider methods, forcing a
    # protocol_mismatch. "tvdb" (FakeMultiCapability) satisfies its sections.
    providers = {
        "tmdb": FakeSearchable(provider_name="tmdb"),  # lacks get_episodes → protocol_mismatch under EpisodeFetcher
        "tvdb": FakeMultiCapability(provider_name="tvdb"),
    }
    # Strip credentials for tmdb to trigger missing_credentials too.
    settings = SimpleNamespace(tmdb_api_key="", tvdb_api_key="y")
    raised = False
    try:
        issues = validate_config(config, providers, settings)
        if issues:
            raise RegistryConfigError(issues)
    except RegistryConfigError as exc:
        raised = True
        codes = {i.code for i in exc.issues}
        expected = {
            "missing_credentials",
            "protocol_mismatch",
            "unknown_provider",
            "empty_chain_section",
            "locked_capability_orphan",
        }
        missing = expected - codes
        assert not missing, f"missing issue codes: {missing}; got {codes}"
    assert raised, "expected RegistryConfigError once issues collected"


# ---------------------------------------------------------------------------
# Phase 25.2 — exercise the on-disk fixture through the real validator
# ---------------------------------------------------------------------------


def test_bad_providers_fixture_loads_and_triggers_all_five_families() -> None:
    """ACC-05b: ``tests/fixtures/bad_providers.json5`` must trigger all 5 families.

    Phase 25.2 — the fixture file is checked into git for ACC-05b but the
    earlier test suite never loaded it through the real ``validate_config``.
    This left a drift gap: a future edit to the JSON5 schema (e.g. renaming
    a section) would not be caught until production. This test closes that
    gap by:

    1. Parsing the on-disk JSON5 fixture via the real
       :class:`ProvidersConfig` model.
    2. Feeding it into :func:`validate_config` with a providers dict that
       mirrors what a real ``build_providers`` call would return (minus
       the deliberately-unknown ``nobody``, and minus ``imdb`` whose
       credential is intentionally missing).
    3. Asserting that the aggregated ``RegistryConfigError`` carries
       every one of the 5 :class:`ConfigIssue` family codes documented
       in the fixture's header comment.

    Catches: drift between the fixture file and the validator's
    accepted schema. A change to the JSON5 keys would silently shrink the
    issue set; this assertion fires before the next ACC-05b re-exercise.
    """
    from pathlib import Path  # noqa: PLC0415

    import json5  # noqa: PLC0415

    fixture_path = Path(__file__).resolve().parents[5] / "tests" / "fixtures" / "bad_providers.json5"
    assert fixture_path.is_file(), f"fixture missing at {fixture_path}"
    with fixture_path.open() as fh:
        raw = json5.load(fh)
    config = ProvidersConfig.model_validate(raw)

    # Build a providers dict that matches what a real registry boot would
    # produce AFTER instantiation — i.e. only the providers that have a
    # registered builder class. ``nobody`` is the deliberate unknown
    # (Family 1); ``imdb`` is excluded so missing_credentials fires
    # without us needing to clear an OMDB env var (Family 4 also fires
    # because the validator iterates the section names).
    #
    # ``tmdb`` is routed through ``FakeSearchable`` so that the section
    # ``IDValidator: {tmdb}`` produces ``protocol_mismatch`` (Family 3) —
    # FakeSearchable does not implement IDValidator (no ``validate_id``
    # method).
    providers = {
        "tmdb": FakeSearchable(provider_name="tmdb"),  # Family 3: not IDValidator
        "tvdb": FakeSearchable(provider_name="tvdb"),  # Family 5: not KeywordProvider
    }
    # Family 4: ``imdb`` listed under RecommendationProvider but its OMDB
    # credential is missing (env var TRAKT_CLIENT_ID / OMDB_API_KEY unset).
    # We strip both to be deterministic.
    settings = SimpleNamespace(tmdb_api_key="x", tvdb_api_key="y")
    import os  # noqa: PLC0415

    os_keys_before = {k: os.environ.get(k) for k in ("OMDB_API_KEY", "TRAKT_CLIENT_ID")}
    for k in ("OMDB_API_KEY", "TRAKT_CLIENT_ID"):
        os.environ.pop(k, None)
    try:
        issues = validate_config(config, providers, settings)  # type: ignore[arg-type]
    finally:
        for k, v in os_keys_before.items():
            if v is not None:
                os.environ[k] = v

    codes = {i.code for i in issues}
    expected = {
        "unknown_provider",  # Family 1: "nobody"
        "empty_chain_section",  # Family 2: MovieDetailsProvider = {}
        "protocol_mismatch",  # Family 3: tmdb under IDValidator
        "missing_credentials",  # Family 4: imdb (no OMDB_API_KEY)
        "locked_capability_orphan",  # Family 5: tvdb under KeywordProvider
    }
    missing = expected - codes
    assert not missing, f"fixture failed to trigger families: {missing}; got {codes}"


# ---------------------------------------------------------------------------
# Registry-construction-dependent tests (xfail until 0.5c)
# ---------------------------------------------------------------------------


def test_partial_boot_no_operation_callable(build_registry: object) -> None:
    """When boot validation fails, no operation can be called on the registry.

    The registry must never reach a "partially constructed" state — the
    ``RegistryConfigError`` propagates out of ``__init__`` and the caller
    has no live instance to invoke.
    """
    config = config_with_unknown_provider()
    fakes = {"tmdb": FakeSearchable(provider_name="tmdb")}
    with pytest.raises(RegistryConfigError):
        build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]


def test_boot_cleanup_on_validation_failure(build_registry: object) -> None:
    """Providers built before validation fails must have ``.close()`` called (DESIGN §6.1.f).

    The cleanup discipline prevents leaking HTTP sessions on boot retries.

    Design: docs/reference/architecture.md#boot-sequence-design-61
    Contract: boot sequence cleanup runs on validation failure to prevent resource leaks.
    """
    # A config that will pass instantiation but fail validation (unknown provider).
    fake_a = FakeSearchable(provider_name="tmdb")
    fakes = {"tmdb": fake_a}
    config = config_with_unknown_provider()  # references "tmdbb" → unknown_provider issue
    with pytest.raises(RegistryConfigError):
        build_registry(fakes=fakes, providers_config=config)  # type: ignore[operator]
    assert fake_a.closed is True, "fake_a should have been closed during boot cleanup"
