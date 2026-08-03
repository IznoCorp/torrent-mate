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

import logging

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


class TestTheRealWritePath:
    """Through ``configure_logging`` and out to the FILE — not the unit alone.

    The blind spot that let three separate leaks survive: every earlier test
    called ``redact_secrets`` directly, so nothing proved the processor was
    actually wired into the paths that write to disk. It was not — stdlib
    records bypassed it entirely, and ``exc_info`` was rendered after it.
    """

    @staticmethod
    def _configured(tmp_path: object) -> object:
        """Point the logger at a temp dir and configure it; return the log file."""
        import personalscraper.logger as lg

        lg.LOGS_DIR = tmp_path  # type: ignore[assignment]
        lg.configure_logging()
        return tmp_path / "personalscraper.json"  # type: ignore[operator]

    def test_structlog_event_is_redacted_in_the_file(self, tmp_path) -> None:
        """The baseline: our own logger writes a redacted line."""
        import personalscraper.logger as lg

        path = self._configured(tmp_path)
        lg.get_logger("t").warning("api_error", url=LEAKED_URL)
        logging.shutdown()
        assert "SUPERSECRETKEY123" not in path.read_text()  # type: ignore[attr-defined]

    def test_stdlib_record_is_redacted_in_the_file(self, tmp_path) -> None:
        """Redact stdlib records too.

        urllib3 & friends never touch structlog's processors, yet urllib3 logs
        the full URL at WARNING on every retry.
        """
        path = self._configured(tmp_path)
        logging.getLogger("urllib3.connectionpool").warning("Retrying %s", LEAKED_URL)
        logging.shutdown()
        assert "SUPERSECRETKEY123" not in path.read_text()  # type: ignore[attr-defined]

    def test_exception_field_is_redacted_in_the_file(self, tmp_path) -> None:
        """Redact the rendered traceback.

        ``format_exc_info`` turns ``exc_info`` into a string, so the redaction
        must run AFTER it or the traceback text leaks verbatim.
        """
        import personalscraper.logger as lg

        path = self._configured(tmp_path)
        try:
            raise RuntimeError(f"Max retries exceeded with url: {LEAKED_URL}")
        except RuntimeError:
            lg.get_logger("t").error("api_call_failed", exc_info=True)
        logging.shutdown()
        assert "SUPERSECRETKEY123" not in path.read_text()  # type: ignore[attr-defined]

    def test_registered_secret_value_is_redacted_anywhere(self, tmp_path) -> None:
        """Catch a secret echoed back in an unforeseen shape.

        Here an XML error body — no ``?``, no ``&``: only value matching sees it.
        """
        import personalscraper.logger as lg

        path = self._configured(tmp_path)
        lg.register_secret_values("tr4k_ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        lg.get_logger("t").warning(
            "api_error_body_unparsable",
            body_preview='<error code="100" description="bad apikey tr4k_ABCDEFGHIJKLMNOPQRSTUVWXYZ"/>',
        )
        logging.shutdown()
        assert "tr4k_ABCDEFGHIJKLMNOPQRSTUVWXYZ" not in path.read_text()  # type: ignore[attr-defined]

    def test_a_non_string_dict_key_does_not_crash_the_log_call(self) -> None:
        """Never let a log call raise.

        An int key (a season number) used to blow up ``re.match`` in the redactor.
        """
        assert _redact(per_season={1: "ok", 2: "ok"})["per_season"] == {1: "ok", 2: "ok"}

    def test_secrets_in_a_tuple_are_redacted(self) -> None:
        """Walk tuples.

        A stdlib record's ``args`` IS a tuple — the shape of every
        ``logger.warning("%s", url)``.
        """
        assert "SUPERSECRETKEY123" not in str(_redact(args=(LEAKED_URL,)))
