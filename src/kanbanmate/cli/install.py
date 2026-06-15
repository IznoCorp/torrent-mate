"""Host-tier installer for KanbanMate (DESIGN §4.1, §5, §10).

This module materialises the **host tier** and **Claude tier** of the three-tier
``kanban install`` model: it creates the ``~/.kanban/`` runtime skeleton, wires the PM2-supervised
daemon, and registers the Claude plugin marketplace (non-interactive, DESIGN §4.2). The per-repo
tier (§4.3) lands in a later sub-phase. The daemon process itself knows nothing about PM2 (DESIGN
§5); PM2 is purely the install/ops path driven from here through ``subprocess``.

Design constraints honoured:

* **No secret material** — the ``token`` file is seeded with a placeholder comment, never a real
  PAT. The operator pastes their ``project + repo``-scoped token afterwards (DESIGN §10).
* **No webhook, no n8n** — polling is the sole ingress (DESIGN §3.1/§4.1); nothing here registers a
  hook or an automation server.
* **Non-root** — the daemon and agents must run unprivileged (``bypassPermissions`` refuses under
  root; tmux-socket ownership). The installer refuses to run as ``uid 0`` (DESIGN §10).
* **Idempotent** — every step tolerates a prior run: directories use ``exist_ok=True``, an existing
  ``token`` is never clobbered, and PM2 "already present" outcomes are treated as success.
* **Kill-switch convention** — the ``PAUSE`` sentinel is *absent* by default; the installer never
  creates it. Its presence (created by hand) is what downgrades/halts the daemon (DESIGN §10 / H5).

Subprocess safety: every PM2 call uses an argv **list** (never ``shell=True``) and routes through an
injectable ``runner`` so tests drive a mock and never touch the real PM2 or ``~/.kanban``.

Layering: ``cli`` is an entrypoint at the top of the import hierarchy (DESIGN §3.2); it may shell
out to system tooling. It does not import concrete adapters here — the host tier is pure filesystem
+ PM2 wiring.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

# A subprocess runner injected for tests (mirrors the workspace adapters' ``Runner`` idiom). Default
# is :func:`subprocess.run`; tests pass a ``MagicMock`` and assert on the argv lists.
Runner = Callable[..., "subprocess.CompletedProcess[Any]"]

# The default runtime root (DESIGN §4.1 / §5). Configurable via the ``root`` parameter so tests pass
# a ``tmp_path`` and never touch the real home directory.
DEFAULT_KANBAN_ROOT = Path("~/.kanban/").expanduser()

# Directory mode: owner-only (rwx------). The runtime root holds the token and per-ticket state, so
# it must not be group/other readable (DESIGN §10).
ROOT_MODE = 0o700

# Token file mode: owner read/write only (rw-------). A PAT lives here once the operator pastes it
# (DESIGN §10 — token in ``~/.kanban/token``, 600, off-git).
TOKEN_MODE = 0o600

# The token skeleton filename under the kanban root.
TOKEN_FILENAME = "token"

# The kill-switch sentinel filename (DESIGN §10 / H5). NEVER created by the installer — its absence
# is the default "running" state; an operator creates it by hand to pause every launch.
PAUSE_FILENAME = "PAUSE"

# Old PoC reaper launchd label (DESIGN §11 cutover). ``kanban uninstall`` removes the plist the PoC
# installed under ``~/Library/LaunchAgents/`` to schedule the reaper — replaced by KanbanMate's
# in-daemon reaper (§8.3). The label matches the reverse-DNS string from the PoC's
# ``reaper_schedule.py`` so the uninstall targets the exact file the PoC wrote.
REAPER_LABEL = "xyz.iznogoudatall.kanban-reaper"

# Default LaunchAgents directory (macOS per-user launchd plists). Injected so tests pass a ``tmp_path``
# and never touch the real ``~/Library``.
DEFAULT_LAUNCH_AGENTS_DIR = Path("~/Library/LaunchAgents/").expanduser()

# The PM2 app name; the daemon is registered as a single named process (DESIGN §5 per-name singleton).
PM2_APP_NAME = "kanban"

# The PM2 ecosystem filename written at the repo root (DESIGN §12 repository layout).
ECOSYSTEM_FILENAME = "ecosystem.config.js"

# Placeholder body for the seeded ``token`` file — a comment, NEVER a real secret. The operator
# replaces this with a ``project + repo``-scoped PAT (DESIGN §10).
_TOKEN_PLACEHOLDER = (
    "# KanbanMate GitHub token (project + repo scopes only — NOT admin:org_hook).\n"
    "# Paste your personal access token on the next line, then save. Keep this file 600.\n"
    "# This file is off-git and must never be committed.\n"
)


class RootPrivilegeError(RuntimeError):
    """Raised when the installer is invoked as root (``uid 0``).

    The daemon and the agents it launches must run unprivileged: ``bypassPermissions`` refuses under
    root and the tmux socket must be owned by the operating user (DESIGN §10). Installing as root
    would create ``~/.kanban`` and the PM2 process under the wrong identity, so the installer
    refuses outright rather than producing a broken, privilege-mismatched setup.
    """


class ClaudeNotFoundError(RuntimeError):
    """Raised when the ``claude`` CLI binary is not found on PATH.

    The Claude tier (DESIGN §4.2) requires the ``claude`` binary to register the plugin
    marketplace and install the ``/kanban`` skill.  Without it the tier cannot be installed;
    the operator must install Claude Code first.
    """


class ClaudePluginInstallError(RuntimeError):
    """Raised when ``claude plugin install`` returns a non-zero exit code.

    The marketplace-add step is best-effort (idempotent), but the plugin install MUST succeed
    for the ``/kanban`` skill to be available.  A non-zero exit means the plugin was not
    registered — the operator sees a clear non-success message instead of the prior false
    "claude plugin registered" echo.
    """


def _ecosystem_body(*, kanban_command: str = "kanban") -> str:
    """Render the PM2 ecosystem file describing the ``kanban`` daemon app.

    The app runs ``kanban run`` (the supervisor-agnostic blocking loop, DESIGN §5) with
    ``autorestart`` so PM2 restarts it on *exit* (not on hang — the daemon's own watchdog handles
    hangs). It is deliberately minimal: the daemon reads ``~/.kanban`` itself, so no environment
    plumbing is needed here.

    Args:
        kanban_command: The console-script name to invoke; ``kanban`` by default. Exposed so a
            non-PATH install can point at an absolute path.

    Returns:
        The JavaScript source of the ecosystem file as a string.
    """
    # A plain CommonJS module exporting the single app. ``script`` + ``args`` run ``kanban run``;
    # ``interpreter: "none"`` is MANDATORY: ``kanban`` is a Python console-script, so PM2 must exec
    # it directly (its shebang selects the pyenv interpreter) — without this, PM2 defaults to running
    # the script through Node and crashes with ``SyntaxError: Unexpected identifier 'kanbanmate'``.
    # ``autorestart`` restarts on process death; ``max_restarts``/``restart_delay`` damp crash loops.
    return (
        "// KanbanMate PM2 ecosystem (generated by `kanban install`; DESIGN §5).\n"
        "// The daemon is supervisor-agnostic — it knows nothing about PM2. PM2 only restarts it\n"
        "// on EXIT (not on hang; the daemon has its own per-tick watchdog).\n"
        "module.exports = {\n"
        "  apps: [\n"
        "    {\n"
        f'      name: "{PM2_APP_NAME}",\n'
        f'      script: "{kanban_command}",\n'
        '      interpreter: "none",\n'
        '      args: "run",\n'
        "      autorestart: true,\n"
        "      max_restarts: 10,\n"
        "      restart_delay: 5000,\n"
        "    },\n"
        "  ],\n"
        "};\n"
    )


def _ensure_root_dir(root: Path) -> None:
    """Create *root* with owner-only permissions, tolerating a prior run.

    Uses ``os.makedirs(..., mode=0o700, exist_ok=True)`` and then an explicit ``os.chmod`` so the
    final mode is ``0o700`` regardless of the process umask (``makedirs`` applies the mode *minus*
    the umask on creation, and is a no-op on mode for an existing directory).

    Args:
        root: The kanban runtime root to create.
    """
    os.makedirs(root, mode=ROOT_MODE, exist_ok=True)
    # Re-assert the mode explicitly: umask may have masked bits on creation, and an existing
    # directory keeps whatever mode it already had. This makes 0o700 deterministic.
    os.chmod(root, ROOT_MODE)


def _seed_token(root: Path) -> None:
    """Seed the ``token`` skeleton (mode 0o600) without clobbering an existing one.

    Idempotent: if a ``token`` file already exists (the operator may have already pasted a real
    PAT), it is left completely untouched — content and mode preserved. Only a fresh file gets the
    placeholder body. The placeholder is a comment, never a real secret (DESIGN §10).

    Args:
        root: The kanban runtime root the token lives under.
    """
    token_path = root / TOKEN_FILENAME
    if token_path.exists():
        # Never clobber: a re-run must not erase a real token the operator already pasted.
        return
    # Create with the placeholder body, then chmod to 0o600 explicitly (umask-independent).
    token_path.write_text(_TOKEN_PLACEHOLDER, encoding="utf-8")
    os.chmod(token_path, TOKEN_MODE)


def _write_ecosystem(ecosystem_path: Path, *, kanban_command: str = "kanban") -> None:
    """Write the PM2 ecosystem file at *ecosystem_path* (overwrite-safe, idempotent).

    The body is deterministic, so overwriting on a re-run yields identical content — there is no
    operator state to preserve here (unlike the token).

    Args:
        ecosystem_path: Where to write ``ecosystem.config.js`` (repo root by default).
        kanban_command: The console-script name baked into the ecosystem file.
    """
    ecosystem_path.write_text(_ecosystem_body(kanban_command=kanban_command), encoding="utf-8")


def _run_quiet(runner: Runner, argv: list[str]) -> subprocess.CompletedProcess[Any]:
    """Run *argv* through *runner*, suppressing noise and tolerating non-zero exits.

    PM2 commands are noisy and some are *expected* to "fail" on a re-run (e.g. ``pm2 startup`` may
    report an already-configured boot hook). Output is captured (not streamed) and ``check`` is
    **not** set, so a non-zero exit is swallowed here — the caller treats "already present" as
    success, keeping the whole install idempotent (DESIGN §4.1).

    Args:
        runner: The injected subprocess runner.
        argv: The command as an argv **list** (never a shell string).

    Returns:
        The completed process (return code inspected by the caller if needed).
    """
    # capture_output keeps PM2's chatter off the console; text decodes it for any future inspection.
    return runner(argv, capture_output=True, text=True)


def host_install(
    root: Path | str | None = None,
    *,
    run_pm2: bool = True,
    runner: Runner = subprocess.run,
    ecosystem_path: Path | str | None = None,
    kanban_command: str = "kanban",
    geteuid: Callable[[], int] = os.geteuid,
) -> Path:
    """Perform the idempotent host-tier install (DESIGN §4.1).

    Steps, all idempotent:

    1. **Refuse root** — abort if running as ``uid 0`` (DESIGN §10); the daemon must be unprivileged.
    2. **Skeleton** — create *root* (mode 0o700), seed the ``token`` skeleton (mode 0o600) without
       clobbering an existing one, and leave the ``PAUSE`` sentinel **absent** (kill-switch default).
    3. **PM2 wiring** — write ``ecosystem.config.js`` then (unless ``run_pm2`` is ``False``) run
       ``pm2 start <ecosystem> --only kanban``, ``pm2 save``, ``pm2 startup`` — all quiet and
       failure-tolerant so a re-run never errors.

    No secret material, no webhook, no n8n is created at any step (DESIGN §4.1).

    Args:
        root: The kanban runtime root; defaults to ``~/.kanban/``. Pass a ``tmp_path`` in tests.
        run_pm2: When ``False``, skip the PM2 subprocess calls (still writes the ecosystem file).
            Tests set this or inject a mock ``runner``.
        runner: The subprocess runner (injected for tests); defaults to :func:`subprocess.run`.
        ecosystem_path: Where to write ``ecosystem.config.js``; defaults to the current working
            directory (the repo root). Pass an explicit path in tests.
        kanban_command: The console-script name baked into the ecosystem file and PM2 invocation.
        geteuid: The effective-uid probe (injected so tests can simulate root); defaults to
            :func:`os.geteuid`.

    Returns:
        The resolved kanban runtime root that was created/ensured.

    Raises:
        RootPrivilegeError: When invoked as root (``geteuid() == 0``).
    """
    # Step 1: non-root guard (DESIGN §10). Do this FIRST so a root invocation creates nothing.
    if geteuid() == 0:
        raise RootPrivilegeError(
            "kanban install must not run as root: the daemon and its agents run unprivileged "
            "(bypassPermissions refuses under root; tmux socket ownership). Re-run as your user."
        )

    resolved_root = DEFAULT_KANBAN_ROOT if root is None else Path(root)
    eco_path = Path(ECOSYSTEM_FILENAME) if ecosystem_path is None else Path(ecosystem_path)

    # Step 2: filesystem skeleton (idempotent; PAUSE intentionally NOT created).
    _ensure_root_dir(resolved_root)
    _seed_token(resolved_root)

    # Step 3: PM2 wiring (write the ecosystem file always; drive PM2 unless asked not to).
    _write_ecosystem(eco_path, kanban_command=kanban_command)
    if run_pm2:
        # `pm2 start <ecosystem> --only kanban`: start (or no-op if already running) just our app.
        _run_quiet(runner, ["pm2", "start", str(eco_path), "--only", PM2_APP_NAME])
        # `pm2 save`: persist the current process list so a reboot restores it.
        _run_quiet(runner, ["pm2", "save"])
        # `pm2 startup`: emit/install the boot hook; already-configured is treated as success.
        _run_quiet(runner, ["pm2", "startup"])

    return resolved_root


def host_uninstall(
    root: Path | str | None = None,
    *,
    run_pm2: bool = True,
    runner: Runner = subprocess.run,
    remove_token: bool = False,
    geteuid: Callable[[], int] = os.geteuid,
    launch_agents_dir: Path | str | None = None,
) -> Path:
    """Perform the idempotent host-tier uninstall (DESIGN §4.1, §11).

    Tears down the PM2 app, (optionally) the runtime skeleton, and the old PoC launchd reaper plist:

    1. **Refuse root** — same non-root guard as install (DESIGN §10).
    2. **PM2 teardown** — ``pm2 delete kanban`` (quiet; a "not found" outcome is tolerated so a
       re-run never errors).
    3. **Host teardown** — by default the ``token`` is **left in place** (it may hold a real PAT the
       operator wants to keep); pass ``remove_token=True`` to delete it. The ``PAUSE`` sentinel and
       runtime root are left untouched here — ``kanban reset`` archives the root (DESIGN §11).
    4. **PoC reaper plist removal** (DESIGN §11 cutover) — if the old launchd plist
       ``xyz.iznogoudatall.kanban-reaper.plist`` exists under *launch_agents_dir*, issue
       ``launchctl unload`` (best-effort, tolerates failure) then remove the file. Absent plist →
       silent skip. Idempotent — a re-run on an already-cleaned system is a no-op.

    Args:
        root: The kanban runtime root; defaults to ``~/.kanban/``. Pass a ``tmp_path`` in tests.
        run_pm2: When ``False``, skip the PM2 ``delete`` call (still performs host teardown).
        runner: The subprocess runner (injected for tests); defaults to :func:`subprocess.run`.
        remove_token: When ``True``, delete the ``token`` file as part of teardown. Default leaves
            it so a real PAT is not silently discarded.
        geteuid: The effective-uid probe (injected for tests); defaults to :func:`os.geteuid`.
        launch_agents_dir: The macOS LaunchAgents directory; defaults to
            ``~/Library/LaunchAgents/``. Pass a ``tmp_path`` in tests so the test never touches
            the real ``~/Library``.

    Returns:
        The resolved kanban runtime root that was targeted.

    Raises:
        RootPrivilegeError: When invoked as root (``geteuid() == 0``).
    """
    if geteuid() == 0:
        raise RootPrivilegeError("kanban uninstall must not run as root: re-run as your user.")

    resolved_root = DEFAULT_KANBAN_ROOT if root is None else Path(root)
    resolved_la = (
        DEFAULT_LAUNCH_AGENTS_DIR if launch_agents_dir is None else Path(launch_agents_dir)
    )

    # Step 2: PM2 teardown. `pm2 delete kanban` exits non-zero when the app is absent — tolerated.
    if run_pm2:
        _run_quiet(runner, ["pm2", "delete", PM2_APP_NAME])

    # Step 3: host teardown. Token preserved unless explicitly asked to remove it (idempotent unlink).
    if remove_token:
        token_path = resolved_root / TOKEN_FILENAME
        try:
            token_path.unlink()
        except FileNotFoundError:
            # Already gone — a re-run must not error.
            pass

    # Step 4: remove the old PoC launchd reaper plist (DESIGN §11 cutover). The PoC scheduled the
    # reaper via a launchd plist; KanbanMate's daemon has an in-process reaper (§8.3), so the plist
    # is dead weight. `launchctl unload` is best-effort (it fails when the plist was never loaded or
    # is already gone) — we still remove the file so a re-run is a clean no-op.
    plist_path = resolved_la / f"{REAPER_LABEL}.plist"
    if plist_path.exists():
        _run_quiet(runner, ["launchctl", "unload", str(plist_path)])
        plist_path.unlink()

    return resolved_root


# ============================================================================
# Claude tier — plugin marketplace + install (DESIGN §4.2)
# ============================================================================


def _is_kanban_installed(runner: Runner) -> bool:
    """Check whether ``kanban@kanbanmate`` is already registered as a Claude plugin.

    Drives ``claude plugin list``, which outputs a table of installed plugins (one per line).
    The check is a simple substring match for the plugin name — any appearance of ``kanban``
    in the output is treated as "already installed", keeping the install idempotent.

    Args:
        runner: The injected subprocess runner (mockable in tests).

    Returns:
        ``True`` when ``kanban`` appears in the ``claude plugin list`` stdout.
    """
    try:
        result = runner(["claude", "plugin", "list"], capture_output=True, text=True)
    except FileNotFoundError:
        raise ClaudeNotFoundError(
            "claude CLI not found — install Claude Code first "
            "(https://docs.anthropic.com/en/docs/claude-code/overview)"
        ) from None
    # A simple substring check: the table includes the plugin name in one column. A
    # zero-return with "kanban" anywhere in stdout means it is already installed.
    return "kanban" in result.stdout


def claude_install(
    repo_path: Path | str,
    *,
    runner: Runner = subprocess.run,
) -> None:
    """Perform the idempotent Claude-tier install (DESIGN §4.2).

    Registers this repo as a Claude plugin marketplace and installs the ``kanban`` plugin,
    both at ``--scope user`` so the setup is persistent and non-interactive. The flow:

    1. **Check already installed** — run ``claude plugin list`` and skip the whole routine
       when ``kanban`` is already present (idempotent).
    2. **Add marketplace** — ``claude plugin marketplace add <repo_path> --scope user``.
    3. **Install plugin** — ``claude plugin install kanban@kanbanmate --scope user``
       (installs and enables in one shot).

    All calls route through *runner* (argv lists, ``capture_output=True``, never
    ``shell=True``) so tests drive a mock and never touch the real ``claude`` CLI.

    Args:
        repo_path: Local path to the KanbanMate repo (the plugin marketplace source).
        runner: The subprocess runner (injected for tests); defaults to :func:`subprocess.run`.
    """
    if _is_kanban_installed(runner):
        return  # Already registered — idempotent, nothing to do.

    # Add the marketplace source pointing at this local repo.  This step is best-effort
    # (idempotent): a re-run on an already-added marketplace may exit non-zero, which is
    # tolerated.  The plugin install below is the hard gate.
    _run_quiet(
        runner, ["claude", "plugin", "marketplace", "add", str(repo_path), "--scope", "user"]
    )
    # Install and enable the kanban plugin from the kanbanmate marketplace.  This MUST
    # succeed — a failure here means the /kanban skill is unavailable, so we surface the
    # non-zero exit instead of swallowing it (errors-2).
    try:
        result = runner(
            ["claude", "plugin", "install", "kanban@kanbanmate", "--scope", "user"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise ClaudeNotFoundError(
            "claude CLI not found — install Claude Code first "
            "(https://docs.anthropic.com/en/docs/claude-code/overview)"
        ) from None
    if result.returncode != 0:
        raise ClaudePluginInstallError(
            f"claude plugin install failed (return code {result.returncode}) — "
            f"check your network and that kanban@kanbanmate is available"
        )


def claude_uninstall(
    repo_path: Path | str,
    *,
    runner: Runner = subprocess.run,
) -> None:
    """Perform the idempotent Claude-tier uninstall (DESIGN §4.2).

    Removes the ``kanban`` plugin and the marketplace source, tolerating "not found"
    outcomes so a re-run never errors:

    1. **Uninstall plugin** — ``claude plugin uninstall kanban`` (best-effort; the plugin
       may already be absent).
    2. **Remove marketplace** — ``claude plugin marketplace remove <repo_path>`` (best-effort;
       the marketplace may already be gone).

    All calls route through *runner* (argv lists, ``capture_output=True``, never
    ``shell=True``).

    Args:
        repo_path: Local path to the KanbanMate repo (the marketplace source to remove).
        runner: The subprocess runner (injected for tests); defaults to :func:`subprocess.run`.
    """
    # Uninstall the plugin; best-effort — a non-zero exit on "not found" is swallowed.
    _run_quiet(runner, ["claude", "plugin", "uninstall", "kanban"])
    # Remove the marketplace source; best-effort — tolerates already-removed.
    _run_quiet(runner, ["claude", "plugin", "marketplace", "remove", str(repo_path)])
