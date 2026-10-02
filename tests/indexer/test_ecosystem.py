"""Static drift guards for PM2 ecosystem.config.js (Phase 8 cutover).

Validates that the PM2 ecosystem file at the repo root stays in sync with the
design: the eleven apps (watch daemon + seven scheduled jobs + prod/staging web + autodeploy),
correct ``interpreter`` / ``script`` / ``cwd``, scheduled jobs on the self-managed
``schedule`` loop (never PM2's ``cron_restart``, which fires twice at a boundary and kills
the run it just started), valid cron expressions, and the ENV-SEP invariant that
every daemon/cron runs from the PROD clone — never the dev checkout.

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
import shlex
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ECOSYSTEM_PATH = Path(__file__).parent.parent.parent / "ecosystem.config.js"

_EXPECTED_APP_NAMES = frozenset(
    {
        "personalscraper-watch",
        "personalscraper-index-full",
        "personalscraper-index-enrich",
        "personalscraper-backfill-ids",
        "personalscraper-follow-detect",
        "personalscraper-search",
        "personalscraper-grab",
        "personalscraper-health-check",
        "torrentmate-web",
        "torrentmate-web-staging",
        "torrentmate-autodeploy",
    }
)

#: Apps whose ``script`` is NOT the personalscraper Python CLI (so their
#: ``interpreter`` is not ``"none"``). The autodeploy poller is a bash script.
_NON_PYTHON_APP_NAMES = frozenset({"torrentmate-autodeploy"})

#: ENV-SEP canonical paths — every daemon/cron runs from the PROD clone, decoupled
#: from the dev checkout (so a cron never executes an in-flight feature branch).
_PROD_CLONE = "/Users/izno/deploy/torrentmate"
_PROD_BIN = "/Users/izno/deploy/torrentmate-venv/bin/personalscraper"
_CANONICAL_CONFIG = "/Users/izno/.torrentmate/config"

#: Python daemon/cron apps — all run the prod-clone venv binary from the prod-clone
#: cwd with the canonical config dir passed explicitly (ENV-SEP). The web apps run
#: from their OWN clones (tested in :func:`test_web_apps_run_from_their_deploy_clones`).
_SCHEDULED_JOB_NAMES = frozenset(
    {
        "personalscraper-index-full",
        "personalscraper-index-enrich",
        "personalscraper-backfill-ids",
        "personalscraper-follow-detect",
        "personalscraper-search",
        "personalscraper-grab",
        "personalscraper-health-check",
    }
)

_PROD_PYTHON_APP_NAMES = frozenset(
    {
        "personalscraper-watch",
        "personalscraper-index-full",
        "personalscraper-index-enrich",
        "personalscraper-backfill-ids",
        "personalscraper-follow-detect",
        "personalscraper-search",
        "personalscraper-grab",
        "personalscraper-health-check",
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


def _job_schedule(app: dict[str, object]) -> tuple[str, list[str]]:
    """Split a scheduled job's ``args`` into its cron expression and the CLI job it runs.

    A scheduled job is ``schedule --cron '<expr>' -- <job args>``: the self-managed loop
    (``personalscraper/scheduler.py``) that replaced PM2's ``cron_restart``.

    Args:
        app: A parsed app dict.

    Returns:
        ``(cron expression, job argv)``.

    Raises:
        AssertionError: If the args are not in the ``schedule`` shape.
    """
    argv = shlex.split(str(app.get("args", "")))
    name = app["name"]
    assert argv[:2] == ["schedule", "--cron"], f"{name}: args must start with 'schedule --cron', got {app['args']!r}"
    assert argv[3] == "--", f"{name}: the job must follow '--', got {app.get('args')!r}"
    return argv[2], argv[4:]


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


def test_ecosystem_declares_expected_apps() -> None:
    """``ecosystem.config.js`` must declare exactly the expected app names."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    names = {str(a["name"]) for a in apps}
    assert names == _EXPECTED_APP_NAMES, f"Expected apps {sorted(_EXPECTED_APP_NAMES)}, got {sorted(names)}"


# ---------------------------------------------------------------------------
# Tests — per-app invariants (parametrised over the 3 expected names)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("app_name", sorted(_EXPECTED_APP_NAMES - _NON_PYTHON_APP_NAMES))
def test_every_app_has_interpreter_none(app_name: str) -> None:
    """Every Python-CLI app must use ``interpreter: "none"`` (personalscraper is a Python CLI).

    The autodeploy poller (a bash script) is excluded — see
    :func:`test_autodeploy_app_runs_poller_via_bash`.

    Args:
        app_name: Name of the app under test.
    """
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    app = _get_app_by_name(apps, app_name)
    assert app.get("interpreter") == "none", f"{app_name}: interpreter must be 'none', got {app.get('interpreter')!r}"


@pytest.mark.parametrize("app_name", sorted(_PROD_PYTHON_APP_NAMES))
def test_python_daemons_run_from_prod_clone(app_name: str) -> None:
    """ENV-SEP: every python daemon/cron runs the PROD clone's venv binary + cwd.

    The crons/watch used to run from the dev checkout via the pyenv editable install
    (``cwd: __dirname``), so they executed whatever feature branch dev happened to be
    on — a version-skew hazard against the shared ``library.db``. They now run the prod
    clone binary + cwd with the canonical config dir passed explicitly.

    Args:
        app_name: Name of the app under test.
    """
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    app = _get_app_by_name(apps, app_name)
    assert app.get("script") == _PROD_BIN, (
        f"{app_name}: script must be the prod-clone venv binary, got {app.get('script')!r}"
    )
    assert app.get("cwd") == _PROD_CLONE, f"{app_name}: cwd must be the prod clone, got {app.get('cwd')!r}"
    assert app.get("PERSONALSCRAPER_CONFIG") == _CANONICAL_CONFIG, (
        f"{app_name}: PERSONALSCRAPER_CONFIG must be the canonical config dir, "
        f"got {app.get('PERSONALSCRAPER_CONFIG')!r}"
    )


def test_no_app_runs_from_the_dev_checkout() -> None:
    """ENV-SEP invariant: no PM2 app runs from the dev checkout.

    Guards against a regression that re-binds any app to the pyenv editable binary
    (``~/.pyenv/.../personalscraper``) or ``cwd: __dirname`` / the dev checkout path —
    which would execute an in-flight feature branch against the shared ``library.db``.
    """
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    for app in apps:
        name = app["name"]
        cwd = str(app.get("cwd", ""))
        script = str(app.get("script", ""))
        assert cwd != "__dirname", f"{name}: cwd must not be __dirname (the dev checkout)"
        assert "/dev/PersonalScraper" not in cwd, f"{name}: cwd must not be under the dev checkout, got {cwd!r}"
        assert ".pyenv" not in script, f"{name}: script must not be the pyenv editable binary, got {script!r}"


def test_no_app_config_points_inside_a_git_worktree() -> None:
    """Invariant: no PM2 app's PERSONALSCRAPER_CONFIG may point inside an ANCESTOR git working tree.

    This is the REAL invariant (DESIGN §3.4) — after relocation, the canonical
    config at ~/.torrentmate/config is outside every working tree by construction.
    The canonical dir's OWN .git is the sanctioned mini-repo (D3) and is explicitly
    excluded by the predicate (ancestor-only walk).  If any app still points at a
    path inside a checkout, the pre-relocation boot-break vector is still active
    for that app.
    """
    from personalscraper.verify.config_home import _is_inside_worktree

    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    violations: list[tuple[str, str]] = []
    for app in apps:
        config_path = app.get("PERSONALSCRAPER_CONFIG")
        if config_path is None:
            continue
        path = Path(str(config_path))
        if _is_inside_worktree(path):
            violations.append((str(app["name"]), str(path)))
    assert violations == [], (
        f"{len(violations)} app(s) have PERSONALSCRAPER_CONFIG inside a git working tree: {violations}"
    )


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


def test_watch_app_has_kill_timeout_30000() -> None:
    """``personalscraper-watch`` must have ``kill_timeout: 30000`` for graceful SIGTERM shutdown.

    The 30 s grace window covers the 1 s interruptible-sleep slice granularity
    plus the ``finally`` block (context close + shutdown log) before PM2
    escalates to SIGKILL.
    """
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    watch = _get_app_by_name(apps, "personalscraper-watch")
    assert watch.get("kill_timeout") == 30000, (
        f"watch app: expected kill_timeout=30000, got {watch.get('kill_timeout')!r}"
    )


# ---------------------------------------------------------------------------
# Tests — full-scan cron specifics
# ---------------------------------------------------------------------------
#
# `full` is the ONLY mode that retires a file the filesystem no longer has: miss
# strikes are raised there alone, and three of them tombstone a row. Nothing
# scheduled it until 2026-09-04, so rows for paths deleted or renamed months ago
# sat in the index indefinitely. Each argument below is a decision, and each is
# pinned because losing it silently un-does the schedule.


@pytest.mark.parametrize("app_name", sorted(_SCHEDULED_JOB_NAMES))
def test_scheduled_job_runs_on_the_self_managed_loop(app_name: str) -> None:
    """A scheduled job never uses PM2's ``cron_restart``: it is one long-lived ``schedule`` loop.

    PM2 6.0.8's ``cron_restart`` ticks twice around a boundary (10:59:59 then 11:00:00)
    and the second tick SIGINT-kills the run the first started — 25 health-check, 4
    search, 4 grab and 1 follow-detect runs were cut on 2026-10-02. The loop
    (``personalscraper schedule``) fires once per boundary and never while a run is going,
    so PM2 only keeps it alive (``autorestart: true``) and must not also schedule it.

    Args:
        app_name: Name of the scheduled app under test.
    """
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    app = _get_app_by_name(apps, app_name)
    assert "cron_restart" not in app, f"{app_name}: cron_restart double-ticks and kills the run it started"
    assert app.get("autorestart") is True, f"{app_name}: the loop must be kept alive (autorestart=true)"
    assert app.get("restart_delay") == 60000, f"{app_name}: a loop that dies at start must not spin"
    assert app.get("kill_timeout") == 30000, f"{app_name}: stop must let the running job finish its shutdown"
    cron, job = _job_schedule(app)
    assert _is_valid_cron_5field(cron), f"{app_name}: '{cron}' is not a valid 5-field cron expression"
    assert job, f"{app_name}: no job after '--'"


def test_index_full_app_cron_is_valid_5field_on_monday() -> None:
    """Monday small hours: the walk ends long before 03:00, and 05:00 reclaims its memory.

    Measured 2026-09-04: 22 min 00 over 97 672 files. Starting at 01:00 leaves
    1 h 38 before ``follow-detect``, and the weekly 05:00 reboot reclaims the wired
    memory the walk grows — which is why Monday beats Sunday evening.
    """
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    full = _get_app_by_name(apps, "personalscraper-index-full")
    cron, _ = _job_schedule(full)
    assert _is_valid_cron_5field(cron), f"index-full app: cron '{cron}' is not a valid 5-field expression"
    fields = cron.strip().split()
    assert fields[4] == "1", f"index-full app: day-of-week must be Monday (1), got '{fields[4]}'"
    assert fields[1] == "1", f"index-full app: hour must be 01, got '{fields[1]}'"


def test_index_full_app_runs_without_a_time_budget() -> None:
    """``--no-budget`` is load-bearing, not decoration.

    The walk takes 22 min against the 1800 s default — a 27 % margin, and a slower
    night would truncate it. A truncated walk no longer strikes anything (the
    run-level guard in ``library_index_command``), so the failure mode is a wasted
    pass rather than a false tombstone; but a pass that completes is the entire
    point of scheduling one.
    """
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    full = _get_app_by_name(apps, "personalscraper-index-full")
    args = " ".join(_job_schedule(full)[1])
    assert isinstance(args, str), f"index-full args must be str, got {type(args)}"
    assert "library-index" in args, f"index-full app: args must contain 'library-index', got {args!r}"
    assert "--mode full" in args, f"index-full app: args must contain '--mode full', got {args!r}"
    assert "--no-budget" in args, (
        f"index-full app: args must contain '--no-budget' — the 1800 s default would "
        f"truncate a 22-minute walk on a slow night. Got {args!r}"
    )


def test_index_full_app_waits_for_the_writer_lock() -> None:
    """The watch daemon's post-dispatch scans hold the indexer lock at unpredictable times.

    With the default ``--wait-for-lock 0`` the weekly run would abandon rather than
    wait, and a week's retirement would be skipped in silence.
    """
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    full = _get_app_by_name(apps, "personalscraper-index-full")
    args = " ".join(_job_schedule(full)[1])
    assert "--wait-for-lock" in args, f"index-full app: args must contain '--wait-for-lock', got {args!r}"
    waited = int(args.split("--wait-for-lock", 1)[1].split()[0])
    assert waited > 0, f"index-full app: --wait-for-lock must be > 0 (0 abandons on a busy lock), got {waited}"


# ---------------------------------------------------------------------------
# Tests — enrich cron specifics
# ---------------------------------------------------------------------------


def test_enrich_app_cron_is_valid_5field_with_sunday() -> None:
    """``personalscraper-index-enrich`` cron must be valid 5-field with Sunday (0/7)."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    enrich = _get_app_by_name(apps, "personalscraper-index-enrich")
    cron, _ = _job_schedule(enrich)
    assert _is_valid_cron_5field(cron), f"enrich app: cron '{cron}' is not a valid 5-field cron expression"
    dow = cron.strip().split()[4]
    assert dow in ("0", "7"), f"enrich app: cron day-of-week must be Sunday (0 or 7), got '{dow}'"


def test_enrich_app_args_contains_mode_enrich() -> None:
    """``personalscraper-index-enrich`` args must contain ``library-index --mode enrich``."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    enrich = _get_app_by_name(apps, "personalscraper-index-enrich")
    args = " ".join(_job_schedule(enrich)[1])
    assert isinstance(args, str), f"enrich args must be str, got {type(args)}"
    assert "library-index" in args, f"enrich app: args must contain 'library-index', got {args!r}"
    assert "--mode enrich" in args, f"enrich app: args must contain '--mode enrich', got {args!r}"


# ---------------------------------------------------------------------------
# Tests — backfill cron specifics
# ---------------------------------------------------------------------------


def test_backfill_app_cron_is_valid_5field_with_sunday() -> None:
    """``personalscraper-backfill-ids`` cron must be valid 5-field with Sunday (0/7)."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    backfill = _get_app_by_name(apps, "personalscraper-backfill-ids")
    cron, _ = _job_schedule(backfill)
    assert _is_valid_cron_5field(cron), f"backfill app: cron '{cron}' is not a valid 5-field cron expression"
    dow = cron.strip().split()[4]
    assert dow in ("0", "7"), f"backfill app: cron day-of-week must be Sunday (0 or 7), got '{dow}'"


def test_backfill_app_args_contains_backfill() -> None:
    """``personalscraper-backfill-ids`` args must contain ``library-backfill-ids``."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    backfill = _get_app_by_name(apps, "personalscraper-backfill-ids")
    args = " ".join(_job_schedule(backfill)[1])
    assert isinstance(args, str), f"backfill args must be str, got {type(args)}"
    assert "library-backfill-ids" in args, f"backfill app: args must contain 'library-backfill-ids', got {args!r}"


# ---------------------------------------------------------------------------
# Tests — follow-detect + grab cron specifics (Follow D3 auto-download)
# ---------------------------------------------------------------------------


def test_follow_detect_app_is_valid_cron_job() -> None:
    """``personalscraper-follow-detect`` runs ``follow detect`` on a valid cron."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    app = _get_app_by_name(apps, "personalscraper-follow-detect")
    assert _job_schedule(app)[1] == ["follow", "detect"], f"expected job 'follow detect', got {app.get('args')!r}"
    cron, _ = _job_schedule(app)
    assert _is_valid_cron_5field(cron), f"invalid cron {cron!r}"


def test_grab_app_is_valid_cron_job() -> None:
    """``personalscraper-grab`` runs ``grab`` on a valid cron (twice daily)."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    app = _get_app_by_name(apps, "personalscraper-grab")
    assert _job_schedule(app)[1] == ["grab"], f"expected job 'grab', got {app.get('args')!r}"
    cron, _ = _job_schedule(app)
    assert _is_valid_cron_5field(cron), f"invalid cron {cron!r}"


def test_search_app_is_valid_cron_job() -> None:
    """``personalscraper-search`` runs ``search`` on a valid cron (twice daily, 10 past)."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    app = _get_app_by_name(apps, "personalscraper-search")
    assert _job_schedule(app)[1] == ["search"], f"expected job 'search', got {app.get('args')!r}"
    cron, _ = _job_schedule(app)
    assert _is_valid_cron_5field(cron), f"invalid cron {cron!r}"


# ---------------------------------------------------------------------------
# Tests — autodeploy poller (torrentmate-autodeploy)
# ---------------------------------------------------------------------------


def test_autodeploy_app_runs_poller_via_bash() -> None:
    """``torrentmate-autodeploy`` runs the poller under ``/bin/bash``, autorestart, 60 s backoff.

    It is a shell script (not the Python CLI), so its ``interpreter`` is
    ``/bin/bash`` rather than ``none``; it is a resilient daemon (autorestart,
    no cron) with a 60 s ``restart_delay`` so a persistent failure cannot
    hot-loop PM2.
    """
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    app = _get_app_by_name(apps, "torrentmate-autodeploy")
    script = app.get("script", "")
    assert isinstance(script, str) and script.endswith("scripts/autodeploy-poll.sh"), (
        f"autodeploy script must be scripts/autodeploy-poll.sh, got {script!r}"
    )
    assert app.get("interpreter") == "/bin/bash", (
        f"autodeploy interpreter must be '/bin/bash', got {app.get('interpreter')!r}"
    )
    assert app.get("cwd") == _PROD_CLONE, (
        f"autodeploy cwd must be the prod clone ({_PROD_CLONE}), got {app.get('cwd')!r}"
    )
    assert app.get("autorestart") is True, f"autodeploy must have autorestart=true, got {app.get('autorestart')!r}"
    assert app.get("restart_delay") == 60000, (
        f"autodeploy restart_delay must be 60000, got {app.get('restart_delay')!r}"
    )
    assert "cron_restart" not in app, "autodeploy is a daemon, not a cron job"


# ---------------------------------------------------------------------------
# Tests — web apps run from their per-clone deploy checkouts (DESIGN §6)
# ---------------------------------------------------------------------------


def test_web_apps_run_from_their_deploy_clones() -> None:
    """Prod/staging web apps run from their own clone venv + cwd, sharing the real config.

    Prod (``torrentmate-web``) serves 8710 from ``~/deploy/torrentmate``; staging
    (``torrentmate-web-staging``) serves 8711 (``web --port 8711``) from
    ``~/staging/torrentmate``. Both point PERSONALSCRAPER_CONFIG at the single
    canonical config dir (DESIGN §6). Each uses its OWN venv's ``personalscraper``
    binary (per-clone isolation) and a 30 s ``kill_timeout`` for graceful uvicorn
    shutdown.
    """
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)

    prod = _get_app_by_name(apps, "torrentmate-web")
    assert prod.get("script") == "/Users/izno/deploy/torrentmate-venv/bin/personalscraper", (
        f"prod script must be the deploy-clone venv binary, got {prod.get('script')!r}"
    )
    assert prod.get("cwd") == "/Users/izno/deploy/torrentmate", (
        f"prod cwd must be the deploy clone, got {prod.get('cwd')!r}"
    )
    assert prod.get("args") == "web", f"prod args must be 'web', got {prod.get('args')!r}"
    assert prod.get("autorestart") is True, "prod web app must autorestart"
    assert prod.get("kill_timeout") == 30000, f"prod kill_timeout must be 30000, got {prod.get('kill_timeout')!r}"

    staging = _get_app_by_name(apps, "torrentmate-web-staging")
    assert staging.get("script") == "/Users/izno/staging/torrentmate-venv/bin/personalscraper", (
        f"staging script must be the staging-clone venv binary, got {staging.get('script')!r}"
    )
    assert staging.get("cwd") == "/Users/izno/staging/torrentmate", (
        f"staging cwd must be the staging clone, got {staging.get('cwd')!r}"
    )
    assert staging.get("args") == "web --port 8711", (
        f"staging args must override the port ('web --port 8711'), got {staging.get('args')!r}"
    )
    assert staging.get("autorestart") is True, "staging web app must autorestart"
    assert staging.get("kill_timeout") == 30000, (
        f"staging kill_timeout must be 30000, got {staging.get('kill_timeout')!r}"
    )

    # Both clones share the single canonical config dir (parser flattens nested
    # env keys, so PERSONALSCRAPER_CONFIG surfaces as a top-level app key).
    for app in (prod, staging):
        assert app.get("PERSONALSCRAPER_CONFIG") == _CANONICAL_CONFIG, (
            f"{app.get('name')}: PERSONALSCRAPER_CONFIG must point at the canonical config dir, "
            f"got {app.get('PERSONALSCRAPER_CONFIG')!r}"
        )


# ---------------------------------------------------------------------------
# Tests — cross-cutting invariants (daemon vs cron segregation)
# ---------------------------------------------------------------------------


def test_no_app_uses_pm2_cron_restart() -> None:
    """No app of the file may carry ``cron_restart`` — PM2's cron fires twice and kills the run."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    offenders = [str(a["name"]) for a in apps if "cron_restart" in a]
    assert offenders == [], f"apps on PM2's double-ticking cron_restart: {offenders}"


def test_scheduled_jobs_are_exactly_the_schedule_apps() -> None:
    """Every app running ``schedule`` is a known job and every known job runs ``schedule``."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    scheduled = {str(a["name"]) for a in apps if str(a.get("args", "")).startswith("schedule ")}
    assert scheduled == _SCHEDULED_JOB_NAMES, f"scheduled apps drifted: {sorted(scheduled ^ _SCHEDULED_JOB_NAMES)}"


def test_daemon_apps_do_not_have_cron_restart() -> None:
    """Any app with ``autorestart: true`` must NOT have ``cron_restart``."""
    apps = _parse_ecosystem_apps(_ECOSYSTEM_PATH)
    for app in apps:
        if app.get("autorestart") is True:
            name = app["name"]
            assert "cron_restart" not in app, f"{name}: daemon must not have cron_restart"
