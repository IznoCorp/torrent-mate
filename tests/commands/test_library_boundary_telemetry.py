"""Free-coverage telemetry assert for boundary-migrated library commands (P3.4).

The ``boundary()`` decorator records the same ``cli.invoke`` / ``cli.complete``
structured telemetry as the root ``@cli_telemetry`` hook (COMMANDS-CLI-05).
Migrating the previously un-instrumented library sub-app commands onto the
boundary therefore gives them that operator-audit telemetry for free. This pins
that a formerly-uninstrumented read command (``library-search``, now on the
``needs="config"`` tier) records BOTH lifecycle events — regression coverage so
the free telemetry is not silently lost in a future refactor.
"""

from __future__ import annotations

from unittest.mock import patch

from tests.commands._e2e_helpers import (
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


def test_library_search_records_boundary_telemetry(tmp_path, test_config) -> None:
    """A boundary-migrated read command emits cli.invoke + cli.complete telemetry.

    The telemetry lands on the structlog stderr channel (the machine-readable
    stdout stays clean JSON, which is why the JSON e2e tests parse ``.stdout``).
    """
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-search", "year:2020"])

    assert result.exit_code == 0, result.output
    # The command name is the wrapped function's __name__ (``library_search``).
    assert "cli.invoke.library_search" in result.stderr, result.stderr
    assert "cli.complete.library_search" in result.stderr, result.stderr
