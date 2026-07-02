"""Static drift guards for PM2 ecosystem.config.js (Phase 8 cutover).

Validates that the PM2 ecosystem file at the repo root stays in sync with the
design: three apps (one daemon + two cron jobs), correct ``interpreter`` /
``cwd``, proper ``autorestart`` vs ``cron_restart`` segregation, and valid cron
expressions.

Test strategy:
    Parse ``ecosystem.config.js`` pragmatically from Python — regex-based
    extraction of the ``module.exports = { apps: [...] }`` CommonJS structure.
    No Node dependency.  Then assert each app block's required fields and
    invariants.  All tests that consume parsed apps call
    :func:`_parse_ecosystem_apps` directly so failures in the parse step surface
    as clear assertion errors rather than fixture-setup crashes.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ECOSYSTEM_PATH = Path(__file__).parent.parent.parent / "ecosystem.config.js"

_EXPECTED_APP_NAMES = frozenset(
    {
        "personalscraper-watch",
        "personalscraper-index-enrich",
        "personalscraper-backfill-ids",
    }
)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _strip_js_comments(text: str) -> str:
    """Remove ``//`` and ``/* */`` comments from JavaScript source text.

    Args:
        text: Raw JS source.

    Returns:
        The source text with all comments replaced by empty strings.
    """
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return text


def _parse_ecosystem_apps(path: Path) -> list[dict[str, object]]:
    """Parse ``ecosystem.config.js`` and return the list of app dicts.

    Uses regex to extract the ``module.exports = { apps: [...] }`` CommonJS
    structure.  Each app dict contains the keys found in the object literal
    (strings unquoted, booleans as Python ``bool``, ``__dirname`` as the
    string ``"__dirname"``, integers as ``int``).

    Args:
        path: Path to ``ecosystem.config.js``.

    Returns:
        List of app dicts.  Empty if the file cannot be parsed.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    raw = path.read_text()
    clean = _strip_js_comments(raw)

    # Extract the apps array body between apps: [ and the matching ].
    m = re.search(r"apps\s*:\s*\[(.*)\]\s*,?\s*\}", clean, re.DOTALL)
    if not m:
        return []

    apps_text = m.group(1)

    # Split into top-level { ... } blocks (brace-depth tracker).
    app_blocks: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in apps_text:
        if ch == "{":
            if depth == 0:
                buf = []
            depth += 1
            buf.append(ch)
        elif ch == "}":
            depth -= 1
            buf.append(ch)
            if depth == 0:
                app_blocks.append("".join(buf))
        elif depth > 0:
            buf.append(ch)

    result: list[dict[str, object]] = []
    for block in app_blocks:
        app: dict[str, object] = {}
        for m_kv in re.finditer(
            r"(\w+)\s*:\s*(?:\"([^\"]*)\"|(true|false|\d+|__dirname))\s*,?",
            block,
        ):
            key = m_kv.group(1)
            str_val = m_kv.group(2)
            lit_val = m_kv.group(3)

            if str_val is not None:
                app[key] = str_val
            elif lit_val == "true":
                app[key] = True
            elif lit_val == "false":
                app[key] = False
            elif lit_val == "__dirname":
                app[key] = "__dirname"
            elif lit_val is not None and lit_val.isdigit():
                app[key] = int(lit_val)
            else:
                app[key] = lit_val
        result.append(app)

    return result


def _is_valid_cron_5field(expr: str) -> bool:
    """Return ``True`` if *expr* looks like a valid 5-field cron expression.

    Validates that the expression has exactly 5 space-separated fields and
    each field is a wildcard (``*``), integer, range (``N-M``), step
    (``*/N``), or comma-separated list of the above.

    Args:
        expr: A cron expression string (e.g. ``"30 4 * * 0"``).

    Returns:
        ``True`` if the expression passes structural validation.
    """
    parts = expr.strip().split()
    if len(parts) != 5:
        return False
    field_re = re.compile(r"^(\*|\d+|\d+-\d+|\*/\d+)(,\d+)*$")
    return all(field_re.match(p) for p in parts)


def _get_app_by_name(apps: list[dict[str, object]], name: str) -> dict[str, object]:
    """Return the app dict with the given *name*, or raise ``StopIteration``.

    Args:
        apps: Parsed app list from :func:`_parse_ecosystem_apps`.
        name: App name to look up.

    Returns:
        The matching app dict.

    Raises:
        StopIteration: If no app with *name* is found.
    """
    return next(a for a in apps if a["name"] == name)


# ---------------------------------------------------------------------------
# Tests — file-level existence & structure
# ---------------------------------------------------------------------------


def test_ecosystem_file_exists() -> None:
    """``ecosystem.config.js`` must exist at the repo root."""
    assert _ECOSYSTEM_PATH.is_file(), f"ecosystem.config.js not found at {_ECOSYSTEM_PATH}"


def test_ecosystem_parses_as_valid_module_exports() -> None:
    """The file must parse as a CommonJS module with a non-empty apps array."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    assert isinstance(apps, list), f"Expected list of apps, got {type(apps)}"
    assert len(apps) >= 1, "Expected at least one app in ecosystem.config.js"


def test_ecosystem_exactly_three_apps() -> None:
    """``ecosystem.config.js`` must declare exactly the 3 expected app names."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    names = {str(a["name"]) for a in apps}
    assert names == _EXPECTED_APP_NAMES, f"Expected apps {sorted(_EXPECTED_APP_NAMES)}, got {sorted(names)}"


# ---------------------------------------------------------------------------
# Tests — per-app invariants (parametrised over the 3 expected names)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("app_name", sorted(_EXPECTED_APP_NAMES))
def test_every_app_has_interpreter_none(app_name: str) -> None:
    """Every app must use ``interpreter: "none"`` (personalscraper is a Python CLI).

    Args:
        app_name: Name of the app under test.
    """
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    app = _get_app_by_name(apps, app_name)
    assert app.get("interpreter") == "none", f"{app_name}: interpreter must be 'none', got {app.get('interpreter')!r}"


@pytest.mark.parametrize("app_name", sorted(_EXPECTED_APP_NAMES))
def test_every_app_has_cwd_dirname(app_name: str) -> None:
    """Every app must use ``cwd: __dirname`` (run from the repo root).

    Args:
        app_name: Name of the app under test.
    """
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    app = _get_app_by_name(apps, app_name)
    assert app.get("cwd") == "__dirname", f"{app_name}: cwd must be __dirname, got {app.get('cwd')!r}"


# ---------------------------------------------------------------------------
# Tests — watch daemon specifics
# ---------------------------------------------------------------------------


def test_watch_app_args() -> None:
    """``personalscraper-watch`` must have ``args: "watch"``."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    watch = _get_app_by_name(apps, "personalscraper-watch")
    assert watch.get("args") == "watch", f"watch app: expected args 'watch', got {watch.get('args')!r}"


def test_watch_app_autorestart_true() -> None:
    """``personalscraper-watch`` must have ``autorestart: true``."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    watch = _get_app_by_name(apps, "personalscraper-watch")
    assert watch.get("autorestart") is True, f"watch app: expected autorestart=true, got {watch.get('autorestart')!r}"


def test_watch_app_no_cron_restart() -> None:
    """``personalscraper-watch`` must NOT have ``cron_restart`` (it is a daemon)."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    watch = _get_app_by_name(apps, "personalscraper-watch")
    assert "cron_restart" not in watch, "watch app must not have cron_restart (it is a daemon, not a cron job)"


# ---------------------------------------------------------------------------
# Tests — enrich cron specifics
# ---------------------------------------------------------------------------


def test_enrich_app_autorestart_false() -> None:
    """``personalscraper-index-enrich`` must have ``autorestart: false``."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    enrich = _get_app_by_name(apps, "personalscraper-index-enrich")
    assert enrich.get("autorestart") is False, (
        f"enrich app: expected autorestart=false, got {enrich.get('autorestart')!r}"
    )


def test_enrich_app_has_cron_restart() -> None:
    """``personalscraper-index-enrich`` must have a ``cron_restart`` field."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    enrich = _get_app_by_name(apps, "personalscraper-index-enrich")
    assert "cron_restart" in enrich, "enrich app must have cron_restart"


def test_enrich_app_cron_is_valid_5field_with_sunday() -> None:
    """``personalscraper-index-enrich`` cron must be valid 5-field with Sunday (0/7)."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    enrich = _get_app_by_name(apps, "personalscraper-index-enrich")
    cron = enrich["cron_restart"]
    assert isinstance(cron, str), f"enrich cron_restart must be str, got {type(cron)}"
    assert _is_valid_cron_5field(cron), f"enrich app: cron_restart '{cron}' is not a valid 5-field cron expression"
    dow = cron.strip().split()[4]
    assert dow in ("0", "7"), f"enrich app: cron_restart day-of-week must be Sunday (0 or 7), got '{dow}'"


def test_enrich_app_args_contains_mode_enrich() -> None:
    """``personalscraper-index-enrich`` args must contain ``library-index --mode enrich``."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    enrich = _get_app_by_name(apps, "personalscraper-index-enrich")
    args = enrich.get("args", "")
    assert isinstance(args, str), f"enrich args must be str, got {type(args)}"
    assert "library-index" in args, f"enrich app: args must contain 'library-index', got {args!r}"
    assert "--mode enrich" in args, f"enrich app: args must contain '--mode enrich', got {args!r}"


# ---------------------------------------------------------------------------
# Tests — backfill cron specifics
# ---------------------------------------------------------------------------


def test_backfill_app_autorestart_false() -> None:
    """``personalscraper-backfill-ids`` must have ``autorestart: false``."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    backfill = _get_app_by_name(apps, "personalscraper-backfill-ids")
    assert backfill.get("autorestart") is False, (
        f"backfill app: expected autorestart=false, got {backfill.get('autorestart')!r}"
    )


def test_backfill_app_has_cron_restart() -> None:
    """``personalscraper-backfill-ids`` must have a ``cron_restart`` field."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    backfill = _get_app_by_name(apps, "personalscraper-backfill-ids")
    assert "cron_restart" in backfill, "backfill app must have cron_restart"


def test_backfill_app_cron_is_valid_5field_with_sunday() -> None:
    """``personalscraper-backfill-ids`` cron must be valid 5-field with Sunday (0/7)."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    backfill = _get_app_by_name(apps, "personalscraper-backfill-ids")
    cron = backfill["cron_restart"]
    assert isinstance(cron, str), f"backfill cron_restart must be str, got {type(cron)}"
    assert _is_valid_cron_5field(cron), f"backfill app: cron_restart '{cron}' is not a valid 5-field cron expression"
    dow = cron.strip().split()[4]
    assert dow in ("0", "7"), f"backfill app: cron_restart day-of-week must be Sunday (0 or 7), got '{dow}'"


def test_backfill_app_args_contains_backfill() -> None:
    """``personalscraper-backfill-ids`` args must contain ``library-backfill-ids``."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    backfill = _get_app_by_name(apps, "personalscraper-backfill-ids")
    args = backfill.get("args", "")
    assert isinstance(args, str), f"backfill args must be str, got {type(args)}"
    assert "library-backfill-ids" in args, f"backfill app: args must contain 'library-backfill-ids', got {args!r}"


# ---------------------------------------------------------------------------
# Tests — cross-cutting invariants (daemon vs cron segregation)
# ---------------------------------------------------------------------------


def test_cron_apps_do_not_have_autorestart_true() -> None:
    """Any app with ``cron_restart`` must NOT have ``autorestart: true``."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    for app in apps:
        if "cron_restart" in app:
            name = app["name"]
            assert app.get("autorestart") is not True, f"{name}: cron job must not have autorestart=true"


def test_daemon_apps_do_not_have_cron_restart() -> None:
    """Any app with ``autorestart: true`` must NOT have ``cron_restart``."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    for app in apps:
        if app.get("autorestart") is True:
            name = app["name"]
            assert "cron_restart" not in app, f"{name}: daemon must not have cron_restart"
