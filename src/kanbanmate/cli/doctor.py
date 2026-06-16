"""``kanban doctor`` — 3-tier health check (DESIGN §4).

Validates the host, Claude, and per-repo tiers in one shot. Every check is a small
pure-ish function returning ``(name, ok: bool, detail: str)``; all external dependencies
are injectable so tests drive them through mocks without touching real pm2, claude, network,
or tmux.

The :func:`run_doctor` entry point returns ``0`` when all checks pass and ``1`` when any
fails. A check that raises is caught and reported as a FAIL with the exception detail —
a single broken check never crashes the whole doctor run.

Layering: ``cli`` is an entrypoint (DESIGN §3.2); it may shell out to system tooling.
It does not import concrete adapters here — all state/token checks are injected.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from kanbanmate.cli.doctor_health import (
    HealthFieldCheck,
    _check_health_field,
    _resolve_health_check,
)
from kanbanmate.cli.doctor_ingress import check_registry_summary, check_webhook_secret

# ---------------------------------------------------------------------------
# Injectable types — mirror the ``install.py`` ``Runner`` pattern.
# ---------------------------------------------------------------------------

# A subprocess runner that mimics :func:`subprocess.run`.
Runner = Callable[..., "subprocess.CompletedProcess[Any]"]

# A callable that probes whether an import is possible (injected so tests
# can simulate "kanbanmate not installed" without polluting the test process).
ImportCheck = Callable[[], bool]

# A callable that returns the granted GitHub token scopes as a ``frozenset[str]``
# (injected so tests bypass real network calls).
TokenScopeCheck = Callable[[], frozenset[str]]

# A callable that checks whether branch protection is enabled on a repo
# (injected so tests bypass GitHub API calls).
BranchProtectionCheck = Callable[[], tuple[bool, str]]

# A callable that performs an authenticated, board-reaching cheap probe and returns its
# token string (injected so tests bypass GitHub API calls). A raise means the board is
# unreachable / the token is rejected.
BoardProbeCheck = Callable[[], str]

# A callable that returns the declared ``kanban-*`` console-script names (injected so tests
# don't depend on the real install state).
ShimListScripts = Callable[[], list[str]]

# A ``name -> path|None`` resolver mirroring :func:`shutil.which` (injected for tests).
ShimWhich = Callable[[str], "str | None"]

# The shape of a single check result.
CheckResult = tuple[str, bool, str]

# ---------------------------------------------------------------------------
# Shared constants (must be defined before the functions that use them as
# default argument values — Python evaluates defaults at definition time).
# ---------------------------------------------------------------------------

# Default runtime root (DESIGN §4.1). Mirrors :data:`install.DEFAULT_KANBAN_ROOT`.
DEFAULT_KANBAN_ROOT = Path("~/.kanban/").expanduser()

# Default tmux socket path — mirrors the workspace adapter convention. The
# agent launcher creates sessions on this socket; it must be owned by the
# operating user (DESIGN §10).
DEFAULT_TMUX_SOCKET = f"/tmp/tmux-{os.getuid()}/default"

# PM2 app name — mirrors :data:`install.PM2_APP_NAME`.
PM2_APP_NAME = "kanban"

# Daemon heartbeat TTL in seconds. The default is derived to ``max(120, 2*idle_max)``
# in :func:`run_doctor` — at the fixed 10 s cadence this is the 120 s floor (#1), tight
# enough that a wedged daemon trips within a couple of minutes instead of the old 30 min.
# A literal 1800 default is kept here only for direct unit calls that don't supply a ttl.
HEARTBEAT_TTL = 1800.0

# The heartbeat-freshness floor (#1). Even when an operator opts into the idle back-off,
# doctor's TTL is at least this many seconds; otherwise it is ``2 * idle_max`` so a single
# missed poll under back-off doesn't false-FAIL.
HEARTBEAT_TTL_FLOOR = 120.0


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_engine_importable(import_check: ImportCheck | None = None) -> CheckResult:
    """Verify the kanbanmate engine is importable (host tier).

    Args:
        import_check: A callable returning ``True`` when the import succeeds.
            When ``None`` (production), performs a real ``import kanbanmate``.
    """
    if import_check is not None:
        try:
            ok = import_check()
        except Exception as exc:
            return ("engine importable", False, f"import probe raised: {exc}")
        if ok:
            return ("engine importable", True, "kanbanmate importable")
        return ("engine importable", False, "kanbanmate not importable (probe returned False)")

    # Production: attempt the real import.
    try:
        import kanbanmate as _km  # noqa: F401
    except Exception as exc:
        return ("engine importable", False, f"import failed: {exc}")
    return (
        "engine importable",
        True,
        f"kanbanmate imported successfully (v{getattr(_km, '__version__', '?')})",
    )


def _check_pm2_daemon(runner: Runner) -> CheckResult:
    """Verify the PM2-supervised daemon is running (host tier, DESIGN §5).

    Uses ``pm2 jlist`` (JSON output) to check whether the ``kanban`` app is
    currently registered and online.

    Args:
        runner: The injected subprocess runner (mockable in tests).
    """
    try:
        result = runner(["pm2", "jlist"], capture_output=True, text=True)
    except FileNotFoundError:
        return ("pm2 daemon", False, "pm2 command not found (is PM2 installed?)")
    except Exception as exc:
        return ("pm2 daemon", False, f"pm2 jlist failed: {exc}")

    # pm2 jlist returns a JSON array of processes. A simple substring check
    # for the app name in the output covers both "running" and "errored"
    # without importing json — the operator can inspect the detail for status.
    if PM2_APP_NAME in result.stdout:
        return ("pm2 daemon", True, f"found '{PM2_APP_NAME}' in pm2 process list")
    return ("pm2 daemon", False, f"'{PM2_APP_NAME}' not found in pm2 process list")


def _check_heartbeat_fresh(
    root: Path | str,
    *,
    now: float | None = None,
    ttl: float = HEARTBEAT_TTL,
    _time: Callable[[], float] | None = None,
) -> CheckResult:
    """Verify the daemon heartbeat is fresh (host tier, DESIGN §5 / §8.3 note).

    The daemon loop (:func:`~kanbanmate.daemon.loop.run_loop`) writes a heartbeat
    marker file (``daemon.heartbeat``) after each tick iteration. This check
    compares the file's mtime against *now*; if the age exceeds *ttl* (or the
    file is missing entirely), the daemon may be wedged.

    This is the **daemon** heartbeat, NOT the per-ticket agent heartbeat
    (which lives in ``state/<issue>.json``). See DESIGN §8.3 for the distinction.

    Args:
        root: The kanban runtime root (default ``~/.kanban/``).
        now: The current wall-clock time. When ``None`` (production), uses
            :func:`time.time`. Inject a value in tests for deterministic output.
        ttl: The maximum acceptable heartbeat age in seconds (default 1800).
        _time: A time-probe callable (injected for tests).
    """
    if _time is None:
        import time as _time_mod

        _time = _time_mod.time

    heartbeat_file = Path(root) / "daemon.heartbeat"
    if not heartbeat_file.exists():
        return (
            "daemon heartbeat",
            False,
            f"no heartbeat file at {heartbeat_file} (daemon may not be running or has never ticked)",
        )

    try:
        mtime = heartbeat_file.stat().st_mtime
    except OSError as exc:
        return ("daemon heartbeat", False, f"cannot stat heartbeat file: {exc}")

    now_val = now if now is not None else _time()
    age = now_val - mtime
    if age > ttl:
        return ("daemon heartbeat", False, f"heartbeat stale ({age:.0f}s ago, TTL={ttl:.0f}s)")

    # The marker is fresh; now read its CONTENT to surface tick HEALTH, not just liveness (#1).
    # A daemon that is alive but persistently failing (the dead-token 401-loop) writes a fresh
    # marker every tick with a climbing ``consecutive_failures`` — so a fresh-but-failing daemon
    # must FAIL doctor. A legacy plain-epoch marker (old daemon mid-upgrade) parses as healthy.
    from kanbanmate.core.heartbeat import DEFAULT_FAILURE_THRESHOLD, parse_heartbeat

    try:
        heartbeat = parse_heartbeat(heartbeat_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # An unreadable/garbage marker is a FAIL: the daemon's own liveness signal is corrupt.
        return ("daemon heartbeat", False, f"cannot parse heartbeat marker: {exc}")

    if heartbeat.consecutive_failures >= DEFAULT_FAILURE_THRESHOLD:
        return (
            "daemon heartbeat",
            False,
            f"daemon alive but FAILING — {heartbeat.consecutive_failures} consecutive tick "
            f"failures (fresh {age:.0f}s ago; check `kanban logs` / the token)",
        )
    return (
        "daemon heartbeat",
        True,
        f"heartbeat fresh ({age:.0f}s ago, TTL={ttl:.0f}s, "
        f"last_tick_ok={heartbeat.last_tick_ok}, failures={heartbeat.consecutive_failures})",
    )


def _check_plugin_present(runner: Runner) -> CheckResult:
    """Verify the kanban Claude plugin is installed (Claude tier, DESIGN §4.2).

    Drives ``claude plugin list`` and checks for ``kanban`` in the output.
    The check reuses the same detection logic as :func:`install._is_kanban_installed`.

    Args:
        runner: The injected subprocess runner (mockable in tests).
    """
    try:
        result = runner(["claude", "plugin", "list"], capture_output=True, text=True)
    except FileNotFoundError:
        return ("claude plugin", False, "claude command not found (is Claude Code installed?)")
    except Exception as exc:
        return ("claude plugin", False, f"claude plugin list failed: {exc}")

    if "kanban" in result.stdout:
        return ("claude plugin", True, "kanban plugin found in claude plugin list")
    return ("claude plugin", False, "kanban plugin not found in claude plugin list")


def _check_token(
    token_scope_check: TokenScopeCheck | None = None,
    *,
    token_load: Callable[[], str] | None = None,
) -> CheckResult:
    """Verify the GitHub token is reachable and correctly scoped (host tier, DESIGN §10).

    Reuses the scope classifier from :mod:`kanbanmate.adapters.github.token`: the token must be
    reachable (file or ``$KANBAN_TOKEN``) and carry the required ``{project, repo}`` FLOOR. Three
    outcomes mirror the PoC (#6/#7):

    * **FAIL** — a classic PAT MISSING a required scope (under-scoped); blocks ``doctor``.
    * **WARNING** — an over-scoped token (extra scopes beyond ``{project, repo}``); advisory + non-
      blocking (least-privilege is advisory, DESIGN §10; #6 downgraded the old hard-fail here).
    * **advisory** — an empty (fine-grained PAT) scope set: passes with a note (the floor cannot be
      proven, only assumed — not a silent pass).

    Args:
        token_scope_check: A zero-arg callable that returns the granted scopes
            as a ``frozenset[str]``. When ``None``, the check is skipped (tests
            that don't inject a scope check still pass).
        token_load: A zero-arg callable that returns the raw token string. When
            ``None`` and ``token_scope_check`` is also ``None``, the production path
            uses :func:`kanbanmate.adapters.github.token.load_token`.
    """
    # If a direct scope check is injected, use it (primary test path).
    if token_scope_check is not None:
        try:
            scopes = token_scope_check()
        except Exception as exc:
            return ("github token", False, f"token scope check failed: {exc}")
    elif token_load is not None:
        # Fallback for tests that want to exercise the validation path with a
        # real-ish token loader.
        try:
            _token = token_load()
        except Exception as exc:
            return ("github token", False, f"token load failed: {exc}")
        # Without a scope header we can't validate scopes — that's a note, not a fail.
        _preview = _token[:4] + "…" if len(_token) > 4 else "…"
        return ("github token", True, f"token loaded (preview: {_preview}, scope check skipped)")
    else:
        # Production path: load the token AND fetch its granted scopes from GitHub so the scope
        # check actually runs (DESIGN §10 — reject admin:org_hook or anything broader than
        # project+repo). A network hiccup degrades to a note rather than failing the whole check.
        from kanbanmate.adapters.github.token import (
            TokenAuthError,
            fetch_token_scopes,
            load_token,
        )

        try:
            _token = load_token()
        except Exception as exc:
            return ("github token", False, f"cannot load token: {exc}")
        _preview = _token[:4] + "…" if len(_token) > 4 else "…"
        try:
            scopes = fetch_token_scopes(_token)
        except TokenAuthError as exc:
            # A 401/403 is a HARD failure (#1): the token is dead or over-broad. Before #1 this
            # was mistaken for a fine-grained-PAT empty-scope advisory PASS, so an expired token
            # looked healthy — the proven silent-401 incident. FAIL the check.
            return ("github token", False, f"token rejected by GitHub: {exc}")
        except Exception as exc:  # noqa: BLE001 — a network hiccup must not fail the token check
            return (
                "github token",
                True,
                f"token loaded (preview: {_preview}, scope check skipped: {exc})",
            )

    # Classify the scopes against the required FLOOR (#6/#7). The pure
    # ``classify_scopes`` reports two orthogonal conditions — missing-required
    # (under-scoped, a FAIL) and extra (over-scoped, a WARNING) — so a single
    # check yields the PoC's three outcomes instead of one hard FAIL (NEW used to
    # call ``validate_scopes`` which RAISES on anything outside {project, repo}).
    from kanbanmate.adapters.github.token import classify_scopes

    # An empty scope set is the fine-grained-PAT advisory branch (the floor cannot
    # be proven from a fine-grained PAT, which reports no classic scopes). We
    # surface it as a pass with an explicit advisory note, NOT a silent pass.
    if not scopes:
        return (
            "github token",
            True,
            "token scopes ok (empty — likely fine-grained PAT; required floor assumed, advisory)",
        )

    missing_required, extra = classify_scopes(scopes)

    # FAIL takes precedence: a classic PAT missing a required scope cannot drive
    # the daemon (PoC ``token_required_scopes``, lower bound, fail_level=error).
    if missing_required:
        return (
            "github token",
            False,
            f"token missing required scope(s): {', '.join(sorted(missing_required))} "
            "(required floor: project + repo)",
        )

    # Over-scoped → WARNING, not a hard FAIL (#6, PoC ``token_not_overscoped``,
    # fail_level=warning). Least-privilege is advisory here, not a gate: report
    # the extra scopes but keep ok=True so doctor does not exit 1.
    if extra:
        return (
            "github token",
            True,
            f"WARNING: token is over-scoped ({', '.join(sorted(extra))}) — "
            "use a narrower PAT (advisory, not blocking)",
        )

    return ("github token", True, f"token scopes ok ({', '.join(sorted(scopes))})")


def _check_branch_protection(
    branch_check: BranchProtectionCheck | None = None,
) -> CheckResult:
    """Verify branch protection is enabled on the default branch (per-repo tier, DESIGN §4.3).

    This is an advisory check — it produces a WARN result when branch protection
    is absent but does not block the overall pass/fail. Branch protection is a
    repository-side safety net that prevents direct pushes to ``main``, which is
    important for the "merge = human only" rule (DESIGN §10).

    Args:
        branch_check: A zero-arg callable returning ``(enabled: bool, detail: str)``.
            When ``None`` (production), the check is skipped with a WARN result
            since the daemon doesn't know which repo to check without config.
    """
    if branch_check is not None:
        try:
            enabled, detail = branch_check()
        except Exception as exc:
            return ("branch protection", True, f"check skipped (error: {exc})")
        if enabled:
            return ("branch protection", True, f"branch protection enabled — {detail}")
        return ("branch protection", True, f"branch protection OFF — {detail} (advisory)")

    # No checker provided — skip with an advisory note. The per-repo tier
    # requires a target repo to check, which isn't available to the host-tier
    # doctor run. The operator can check manually.
    return ("branch protection", True, "skipped — no target repo specified (advisory)")


def _check_non_root(
    geteuid: Callable[[], int] | None = None,
) -> CheckResult:
    """Verify the current user is not root (host tier, DESIGN §10).

    The daemon and its agents must run unprivileged: ``bypassPermissions`` refuses
    under root and the tmux socket must be owned by the operating user.

    Args:
        geteuid: The effective-uid probe (injected for tests); defaults to
            :func:`os.geteuid`.
    """
    euid = os.geteuid() if geteuid is None else geteuid()
    if euid == 0:
        return ("non-root", False, "running as root — daemon must be unprivileged (DESIGN §10)")
    return ("non-root", True, f"running as uid {euid} (non-root)")


def _check_tmux_socket(
    stat_socket: Callable[[str], int] | None = None,
    *,
    geteuid: Callable[[], int] | None = None,
    socket_path: str = DEFAULT_TMUX_SOCKET,
) -> CheckResult:
    """Verify the tmux socket is owned by the current user (host tier, DESIGN §10).

    The agent launcher creates tmux sessions on the socket at *socket_path*.
    If the socket is owned by a different user (e.g. root from a prior misconfigured
    run), the agent cannot attach and the whole orchestration is broken.

    **Divergence from the PoC (#8 KEEP+DOC, ratified).** The PoC
    (``cli/plan_doctor.py:110-113``) merely WARNED on tmux socket *presence* — a
    missing/foreign socket was advisory, never a gate. NEW deliberately TIGHTENS
    this to an ownership FAIL: a socket owned by a different euid (the classic
    root-from-a-prior-run mistake) is a hard error, not a warning. The rationale is
    DESIGN §10 (non-root socket ownership): the daemon and its agents MUST run
    unprivileged, ``bypassPermissions`` refuses under root, and a foreign-owned
    socket means the launcher cannot create/attach sessions as the operating user —
    a real safety regression, not cosmetics. The presence→ownership /
    warning→error tightening is therefore intentional, the stronger §10 floor.

    Args:
        stat_socket: A callable that takes a path and returns the owner uid.
            When ``None`` (production), uses ``os.stat`` on *socket_path*.
        geteuid: The effective-uid probe (injected for tests); defaults to
            :func:`os.geteuid`.
        socket_path: The tmux socket path to check. Default value mirrors the
            workspace adapter's socket path convention.
    """
    euid = os.geteuid() if geteuid is None else geteuid()

    try:
        if stat_socket is not None:
            owner_uid = stat_socket(socket_path)
        else:
            owner_uid = os.stat(socket_path).st_uid
    except FileNotFoundError:
        return (
            "tmux socket",
            False,
            f"tmux socket not found at {socket_path} (is tmux running?)",
        )
    except OSError as exc:
        return ("tmux socket", False, f"cannot stat tmux socket: {exc}")

    if owner_uid == euid:
        return ("tmux socket", True, f"tmux socket owned by uid {euid} at {socket_path}")
    return (
        "tmux socket",
        False,
        f"tmux socket at {socket_path} owned by uid {owner_uid}, running as uid {euid}",
    )


def _check_board_reachable(
    board_probe_check: BoardProbeCheck | None = None,
) -> CheckResult:
    """Verify the board is reachable with an authenticated cheap probe (#1, host tier).

    The token-scope check (:func:`_check_token`) introspects the PAT's grants, but it does NOT
    prove the daemon can actually reach the *board* it drives — a token can be syntactically fine
    yet rejected for the specific project, or the project id can be wrong. This check runs the same
    ``cheap_probe`` the tick uses every poll, so doctor catches a board-unreachable condition the
    operator would otherwise only discover by reading daemon logs.

    A raise is a FAIL (the board is unreachable / the token is rejected for it). When no probe is
    injected — and no project is registered — the check is SKIPPED with an advisory PASS, exactly
    like the branch-protection check, so a host-tier doctor run without config is unchanged.

    Args:
        board_probe_check: A zero-arg callable that performs the probe and returns its token
            string. When ``None``, the check is skipped with an advisory PASS.
    """
    if board_probe_check is None:
        return ("board reachable", True, "skipped — no project registered (advisory)")
    try:
        token = board_probe_check()
    except Exception as exc:  # noqa: BLE001 — any probe failure is a board-unreachable FAIL
        return ("board reachable", False, f"board probe failed: {exc}")
    return ("board reachable", True, f"board reachable (probe token: {token[:12]}…)")


def _kanban_console_scripts() -> list[str]:
    """Return the declared ``kanban-*`` console-script names (group ``console_scripts``).

    Reads the installed distribution's entry points via :func:`importlib.metadata.entry_points`
    and keeps the names that start with ``kanban`` (the bare ``kanban`` CLI plus the ``kanban-*``
    agent helpers). These are the shims a launched agent must be able to invoke by name.

    Returns:
        A sorted list of console-script names beginning with ``kanban`` (empty when the package is
        not installed / declares none).
    """
    from importlib.metadata import entry_points

    eps = entry_points(group="console_scripts")
    return sorted(ep.name for ep in eps if ep.name.startswith("kanban"))


def _check_helper_shims(
    list_scripts: Callable[[], list[str]] | None = None,
    which: Callable[[str], str | None] | None = None,
) -> CheckResult:
    """Verify every ``kanban-*`` console script RESOLVES on PATH (host tier, phase 35).

    The hardened transition prompts instruct agents to call helper binaries by NAME
    (``kanban-update-body`` / ``kanban-move`` / …). The existing gate test only asserts those
    helpers are DECLARED in ``[project.scripts]`` — not that they actually resolve at runtime. A
    stale editable install can leave a freshly added entry point (the §29 ``kanban-update-body``
    case observed live) undeclared on PATH until a manual ``pip install -e .``; the launched agent
    then gets "command not found" and improvises an unsanctioned ``python -m`` path. This check
    closes that gap: it enumerates the declared ``kanban-*`` console scripts and confirms each one
    is on PATH via :func:`shutil.which`.

    Args:
        list_scripts: A zero-arg callable returning the declared ``kanban-*`` console-script names.
            When ``None`` (production), reads them from the installed distribution's entry points.
        which: A ``name -> path|None`` resolver. When ``None`` (production), uses
            :func:`shutil.which`.

    Returns:
        ``(name, ok, detail)`` — ``ok=True`` when every script resolves, ``ok=False`` naming the
        unresolved ones with a ``pip install -e .`` hint.
    """
    resolve = shutil.which if which is None else which
    try:
        scripts = _kanban_console_scripts() if list_scripts is None else list_scripts()
    except Exception as exc:  # noqa: BLE001 — an entry-point read failure is a check FAIL, not a crash
        return ("helper shims", False, f"could not enumerate console scripts: {exc}")

    if not scripts:
        # No kanban-* console scripts declared at all means the package is not installed as a
        # distribution (or declares none) — the helpers cannot resolve. Surface it as a FAIL with
        # the same remediation hint.
        return (
            "helper shims",
            False,
            "no kanban-* console scripts declared (run: pip install -e . — stale editable install)",
        )

    missing = [name for name in scripts if resolve(name) is None]
    if missing:
        return (
            "helper shims",
            False,
            f"console script(s) not on PATH: {', '.join(missing)} "
            "(run: pip install -e . — stale editable install)",
        )
    return ("helper shims", True, f"all {len(scripts)} kanban-* console scripts resolve on PATH")


def _engine_python_version() -> str:
    """Return the engine interpreter's ``MAJOR.MINOR`` version (the daemon's own python).

    Reads :data:`sys.version_info` — the interpreter running this very process IS the engine
    interpreter whose console scripts the worktree kanban-bin symlinks point at (phase 38).

    Returns:
        The ``"MAJOR.MINOR"`` string, e.g. ``"3.12"``.
    """
    import sys

    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _pyenv_global_version(
    read_version: Callable[[], str | None] | None = None,
) -> str | None:
    """Read the pyenv GLOBAL version (``~/.pyenv/version`` first line) — FAIL-SOFT to ``None``.

    A launched agent's tmux session inherits the shell's ``pyenv global`` python; when that differs
    from the engine interpreter, the agent's pyenv shims dispatch to a DIFFERENT install whose entry
    points may predate a freshly added helper (the live ``kanban-update-body`` 127 case). The phase
    38 worktree kanban-bin PATH prefix neutralises this, but doctor still SURFACES the mismatch
    advisorily so the operator knows the floor they are relying on.

    Args:
        read_version: A zero-arg callable returning the raw pyenv-version file content (injected for
            tests). When ``None`` (production), reads ``~/.pyenv/version``.

    Returns:
        The first non-empty line of the pyenv version file (``"3.11.9"`` → caller derives MAJOR.MINOR),
        or ``None`` when pyenv is not in use / the file is absent or unreadable (fail-soft).
    """
    try:
        if read_version is not None:
            raw = read_version()
        else:
            version_file = Path("~/.pyenv/version").expanduser()
            if not version_file.is_file():
                return None
            raw = version_file.read_text(encoding="utf-8")
    except OSError:
        return None
    if raw is None:
        return None
    # The file holds one version per line; the first non-empty line is the global version.
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _check_pyenv_global_twin(
    read_pyenv_version: Callable[[], str | None] | None = None,
) -> CheckResult:
    """Warn when the pyenv GLOBAL python differs from the engine interpreter (advisory, phase 38).

    ADVISORY ONLY (always ``ok=True``): a launched agent's tmux session inherits ``pyenv global``,
    and pyenv shims dispatch per ACTIVE version. When the global version differs from the engine's
    interpreter, a kanban-* helper added after the global install would exit 127 there — the live
    ``kanban-update-body`` finding. Phase 38's worktree kanban-bin PATH prefix already neutralises
    this (agents resolve helpers from the engine's interpreter regardless of pyenv global), so this
    check never BLOCKS doctor; it merely tells the operator which floor they rely on.

    Fail-soft: when pyenv is not in use (no ``~/.pyenv/version``) the check passes silently.

    Args:
        read_pyenv_version: A zero-arg callable returning the raw pyenv-version file content
            (injected for tests). When ``None`` (production), reads ``~/.pyenv/version``.

    Returns:
        ``(name, True, detail)`` — always a PASS; the detail notes a mismatch when one exists.
    """
    engine = _engine_python_version()
    global_raw = _pyenv_global_version(read_version=read_pyenv_version)
    if global_raw is None:
        return ("pyenv twin", True, f"engine python {engine}; pyenv global not detected (advisory)")
    # Compare only MAJOR.MINOR — a 3.11.9-vs-3.11.4 patch drift shares entry points, so it is benign;
    # a 3.11-vs-3.12 minor drift is the dangerous case (entry points are per-install).
    global_minor = ".".join(global_raw.split(".")[:2])
    if global_minor != engine:
        return (
            "pyenv twin",
            True,
            f"WARNING: agents inherit pyenv global {global_raw} but the engine runs python "
            f"{engine} — helpers are provisioned via the worktree kanban-bin PATH prefix "
            "(phase 38), so this is advisory only",
        )
    return ("pyenv twin", True, f"engine python {engine} matches pyenv global {global_raw}")


def _check_orphan_slots(root: Path | str) -> CheckResult:
    """Verify no concurrency-cap slot is held without a matching state file (#11).

    A ``slots/ticket-<n>`` marker reserves one of the ``concurrency_cap`` agent slots; the matching
    ``state/<n>.json`` is the live session record the reaper observes. When a state file is corrupt
    (now quarantined to ``state/corrupt/``, #11) or otherwise lost, its slot can be left HELD with no
    state — invisible to the reaper, permanently under-counting the cap until the board wedges. This
    check surfaces such orphan slots to the operator.

    **It does NOT auto-release the slot** (rank-12 verdict): a slot could still back a genuinely live
    session whose state is merely unreadable for a moment; auto-releasing it would let a new agent
    over-cap. The operator inspects and clears it manually. The check is therefore advisory in spirit
    but reports a FAIL so the condition is not lost in the noise (an orphan slot is a real defect).

    Args:
        root: The kanban runtime root holding ``slots/`` and ``state/``.

    Returns:
        ``(name, ok, detail)`` — ``ok=True`` (no orphans) or ``ok=False`` naming the orphan slots.
    """
    base = Path(root)
    slots_dir = base / "slots"
    state_dir = base / "state"
    if not slots_dir.is_dir():
        return ("orphan slots", True, "no slots directory (no agents have run yet)")
    orphans: list[str] = []
    for slot in sorted(slots_dir.glob("ticket-*")):
        # Map ``slots/ticket-<n>`` → ``state/<n>.json`` and check the state file is present.
        issue = slot.name[len("ticket-") :]
        if not (state_dir / f"{issue}.json").exists():
            orphans.append(slot.name)
    if orphans:
        return (
            "orphan slots",
            False,
            f"slot(s) held without a matching state file: {', '.join(orphans)} "
            "(a slot is pinned with no session — inspect and clear manually; NOT auto-released)",
        )
    return ("orphan slots", True, "no orphan slots (every held slot has a state file)")


# ---------------------------------------------------------------------------
# Live branch-protection checker resolution (per-repo tier wiring)
# ---------------------------------------------------------------------------


def _resolve_branch_check(root: Path) -> BranchProtectionCheck | None:
    """Build a LIVE branch-protection checker for the first registered repo.

    Ports the PoC's live probe wiring (``cli/runners.py:459-467`): it reads
    ``<root>/projects.json`` via the registry helper, resolves the FIRST
    registered project's ``repo``, and returns a zero-arg callable that probes
    that repo's ``main`` branch through the GitHub adapter. When no project is
    registered, it returns ``None`` so :func:`_check_branch_protection` keeps the
    existing advisory skip — the no-config case is UNCHANGED.

    FAIL-SOFT at resolve time: a missing/unreadable registry, a malformed entry,
    or a token-load failure must NOT crash ``doctor``. Any exception here yields
    ``None`` (the advisory skip), and the returned callable defers the actual
    network round-trip to call time, where :func:`_check_branch_protection`
    already wraps it in try/except and downgrades a failure to a skip-WARN. The
    check therefore stays ADVISORY (never blocks the overall pass/fail), matching
    the PoC's WARNING-only semantics.

    Args:
        root: The kanban runtime root holding ``projects.json``.

    Returns:
        A zero-arg ``() -> (enabled, detail)`` checker for the first registered
        repo, or ``None`` when no repo is registered (or resolution fails).
    """
    # Lazy imports keep doctor's module-level surface lean and the resolution
    # fail-soft: an import or load error degrades to the advisory skip (None)
    # rather than crashing the health check.
    try:
        from kanbanmate.adapters.github.client import GithubClient
        from kanbanmate.adapters.github.token import load_token
        from kanbanmate.cli.init import _load_registry, _projects_path

        registry = _load_registry(_projects_path(root))
        if not registry:
            # No registered project — keep the advisory skip (no target repo).
            return None
        # The PoC's ``_first_registered_repo``: the first entry's repo slug.
        first_entry = next(iter(registry.values()))
        repo = first_entry.repo
        if not repo:
            return None
        # Build the client once at resolve time. ``load_token`` may raise when no
        # token is configured — guarded here so resolution returns None (advisory
        # skip) rather than raising before the checks even run.
        client = GithubClient(load_token(), repo=repo)
    except Exception:  # noqa: BLE001 — resolution is best-effort; never crash doctor.
        return None

    def _check() -> tuple[bool, str]:
        """Probe the first registered repo's ``main`` branch protection."""
        return client.branch_protection_on("main"), f"{repo}@main"

    return _check


def _resolve_board_probe(root: Path) -> BoardProbeCheck | None:
    """Build a LIVE authenticated board probe for the first registered project (#1).

    Mirrors :func:`_resolve_branch_check`: it reads ``<root>/projects.json``, resolves the FIRST
    registered project's ``project_id`` + token, and returns a zero-arg callable that runs the same
    ``cheap_probe`` the tick uses every poll. When no project is registered (or resolution fails),
    it returns ``None`` so :func:`_check_board_reachable` keeps its advisory skip — the no-config
    host-tier run is UNCHANGED.

    FAIL-SOFT at resolve time (registry/token/import errors yield ``None``); the actual network
    round-trip is deferred to call time, where :func:`_check_board_reachable` turns a probe failure
    into a FAIL (unlike branch protection, board reachability IS a gate — a daemon that cannot read
    its board cannot drive it).

    Args:
        root: The kanban runtime root holding ``projects.json``.

    Returns:
        A zero-arg ``() -> probe_token`` board probe for the first registered project, or ``None``
        when none is registered (or resolution fails).
    """
    try:
        from kanbanmate.adapters.github.client import GithubClient
        from kanbanmate.adapters.github.token import load_token
        from kanbanmate.cli.init import _load_registry, _projects_path

        registry = _load_registry(_projects_path(root))
        if not registry:
            return None
        first_entry = next(iter(registry.values()))
        project_id = first_entry.project_id
        if not project_id:
            return None
        client = GithubClient(load_token(), project_id=project_id, repo=first_entry.repo)
    except Exception:  # noqa: BLE001 — resolution is best-effort; never crash doctor.
        return None

    def _probe() -> str:
        """Run the tick's ``cheap_probe`` against the first registered board."""
        return client.cheap_probe()

    return _probe


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_doctor(
    *,
    root: Path | str | None = None,
    runner: Runner | None = None,
    import_check: ImportCheck | None = None,
    token_scope_check: TokenScopeCheck | None = None,
    token_load: Callable[[], str] | None = None,
    branch_check: BranchProtectionCheck | None = None,
    geteuid: Callable[[], int] | None = None,
    stat_socket: Callable[[str], int] | None = None,
    board_probe_check: BoardProbeCheck | None = None,
    health_check: HealthFieldCheck | None = None,
    shim_list_scripts: ShimListScripts | None = None,
    shim_which: ShimWhich | None = None,
    pyenv_version_read: Callable[[], str | None] | None = None,
    now: float | None = None,
    ttl: float | None = None,
    idle_max: float = 10.0,
    time_callable: Callable[[], float] | None = None,
    tmux_socket_path: str = DEFAULT_TMUX_SOCKET,
) -> int:
    """Run all thirteen health checks and print a structured pass/fail table.

    Every external dependency is a keyword argument — in production all are
    ``None`` and the real system calls / imports are used; in tests every one
    is a mock so no real pm2/claude/network/tmux is touched.

    Checks (DESIGN §4):
    1. engine importable
    2. PM2 daemon up
    3. daemon heartbeat fresh AND healthy (FAIL on consecutive_failures >= 3, #1)
    4. plugin present (``claude plugin list``)
    5. GitHub token reachable + required floor {project, repo} (FAIL on missing-required / 401/403,
       WARN on over-scoped, advisory on fine-grained)
    6. board reachable — authenticated cheap probe (FAIL on unreachable; advisory skip with no
       registered project, #1)
    6b. health field — per-card Health single-select carries the 5 named options (ADVISORY)
    7. branch protection on (advisory — always passes; warns when absent)
    8. orphan slots — a held slot with no matching state file (FAIL; NOT auto-released, #11)
    9. helper shims — every declared ``kanban-*`` console script resolves on PATH (FAIL; phase 35)
    10. pyenv twin — pyenv global vs engine interpreter (advisory WARN; never blocks, phase 38)
    11. non-root; 12. tmux socket owned by current user

    **Intentionally removed (#5 KEEP+DOC).** The PoC's ``gh_installed`` check is dropped on purpose:
    NEW has no ``gh``-CLI runtime dependency (it reaches GitHub via the urllib token-scope fetch +
    REST client, never by shelling out to ``gh``), so the check is moot — its absence is deliberate.

    Each check that raises is caught and reported as FAIL — a single broken check never crashes the
    whole doctor run.

    Args:
        root: The kanban runtime root for the heartbeat file. Defaults to ``~/.kanban/``.
        runner: The subprocess runner for pm2/claude checks. Defaults to :func:`subprocess.run`.
        import_check: Inject for test (see :class:`ImportCheck`).
        token_scope_check: Inject for test (see :class:`TokenScopeCheck`).
        token_load: Inject for test — loads the raw token string.
        branch_check: Inject for test (see :class:`BranchProtectionCheck`).
        geteuid: The effective-uid probe (injected for tests).
        stat_socket: Inject for test — returns the owner uid for a path.
        board_probe_check: Inject for test (see :class:`BoardProbeCheck`); ``None`` resolves a
            live registry-derived probe in production and skips advisory when none is registered.
        health_check: Inject for test (Health-field probe); ``None`` resolves a live one (ADVISORY).
        shim_list_scripts: Inject for test — returns the declared ``kanban-*`` console-script names;
            ``None`` (production) reads them from the installed distribution's entry points.
        shim_which: Inject for test — a ``name -> path|None`` resolver; ``None`` uses
            :func:`shutil.which`.
        pyenv_version_read: Inject for test — returns the raw ``~/.pyenv/version`` content for the
            advisory pyenv-twin check; ``None`` reads the real file (fail-soft).
        now: The wall-clock time for the heartbeat age calculation.
        ttl: The maximum acceptable heartbeat age in seconds. ``None`` (the default) derives it
            as ``max(120, 2*idle_max)`` (#1); pass a value to pin it.
        idle_max: The daemon's configured idle-back-off ceiling in seconds (default 10 = the
            fixed cadence); only used to derive ``ttl`` when ``ttl`` is ``None``.
        time_callable: A time-probe callable (injected for tests).
        tmux_socket_path: The tmux socket path to check.

    Returns:
        ``0`` when ALL checks pass, ``1`` when ANY check fails.
    """
    resolved_root = DEFAULT_KANBAN_ROOT if root is None else Path(root)
    resolved_runner: Runner = subprocess.run if runner is None else runner
    # Derive the heartbeat TTL (#1): when the caller doesn't pin one, the freshness window is
    # ``max(120, 2*idle_max)`` — the 120 s floor matches the fixed 10 s cadence (a wedged daemon
    # trips in ~2 min, not the old 30 min), and ``2*idle_max`` tolerates one missed poll under back-off.
    resolved_ttl = ttl if ttl is not None else max(HEARTBEAT_TTL_FLOOR, 2 * idle_max)
    # Resolve a LIVE board probe from the registry when none is injected; ``None`` keeps the skip.
    resolved_board_probe = board_probe_check
    if resolved_board_probe is None and token_scope_check is None and token_load is None:
        resolved_board_probe = _resolve_board_probe(resolved_root)
    # Resolve a LIVE Health-field probe the same way (advisory, health-field nit; never FAILs).
    resolved_health_check = health_check
    if resolved_health_check is None and token_scope_check is None and token_load is None:
        resolved_health_check = _resolve_health_check(resolved_root)

    # Build the check list. Each entry is (label, thunk that returns CheckResult).
    # The thunks close over their injected dependencies so the loop below is uniform.
    checks: list[tuple[str, Callable[[], CheckResult]]] = [
        ("engine importable", lambda: _check_engine_importable(import_check=import_check)),
        ("pm2 daemon", lambda: _check_pm2_daemon(resolved_runner)),
        (
            "daemon heartbeat",
            lambda: _check_heartbeat_fresh(
                resolved_root, now=now, ttl=resolved_ttl, _time=time_callable
            ),
        ),
        ("claude plugin", lambda: _check_plugin_present(resolved_runner)),
        (
            "github token",
            lambda: _check_token(token_scope_check=token_scope_check, token_load=token_load),
        ),
        (
            "board reachable",
            lambda: _check_board_reachable(board_probe_check=resolved_board_probe),
        ),
        ("health field", lambda: _check_health_field(health_check=resolved_health_check)),
        # ingress-multiproject §8: advisory webhook-secret presence/perms + a multi-project registry
        # summary (both ALWAYS PASS — ingress is config, not a launch gate).
        ("webhook secret", lambda: check_webhook_secret(resolved_root)),
        ("registry", lambda: check_registry_summary(resolved_root)),
        ("branch protection", lambda: _check_branch_protection(branch_check=branch_check)),
        ("orphan slots", lambda: _check_orphan_slots(resolved_root)),
        (
            "helper shims",
            lambda: _check_helper_shims(list_scripts=shim_list_scripts, which=shim_which),
        ),
        (
            "pyenv twin",
            lambda: _check_pyenv_global_twin(read_pyenv_version=pyenv_version_read),
        ),
        ("non-root", lambda: _check_non_root(geteuid=geteuid)),
        (
            "tmux socket",
            lambda: _check_tmux_socket(
                stat_socket=stat_socket,
                geteuid=geteuid,
                socket_path=tmux_socket_path,
            ),
        ),
    ]

    all_ok = True
    rows: list[tuple[str, str, str]] = []

    for label, thunk in checks:
        try:
            name, ok, detail = thunk()
        except Exception as exc:
            name, ok, detail = label, False, f"check raised: {exc}"

        status = "PASS" if ok else "FAIL"
        rows.append((name, status, detail))
        if not ok:
            all_ok = False

    # Render the table.
    _print_table(rows)

    return 0 if all_ok else 1


def _print_table(rows: Iterable[tuple[str, str, str]]) -> None:
    """Print a formatted pass/fail table to stdout.

    Columns are padded to the widest entry so the output is readable regardless
    of detail length. Mirrors the structured-output convention from DESIGN §4.

    Args:
        rows: An iterable of ``(check_name, PASS/FAIL, detail)`` tuples.
    """
    row_list = list(rows)
    if not row_list:
        return

    name_width = max(len(r[0]) for r in row_list)
    status_width = max(len(r[1]) for r in row_list)

    # Header
    header = f"  {'Check':<{name_width}}  {'Status':<{status_width}}  Detail"
    print(header)
    print("-" * len(header))

    for name, status, detail in row_list:
        print(f"  {name:<{name_width}}  {status:<{status_width}}  {detail}")

    # Summary line.
    failures = sum(1 for _, s, _ in row_list if s == "FAIL")
    if failures:
        print(f"\n{failures} check(s) failed.")
    else:
        print("\nAll checks passed.")
