"""Regression tests for ``_eligible()`` strict allowlist (sub-phase 6.1).

Verifies the three no-circuit eligibility categories:

1. **Documented no-circuit providers** (IMDb / RottenTomatoes façades) — allowed.
2. **Test fakes** (``Fake*`` / ``_Fake*`` class names) — allowed.
3. **Unknown real provider without circuit** — rejected with a warning.
"""

from __future__ import annotations

from typing import ClassVar

from personalscraper.api.metadata.registry._factory import _eligible


def test_eligible_unknown_provider_no_circuit_rejected(caplog):
    """Real provider without .circuit AND not in allowlist → excluded, logs WARNING."""

    class _UnknownProvider:
        provider_name: ClassVar[str] = "unknown_provider"
        # no .circuit attribute, not in allowlist

    with caplog.at_level("WARNING", logger="personalscraper.api.metadata.registry._factory"):
        result = _eligible(_UnknownProvider())

    assert result is False
    assert any("registry_provider_no_circuit" in r.message for r in caplog.records)


def test_eligible_imdb_facade_no_circuit_allowed():
    """IMDb façade (no circuit, shared with OMDb) → eligible per allowlist."""

    class _ImdbFacade:
        provider_name: ClassVar[str] = "imdb"

    assert _eligible(_ImdbFacade()) is True


def test_eligible_fake_class_no_circuit_allowed():
    """Test fake class (Fake* prefix, no circuit) → eligible heuristic."""

    class FakeProvider:
        provider_name: ClassVar[str] = "fake_test"

    assert _eligible(FakeProvider()) is True
