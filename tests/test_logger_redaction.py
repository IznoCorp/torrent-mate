"""Redaction guard for the structured logger — no credential may reach disk.

Written after a production leak: on 2026-08-02 four tr4ker API keys landed in
``logs/personalscraper.json`` in clear text, inside the ``url`` field of an
``api_error_body_unparsable`` event. The redactor DID exist; it simply could not
see them. Its URL rule was ``([?&])key=[^&]*`` — the separator had to sit
IMMEDIATELY before ``key=``, so ``?apikey=<secret>`` never matched (the
character before ``key`` is an ``i``). And no test covered ``redact_secrets``
at all, which is why the hole survived.

Two rules, tested independently, because either alone leaks:
  * a secret-looking FIELD NAME is redacted wholesale;
  * EVERY string is scrubbed for credentials embedded in a URL — a secret does
    not announce itself by the name of the field carrying it.
"""

from __future__ import annotations

import pytest

from personalscraper.logger import redact_secrets

REDACTED = "***REDACTED***"

# The literal shape that leaked in production (key replaced by a placeholder).
LEAKED_URL = "https://tr4ker.net/api/torznab?apikey=SUPERSECRETKEY123&t=tvsearch&q=Some+Show+S01"


def _redact(**fields: object) -> dict[str, object]:
    """Run the processor over one event dict."""
    return dict(redact_secrets(None, "info", dict(fields)))


class TestTheProductionLeak:
    """The exact 2026-08-02 incident must not be reproducible."""

    def test_apikey_in_a_url_field_is_redacted(self) -> None:
        """The leaked key must not survive the processor."""
        out = _redact(event="api_error_body_unparsable", url=LEAKED_URL)
        assert "SUPERSECRETKEY123" not in str(out)
        assert REDACTED in str(out["url"])

    def test_the_rest_of_the_url_survives(self) -> None:
        """Only the VALUE goes — the line stays useful for debugging."""
        # Redaction must stay useful for debugging: only the VALUE goes.
        url = str(_redact(url=LEAKED_URL)["url"])
        assert url.startswith("https://tr4ker.net/api/torznab?apikey=")
        assert "t=tvsearch" in url and "q=Some+Show+S01" in url

    def test_the_old_rule_would_have_missed_it(self) -> None:
        """Document why this suite exists: the old regex could not see it."""
        # Documents WHY this suite exists: the previous regex required the
        # separator immediately before `key=`.
        import re

        old = re.compile(r"([?&])key=[^&]*")
        assert old.search(LEAKED_URL) is None, "the old rule could not see the leak"


class TestSecretQueryParameters:
    """Any credential-bearing parameter, however it is spelled."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://x.test/api?apikey=SECRETVALUE",
            "https://x.test/api?api_key=SECRETVALUE",
            "https://x.test/api?API-KEY=SECRETVALUE",
            "https://x.test/api?t=search&apikey=SECRETVALUE&q=dune",
            "https://x.test/rss?passkey=SECRETVALUE",
            "https://x.test/api?token=SECRETVALUE",
            "https://x.test/api?tmdb_api_key=SECRETVALUE",
            "https://x.test/dl?key=SECRETVALUE",
            "https://x.test/api?authorization=SECRETVALUE",
            "https://x.test/api?signature=SECRETVALUE",
            # Percent-encoded separators: a magnet carries its announce URL
            # encoded inside `tr=`, which is where a tracker passkey hides.
            "magnet:?xt=urn:btih:abc&tr=https%3A%2F%2Ftr.test%2Fannounce%3Fpasskey%3DSECRETVALUE",
        ],
    )
    def test_value_never_survives(self, url: str) -> None:
        """No credential-bearing parameter leaks, however it is spelled."""
        assert "SECRETVALUE" not in str(_redact(url=url))

    def test_userinfo_credentials_are_redacted(self) -> None:
        """``user:password@host`` credentials are redacted too."""
        out = str(_redact(url="https://admin:SECRETVALUE@host.test/path")["url"])
        assert "SECRETVALUE" not in out
        assert out.startswith("https://admin:")

    def test_a_secret_hidden_in_an_innocuous_field_name(self) -> None:
        """A secret in any field name (or nested) is still caught."""
        # The leak rode in a field called `url`; it could as well ride in
        # `detail`, `message` or a nested payload.
        out = _redact(detail={"request": [f"GET {LEAKED_URL}"]})
        assert "SUPERSECRETKEY123" not in str(out)


class TestNoOverRedaction:
    """Redaction must not eat legitimate values — the repo learned this once."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://x.test/api?monkey=12",  # 'key' not on a segment boundary
            "https://x.test/api?turnkey=1",
            "https://x.test/search?q=the+key+of+life&page=2",
        ],
    )
    def test_lookalike_parameters_are_left_alone(self, url: str) -> None:
        """``monkey``/``turnkey`` are not secrets — leave them alone."""
        assert _redact(url=url)["url"] == url

    @pytest.mark.parametrize("field", ["token_count", "secret_count", "cookie_count"])
    def test_counter_fields_keep_their_value(self, field: str) -> None:
        """Counter fields keep their integer value."""
        assert _redact(**{field: 7})[field] == 7

    def test_plain_strings_pass_through(self) -> None:
        """Ordinary events pass through untouched."""
        assert _redact(event="acquire.grab.succeeded", title="Dune (2021)") == {
            "event": "acquire.grab.succeeded",
            "title": "Dune (2021)",
        }


class TestSecretFieldNames:
    """The pre-existing field-name layer must keep working."""

    @pytest.mark.parametrize("field", ["api_key", "apikey", "authorization", "cookie", "secret", "token", "password"])
    def test_secret_field_names_are_redacted(self, field: str) -> None:
        """A secret-looking field name is redacted wholesale."""
        assert _redact(**{field: "SECRETVALUE"})[field] == REDACTED

    def test_nested_secret_field_names_are_redacted(self) -> None:
        """Nested secret field names are redacted too."""
        out = _redact(config={"providers": [{"tmdb_api_key": "SECRETVALUE"}]})
        assert "SECRETVALUE" not in str(out)
