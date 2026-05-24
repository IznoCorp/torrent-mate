"""Tests pinning the OmdbQuotaExhausted propagation in personalscraper.scraper._xref.

Before this contract was pinned, ``safe_get_rating`` and the
``validate_id`` site in ``resolve_external_ids`` both caught
``except Exception`` — silently swallowing the new typed quota
exception and degrading "quota gone" into the same fail-soft "[]" /
"continue" path used for transient transport errors. The whole point
of the OMDB façade re-raise chain (omdb → imdb/rt) was to let
discriminating consumers stop the rating pass; the scraper layer was
breaking that promise. These tests fail if the
``except OmdbQuotaExhausted: raise`` clauses are reverted.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from personalscraper.api.metadata.omdb import OmdbQuotaExhausted
from personalscraper.scraper._xref import resolve_external_ids, safe_get_rating


class TestSafeGetRatingPropagatesQuotaExhausted:
    """safe_get_rating must propagate OmdbQuotaExhausted (not swallow as fail-soft)."""

    def test_propagates_pre_call_quota_exhausted(self) -> None:
        """Pre-call quota signal (tracker short-circuit) bubbles out."""
        client = MagicMock()
        client.get_rating.side_effect = OmdbQuotaExhausted(pre_call=True)
        with pytest.raises(OmdbQuotaExhausted) as excinfo:
            safe_get_rating(client, "tt1375666")
        assert excinfo.value.pre_call is True

    def test_propagates_runtime_quota_exhausted(self) -> None:
        """Runtime quota signal (real upstream 401) bubbles out with http_status=401."""
        client = MagicMock()
        client.get_rating.side_effect = OmdbQuotaExhausted()  # pre_call=False default
        with pytest.raises(OmdbQuotaExhausted) as excinfo:
            safe_get_rating(client, "tt1375666")
        assert excinfo.value.pre_call is False
        assert excinfo.value.http_status == 401

    def test_returns_empty_on_generic_exception(self) -> None:
        """Non-quota exceptions still fall back to [] (fail-soft preserved)."""
        client = MagicMock()
        client.get_rating.side_effect = RuntimeError("transient transport")
        assert safe_get_rating(client, "tt1375666") == []

    def test_returns_list_on_success(self) -> None:
        """Happy path unaffected."""
        from personalscraper.api.metadata._base import Notations

        client = MagicMock()
        notation = Notations(provider="omdb", source="imdb", score=8.5)
        client.get_rating.return_value = [notation]
        result = safe_get_rating(client, "tt1375666")
        assert result == [notation]


class TestResolveExternalIdsPropagatesQuotaExhausted:
    """resolve_external_ids must propagate OmdbQuotaExhausted from validate_id + get_rating."""

    def _family_to_client(self, mapping):
        """Build a family→client closure from a {family: client} dict."""
        return lambda family: mapping.get(family)

    def test_validate_id_quota_propagates(self) -> None:
        """OmdbQuotaExhausted raised by validate_id stops the function (not silently dropped)."""
        imdb_client = MagicMock()
        imdb_client.validate_id.side_effect = OmdbQuotaExhausted(pre_call=True)

        with pytest.raises(OmdbQuotaExhausted) as excinfo:
            resolve_external_ids(
                canonical_provider="tvdb",
                ids={"tvdb": "12345", "imdb": "tt1375666"},
                expected_title="Inception",
                expected_year=2010,
                family_to_client=self._family_to_client({"imdb": imdb_client}),
                imdb_client=imdb_client,
                rt_client=None,
            )
        assert excinfo.value.pre_call is True

    def test_get_rating_quota_propagates(self) -> None:
        """OmdbQuotaExhausted raised by safe_get_rating reaches the caller."""
        imdb_client = MagicMock()
        imdb_client.validate_id.return_value = True  # validates fine, quota hits next
        imdb_client.get_rating.side_effect = OmdbQuotaExhausted()

        with pytest.raises(OmdbQuotaExhausted):
            resolve_external_ids(
                canonical_provider="tvdb",
                ids={"tvdb": "12345", "imdb": "tt1375666"},
                expected_title="Inception",
                expected_year=2010,
                family_to_client=self._family_to_client({"imdb": imdb_client}),
                imdb_client=imdb_client,
                rt_client=None,
            )

    def test_non_quota_validate_id_failure_still_fail_soft(self) -> None:
        """A generic validate_id exception is still swallowed (fail-soft preserved)."""
        imdb_client = MagicMock()
        imdb_client.validate_id.side_effect = RuntimeError("network timeout")
        # No get_rating call expected since validate_id failed.

        trusted, ratings = resolve_external_ids(
            canonical_provider="tvdb",
            ids={"tvdb": "12345", "imdb": "tt1375666"},
            expected_title="Inception",
            expected_year=2010,
            family_to_client=self._family_to_client({"imdb": imdb_client}),
            imdb_client=imdb_client,
            rt_client=None,
        )
        # imdb dropped (not trusted) because validation failed, but no exception escaped.
        assert "imdb" not in trusted
        assert "tvdb" in trusted
        assert ratings == []
