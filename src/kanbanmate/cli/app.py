"""The ``kanban`` Typer application: user-facing commands shelling out to the engine.

This is the CLI entrypoint named by ``pyproject``'s console script
(``kanban = "kanbanmate.cli.app:main"``). It is the thin imperative shell a human drives. Every
command from the DESIGN §3.3 CLI surface is wired here — installer tiers (``install``/``uninstall``/
``doctor``/``init``/``seed``), the daemon (``run``), and the read/ops commands (``status``/
``sessions``/``cancel``/``logs``/``reset``/``poll``). Each command body is intentionally thin: it
delegates to a dedicated ``cli/<command>.py`` module whose I/O dependencies are injectable for tests.

The module is importable with **no side effects** — building the Typer app and registering
commands does no I/O and starts no daemon. Side-effecting work happens only when a command runs.

Layering: ``cli`` is an entrypoint at the top of the hierarchy (DESIGN §3.2); it may import
``daemon`` and ``app`` freely. It does not name concrete adapters.
"""

from __future__ import annotations

from pathlib import Path

import typer

from kanbanmate.app.wiring import WiringConfig, build_deps
from kanbanmate.cli import cancel as cancel_cmd
from kanbanmate.cli import doctor as doctor_mod
from kanbanmate.cli import init as init_cmd
from kanbanmate.cli import install as host_installer
from kanbanmate.cli import logs as logs_cmd
from kanbanmate.cli import move as move_cmd
from kanbanmate.cli import pill as pill_cmd
from kanbanmate.cli import poll as poll_cmd
from kanbanmate.cli import reset as reset_cmd
from kanbanmate.cli import seed as seed_cmd
from kanbanmate.cli import sessions as sessions_cmd
from kanbanmate.cli import state as state_cmd
from kanbanmate.cli import status as status_cmd
from kanbanmate.cli import ticket as ticket_cmd
from kanbanmate.cli.board import board_app
from kanbanmate.cli.config import config_app
from kanbanmate.daemon import loop as daemon_loop
from kanbanmate.daemon.registry_wiring import ProjectSelectionError, wiring_for_selection

app = typer.Typer(
    name="kanban",
    help="Reusable Kanban orchestrator on GitHub Projects v2 (polling daemon + agents).",
    no_args_is_help=True,
    add_completion=False,
)

# Operator ticket-CRUD sub-app (cockpit PR3): `kanban ticket create ...` enqueues an intent the
# daemon executes (the bare `kanban` CLI is agent-excluded, so this stays operator-only). The
# subcommands are registered at the END of the module (they need _DEFAULT_ROOT + the helpers).
ticket_app = typer.Typer(
    name="ticket",
    help="Operator ticket CRUD via the cockpit intent queue (daemon-executed).",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(ticket_app, name="ticket")

# Operator pill-override sub-app (cockpit PR3): `kanban pill set-health|note|clear` enqueues an
# intent the daemon applies to the rolling status pill. Subcommands registered at the END of module.
pill_app = typer.Typer(
    name="pill",
    help="Operator override of the rolling status pill (daemon-applied).",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(pill_app, name="pill")

# Config management sub-app (helm PR 1): `kanban config serve` starts the headless HTTP API for
# pipeline config editing. Defined in ``cli/config.py`` (the FastAPI import is lazy there, inside
# the ``serve`` body) so the bare ``kanban`` CLI imports succeed with no ``[ui]`` extra installed.
app.add_typer(config_app, name="config")
# anchor §8: ``kanban board import`` / ``kanban board status`` sub-app.
app.add_typer(board_app, name="board")


# The ``--root`` option default, shared across commands. Resolved eagerly so the command surface
# shows the concrete path; the daemon/loop reads the same default at runtime.
_DEFAULT_ROOT = Path("~/.kanban/").expanduser()


@app.command()
def run(
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Runtime root the daemon drives (default ~/.kanban). Use a separate root to run a "
        "SECOND daemon for a different project on the same machine.",
    ),
) -> None:
    """Start the long-running poll daemon (``kanban run``).

    Hands off to :func:`kanbanmate.daemon.loop.main`, which acquires the single-instance lock and
    blocks in the adaptive poll loop until SIGTERM (DESIGN §5). ``--root`` points the daemon at an
    alternate runtime root (its own ``projects.json`` / lock / PAUSE), so a second daemon can drive
    a different project alongside the default one.

    Args:
        root: The runtime root the daemon drives; defaults to ``~/.kanban``.
    """
    daemon_loop.main(root=root)


@app.command()
def serve(
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Runtime root the receiver fronts (default ~/.kanban). Use a separate root to front a "
        "SECOND daemon on the same machine.",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Bind host (default loopback). Use 0.0.0.0 ONLY behind a TLS reverse proxy.",
    ),
    port: int = typer.Option(
        8765,
        "--port",
        help="Bind port (unprivileged; default 8765). Front it with your reverse proxy for TLS.",
    ),
) -> None:
    """Start the GitHub webhook receiver (``kanban serve``, ingress-multiproject §4).

    A hardened HTTP front-door that verifies the webhook HMAC, identifies which managed project the
    event hit, and bumps that runtime root's daemon-wake nudge — so the daemon's next tick reconciles
    the moved board in <1 s instead of waiting out the (slow) safety-sweep interval. The daemon stays
    the SOLE board writer; the receiver only nudges (it never synthesises Transitions). Runs as a
    SECOND PM2 app alongside ``kanban run`` on one runtime root. Refuses root + privileged ports.

    Args:
        root: The runtime root holding ``projects.json`` / ``webhook_secret`` / the nudge sentinel.
        host: The bind host (loopback by default; 0.0.0.0 opt-in behind a TLS proxy).
        port: The bind port (unprivileged; 8765 default).
    """
    from kanbanmate.http import serve as http_serve

    # Fail LOUD on a start-time guard (no real secret / root / privileged port) — a clean non-zero
    # exit with the actionable message, never a raw traceback (#3 part b: refuse to start without a
    # real secret). A placeholder/empty/comment-only secret raises WebhookSecretMissingError here.
    try:
        http_serve.main(root=root, host=host, port=port)
    except (
        http_serve.WebhookSecretMissingError,
        http_serve.RootPrivilegeError,
        http_serve.PrivilegedPortError,
    ) as exc:
        typer.echo(f"kanban serve: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _wiring_for(
    root: Path,
    *,
    project: str | None = None,
    repo: str | None = None,
) -> WiringConfig:
    """Load the board ``WiringConfig`` for a CLI command, project-aware (ingress-multiproject §8, #1).

    The read-and-act commands (``status``/``state``/``sessions``/``cancel``/``move``/``ticket``/
    ``pill``) need the SAME wiring the daemon uses, AND — on a multi-project root — must resolve WHICH
    board to act on. Resolution, in precedence order:

    1. **Explicit ``<root>/config.yml``** — the override path (a single project), unchanged: parsed
       via the daemon's YAML loader so there is exactly one config-reading path. A selector is moot
       here (the config.yml already names one project).
    2. **The registry** (no ``config.yml``) — :func:`~kanbanmate.daemon.registry_wiring.wiring_for_selection`
       resolves the entry via the SAME pure resolvers the daemon uses: N=1 → the sole entry (no
       selector needed — byte-identical to before); N>1 → the ``--project``/``--repo`` selector
       (FAIL LOUD listing the candidates when missing/ambiguous — never silently pick the wrong board).

    Args:
        root: The kanban runtime root holding ``config.yml`` / ``projects.json``.
        project: The ``--project`` Project v2 node id selector (N>1 multi-project roots), or ``None``.
        repo: The ``--repo`` ``owner/name`` selector (N>1 multi-project roots), or ``None``.

    Returns:
        The parsed :class:`~kanbanmate.app.wiring.WiringConfig` for the resolved project.

    Raises:
        ProjectSelectionError: When N>1 and the selector is missing / matches zero / matches >1.
    """
    config_path = root / daemon_loop.CONFIG_FILENAME
    if config_path.exists():
        # The config.yml override already names one project — the selector is moot (single-project).
        return daemon_loop._load_wiring_config(config_path)
    return wiring_for_selection(root, project=project, repo=repo)


def _resolve_wiring(root: Path, project: str | None, repo: str | None) -> WiringConfig:
    """Resolve the board wiring for a CLI command, failing LOUD + CLEAN on an ambiguous selection.

    Wraps :func:`_wiring_for` so a :class:`~kanbanmate.daemon.registry_wiring.ProjectSelectionError`
    (a multi-project root with no/ambiguous ``--project``/``--repo``) becomes a clean non-zero
    ``typer.Exit`` with the actionable candidate list — never a raw traceback, and never a silent
    wrong-board pick (#1). N=1 roots resolve flagless (the selector is unused).

    Args:
        root: The kanban runtime root.
        project: The ``--project`` selector, or ``None``.
        repo: The ``--repo`` selector, or ``None``.

    Returns:
        The resolved :class:`~kanbanmate.app.wiring.WiringConfig`.
    """
    try:
        return _wiring_for(root, project=project, repo=repo)
    except ProjectSelectionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


# Shared ``--project`` / ``--repo`` selectors for the board commands (ingress-multiproject §8, #1).
# Defined once so every board command declares the SAME option; both default ``None`` so an N=1 root
# is driven flagless (zero behaviour change) and a multi-project root selects the target board.
_PROJECT_OPTION = typer.Option(
    None,
    "--project",
    help="Project v2 node id to act on (REQUIRED on a multi-project root; ignored when N=1).",
)
_REPO_OPTION = typer.Option(
    None,
    "--repo",
    help="owner/name of the project to act on (alternative to --project on a multi-project root).",
)


@app.command()
def mcp(
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root (default ~/.kanban).",
    ),
    issue: int = typer.Option(
        ...,
        "--issue",
        help="The agent's pinned issue number (write tools refuse any other).",
    ),
    project: str = _PROJECT_OPTION,
    repo: str = _REPO_OPTION,
) -> None:
    """Start the stdio MCP board server, pinned to ``--issue`` (conduit / roadmap mcp).

    A thin stdio front-door exposing the board as MCP resources + tools to the agent's own
    ``claude`` session. Every WRITE tool is pinned to ``--issue`` (an agent may act ONLY on its own
    ticket, DESIGN §7) and PAUSE-guarded; there is NO ``merge`` tool. Read resources mirror
    ``kanban state``. The server runs over stdio and blocks until the client disconnects.

    Requires the ``[mcp]`` optional extra (``pip install 'kanbanmate[mcp]'``); the import is guarded
    so the bare ``kanban`` CLI works without it (mirrors how ``config serve`` guards the ``[ui]``
    import in ``cli/config.py``).

    Args:
        root: The runtime root holding ``config.yml`` / ``projects.json`` and the state markers.
        issue: The agent's pinned issue number (every write tool refuses any other).
        project: The ``--project`` node-id selector (multi-project roots; ignored when N=1).
        repo: The ``--repo`` selector (multi-project roots; alternative to ``--project``).
    """
    # Lazy + guarded import: the ``mcp`` SDK is the optional ``[mcp]`` extra, NOT a base dependency.
    # This guard keeps the bare ``kanban`` CLI importable without it (exactly as ``config serve``
    # guards the ``[ui]`` FastAPI import in ``cli/config.py:51``).
    try:
        from kanbanmate.mcp import server as mcp_server
    except ImportError as exc:
        typer.echo(
            f"Error: {exc}\n\n"
            "The MCP board server requires the [mcp] optional extra.\n"
            "Install it with: pip install 'kanbanmate[mcp]'",
            err=True,
        )
        raise typer.Exit(code=1) from exc
    # Fail LOUD + CLEAN on the start-up pin guard: a worktree pin file disagreeing with --issue is a
    # misconfiguration (every write would target the wrong ticket). A clean non-zero exit with the
    # actionable message, never a raw traceback (mirrors how ``serve`` handles its start-up guards).
    try:
        mcp_server.main(root=root.expanduser(), issue=issue, project=project, repo=repo)
    except mcp_server.PinMismatchError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def install(
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root to create (default ~/.kanban).",
    ),
    pm2: bool = typer.Option(
        True,
        "--pm2/--no-pm2",
        help="Drive PM2 (start/save/startup). Use --no-pm2 to only write the skeleton + ecosystem.",
    ),
    repo: Path = typer.Option(
        Path.cwd(),
        "--repo",
        help="Path to the KanbanMate repo for claude plugin marketplace add (default cwd).",
    ),
    kanban_command: str = typer.Option(
        "kanban",
        "--kanban-command",
        help="Console-script command PM2 runs (e.g. an ABSOLUTE pyenv path so PM2's boot "
        "environment need not have the pyenv shims on PATH). Default: the bare 'kanban'.",
    ),
    serve: bool = typer.Option(
        False,
        "--serve/--no-serve",
        help="Also install + start the `kanban-serve` webhook-receiver PM2 app alongside the "
        "daemon (ingress-multiproject §8). Use when ingress=webhook; front it with a TLS proxy.",
    ),
) -> None:
    """Install/upgrade the host + claude tiers: skeleton, PM2 daemon, and claude plugin (DESIGN §4).

    Idempotent: re-running ensures the root (mode 0o700), seeds the ``token`` skeleton (mode 0o600)
    without clobbering an existing one, writes ``ecosystem.config.js``, (re)registers the
    ``kanban`` PM2 app (plus the ``kanban-serve`` receiver app when ``--serve``), and adds the
    claude plugin marketplace + installs the ``/kanban`` skill. Refuses to run as root (DESIGN §10).

    Args:
        root: The kanban runtime root to create; defaults to ``~/.kanban``.
        pm2: When ``False`` (``--no-pm2``), skip the PM2 calls (still writes the ecosystem file).
        repo: Path to the KanbanMate repo (the plugin marketplace source); defaults to cwd.
        kanban_command: The console-script name baked into the ecosystem file so PM2 runs the
            right interpreter; defaults to the bare ``kanban``. Pass an absolute pyenv path
            (e.g. ``$(pyenv which kanban)``) when PM2's boot environment lacks the pyenv shims.
        serve: When ``True`` (``--serve``), also install + start the ``kanban-serve`` webhook
            receiver app (ingress=webhook deployments).
    """
    try:
        resolved = host_installer.host_install(
            root, run_pm2=pm2, kanban_command=kanban_command, serve=serve
        )
    except host_installer.RootPrivilegeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"kanban install: host tier ready at {resolved}")
    # Claude tier: register the plugin marketplace and install the /kanban skill (DESIGN §4.2).
    # A missing ``claude`` binary or a failed plugin install surfaces a clear actionable error
    # instead of a raw traceback or a false "registered" success (errors-2 / errors-7).
    try:
        host_installer.claude_install(repo)
    except (
        host_installer.ClaudeNotFoundError,
        host_installer.ClaudePluginInstallError,
    ) as exc:
        typer.echo(f"kanban install: claude tier failed — {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"kanban install: claude plugin registered from {repo}")


@app.command()
def uninstall(
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root to target (default ~/.kanban).",
    ),
    pm2: bool = typer.Option(
        True,
        "--pm2/--no-pm2",
        help="Drive PM2 (delete the kanban app). Use --no-pm2 to only perform host teardown.",
    ),
    repo: Path = typer.Option(
        Path.cwd(),
        "--repo",
        help="Path to the KanbanMate repo for claude plugin marketplace remove (default cwd).",
    ),
) -> None:
    """Remove the host + claude tiers: PM2 app, host teardown, and claude plugin (DESIGN §4).

    Idempotent: ``pm2 delete kanban`` tolerates a missing app, ``claude plugin uninstall`` tolerates
    a missing plugin; the ``token`` is left in place (it may hold a real PAT) — use ``kanban reset``
    to archive the whole root. Refuses root (DESIGN §10).

    Args:
        root: The kanban runtime root to target; defaults to ``~/.kanban``.
        pm2: When ``False`` (``--no-pm2``), skip the PM2 ``delete`` call (host teardown only).
        repo: Path to the KanbanMate repo (the marketplace source to remove); defaults to cwd.
    """
    try:
        resolved = host_installer.host_uninstall(root, run_pm2=pm2)
    except host_installer.RootPrivilegeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"kanban uninstall: host tier removed for {resolved}")
    # Claude tier: uninstall the plugin and remove the marketplace source (DESIGN §4.2).
    host_installer.claude_uninstall(repo)
    typer.echo("kanban uninstall: claude plugin removed")


@app.command()
def doctor() -> None:
    """Run the 3-tier health check: host, claude, and per-repo (DESIGN §4).

    Checks: engine importable, PM2 daemon up, daemon heartbeat fresh, claude
    plugin present, GitHub token scoped to {project, repo}, branch protection
    on, non-root user, and tmux socket owned by the current user. Exits 0 when
    all pass, 1 when any fail.

    The branch-protection check is wired LIVE from the registry: the resolved
    checker probes the first registered repo's ``main`` branch via the GitHub
    adapter (advisory only — it WARNs when protection is off but never fails the
    run). When no repo is registered the resolver returns ``None`` and the check
    keeps its advisory skip.
    """
    code = doctor_mod.run_doctor(
        root=_DEFAULT_ROOT,
        branch_check=doctor_mod._resolve_branch_check(_DEFAULT_ROOT),
    )
    raise typer.Exit(code=code)


@app.command()
def init(
    repo: str = typer.Option(
        ...,
        "--repo",
        help="Target repository as 'owner/name'.",
    ),
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root holding projects.json (default ~/.kanban).",
    ),
    clone: Path = typer.Option(
        Path.cwd(),
        "--clone",
        help="Local clone path for .claude/kanban/columns.yml (default cwd).",
    ),
    title: str = typer.Option(
        "",
        "--title",
        help="Project v2 title to find-or-create (default: the repo name).",
    ),
    dev_repo_path: str = typer.Option(
        "",
        "--dev-repo-path",
        help="Operator's dev-clone path (post-merge ff-only update target, DESIGN §10). "
        "Configured ONCE here; the daemon's post-merge update then resolves it from "
        "projects.json instead of demanding it on every kanban-update-main call.",
    ),
    ingress: str = typer.Option(
        "polling",
        "--ingress",
        help="Per-project ingress mode: 'polling' (default — tight 10 s cadence, right for a native "
        "ONE-WAY board whose input is local) or 'webhook' (fast nudge + slow safety-sweep fallback; "
        "seeds <root>/webhook_secret — for a github-backed board).",
    ),
) -> None:
    """Initialise the per-repo tier: project, columns, labels, config, registry (DESIGN §4.3).

    Creates a fresh GitHub Project v2, reuses its auto Status field to materialise the columns
    from the bundled ``columns.yml`` template, ensures the ``wave:*``/``prio:*`` labels, bootstraps
    the local clone (``ensure_clone`` — git init in place + credential helper), copies the
    template into ``<clone>/.claude/kanban/columns.yml``, and registers the project in
    ``projects.json``. No webhook/n8n step (DESIGN §4.3). Idempotent.

    Args:
        repo: The target repository as ``owner/name``.
        root: The kanban runtime root holding ``projects.json``.
        clone: The local clone path the per-repo ``columns.yml`` is written into.
        title: The Project v2 title to find-or-create (defaults to the repo name).
        dev_repo_path: The operator's dev-clone path persisted on the registry entry (the
            post-merge ff-only update target, DESIGN §10); defaults to ``""`` (disabled).
        ingress: The per-project ingress mode (``polling`` default | ``webhook``); recorded on the
            registry entry and (for ``webhook``) seeds the ``<root>/webhook_secret`` skeleton.
    """
    entry = init_cmd.init(
        repo,
        root=root,
        clone=clone,
        project_title=title or None,
        dev_repo_path=dev_repo_path,
        ingress=ingress,
    )
    typer.echo(
        f"kanban init: project {entry.project_id} ready for {entry.repo} (ingress={ingress})"
    )


@app.command()
def seed(
    roadmap: Path = typer.Argument(
        ...,
        help="Path to the ROADMAP.md to seed issues from.",
    ),
    repo: str = typer.Option(
        ...,
        "--repo",
        help="Target repository as 'owner/name'.",
    ),
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="Project v2 node id to add the seeded issues to. Optional: when omitted, "
        "it is auto-resolved from projects.json by --repo (the kanban init handoff). "
        "Pass it explicitly to override the registry.",
    ),
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root holding projects.json (default ~/.kanban). Only "
        "consulted when --project-id is omitted (registry auto-resolve).",
    ),
) -> None:
    """Seed the board from a roadmap: issues + project items + ``Depends on`` rewrite (DESIGN §4.3).

    Parses the roadmap, creates issues in dependency order, rewrites ``Depends on RPx`` references
    to the real ``#N`` issue numbers, and adds each issue to the project (it lands in Backlog). The
    project node id comes from ``--project-id`` when given, else is resolved from ``projects.json``
    by ``--repo`` (run ``kanban init`` first if the repo is unregistered) — the PoC init→seed handoff.

    Args:
        roadmap: The path to the ``ROADMAP.md`` to seed from.
        repo: The target repository as ``owner/name``.
        project_id: The Project v2 node id (from ``kanban init``) to add issues to;
            optional, auto-resolved from the registry by ``repo`` when omitted.
        root: The kanban runtime root holding ``projects.json`` (registry resolve).
    """
    try:
        created = seed_cmd.seed(roadmap, repo=repo, project_id=project_id, root=root)
    except ValueError as exc:
        # An unregistered repo (registry resolve miss) fails clean with the
        # "run kanban init first" message (#12 PoC parity), exit 1 — not a traceback.
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"kanban seed: created {len(created)} issue(s) for {repo}")


@app.command()
def status(
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root holding config.yml + state (default ~/.kanban).",
    ),
    project: str = _PROJECT_OPTION,
    repo: str = _REPO_OPTION,
) -> None:
    """Show the single-pane board summary + operator signals (DESIGN §3.3 / §5 / §10, 31.1).

    Read-only — crosses a fresh board snapshot with the persisted running state AND the runtime
    root's operator signals (the ``PAUSE`` kill-switch banner, the ``DEGRADED`` auth breadcrumb,
    the ``daemon.heartbeat`` last-tick health, the launch queue with ages, and a concrete
    ``tmux attach`` hint per agent), then prints a single pane. Nothing is moved or commented.

    Args:
        root: The kanban runtime root holding ``config.yml``, the state store, and the markers.
        project: The ``--project`` node-id selector (multi-project roots; ignored when N=1).
        repo: The ``--repo`` selector (multi-project roots; alternative to ``--project``).
    """
    deps = build_deps(_resolve_wiring(root, project, repo))
    typer.echo(
        status_cmd.status(
            deps.board_reader,
            deps.store,
            root=root.expanduser(),
            ttl=doctor_mod.HEARTBEAT_TTL_FLOOR,
        )
    )


@app.command()
def state(
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root holding config.yml + state (default ~/.kanban).",
    ),
    json_out: bool = typer.Option(
        False,
        "--json",
        help="Emit a machine-readable JSON shape (for agents/scripts) instead of the human pane.",
    ),
    project: str = _PROJECT_OPTION,
    repo: str = _REPO_OPTION,
) -> None:
    """Show the unified read-only board + agents + queue + recent-events + health-pill view (cockpit PR1).

    Read-only — extends ``status`` with the recent-events ring and the current health pill (the
    daemon's last-computed enum, read off the ``status/last_status`` marker). ``--json`` emits a
    stable machine shape for agents/scripts. Nothing is moved, posted, or written.

    Args:
        root: The kanban runtime root holding ``config.yml``, the state store, and the markers.
        json_out: When set, emit JSON instead of the human operator pane.
        project: The ``--project`` node-id selector (multi-project roots; ignored when N=1).
        repo: The ``--repo`` selector (multi-project roots; alternative to ``--project``).
    """
    deps = build_deps(_resolve_wiring(root, project, repo))
    typer.echo(
        state_cmd.state(
            deps.board_reader,
            deps.store,
            root=root.expanduser(),
            ttl=doctor_mod.HEARTBEAT_TTL_FLOOR,
            as_json=json_out,
        )
    )


@app.command()
def pause(
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root holding the PAUSE sentinel (default ~/.kanban).",
    ),
) -> None:
    """Engage the kill-switch: create the ``PAUSE`` sentinel so no agent launches (DESIGN §10).

    Idempotent — re-pausing an already-paused root is a clean no-op. The daemon reads the sentinel
    fresh every tick, so the pause takes effect on the next poll without a restart. Echoes the
    resulting state.

    Args:
        root: The kanban runtime root the ``PAUSE`` sentinel is created under.
    """
    typer.echo(status_cmd.render_pause(status_cmd.pause(root.expanduser())))


@app.command()
def resume(
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root holding the PAUSE sentinel (default ~/.kanban).",
    ),
) -> None:
    """Release the kill-switch: remove the ``PAUSE`` sentinel so launches resume (DESIGN §10).

    Idempotent — resuming a root that is not paused is a clean no-op. The daemon picks the change
    up on its next tick. Echoes the resulting state.

    Args:
        root: The kanban runtime root the ``PAUSE`` sentinel is removed from.
    """
    typer.echo(status_cmd.render_resume(status_cmd.resume(root.expanduser())))


@app.command()
def sessions(
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root holding config.yml + state (default ~/.kanban).",
    ),
    project: str = _PROJECT_OPTION,
    repo: str = _REPO_OPTION,
) -> None:
    """List the live agent sessions, flagging reaper candidates (DESIGN §3.3 / §8.3).

    Read-only — crosses the persisted running state with the live tmux sessions; a ``running``
    ticket whose session is gone is shown as DEAD (a reaper candidate).

    Args:
        root: The kanban runtime root holding ``config.yml`` and the state store.
        project: The ``--project`` node-id selector (multi-project roots; ignored when N=1).
        repo: The ``--repo`` selector (multi-project roots; alternative to ``--project``).
    """
    deps = build_deps(_resolve_wiring(root, project, repo))
    typer.echo(sessions_cmd.sessions(deps.store, deps.sessions))


@app.command()
def cancel(
    issue: int = typer.Argument(
        ...,
        help="The GitHub issue number whose agent to tear down.",
    ),
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root holding config.yml + state (default ~/.kanban).",
    ),
    project: str = _PROJECT_OPTION,
    repo: str = _REPO_OPTION,
) -> None:
    """Manually tear down a ticket's agent via the app-layer ``TeardownAction`` (DESIGN §8.2).

    Reuses the exact :class:`~kanbanmate.app.actions.TeardownAction` the daemon runs on a Cancel-
    column move: kill the tmux session, remove the worktree, release the slot, post a recap comment.

    Args:
        issue: The GitHub issue number whose agent to tear down.
        root: The kanban runtime root holding ``config.yml`` and the state store.
        project: The ``--project`` node-id selector (multi-project roots; ignored when N=1).
        repo: The ``--repo`` selector (multi-project roots; alternative to ``--project``).
    """
    cancel_cmd.cancel(issue, deps=build_deps(_resolve_wiring(root, project, repo)))
    typer.echo(f"kanban cancel: torn down agent for #{issue}")


@app.command()
def move(
    issue: int = typer.Argument(..., help="The GitHub issue number whose card to move."),
    column: str = typer.Argument(..., help="Destination column KEY (as shown by `kanban state`)."),
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root holding config.yml + state (default ~/.kanban).",
    ),
    wait: bool = typer.Option(
        False,
        "--wait",
        help="Block on the daemon's result (done/rejected) up to a timeout instead of returning now.",
    ),
    project: str = _PROJECT_OPTION,
    repo: str = _REPO_OPTION,
) -> None:
    """Enqueue an operator move of #issue's card to <column> — executed by the daemon (cockpit PR2).

    Writes a move intent into the ``~/.kanban/intents/`` queue; the daemon (the sole board writer)
    applies it on its next tick (re-validating + advancing the diff baseline so the move never
    re-fires a launch). ``--wait`` blocks on the result. ``<column>`` is a column KEY.

    Args:
        issue: The GitHub issue number whose card to move.
        column: The destination column KEY.
        root: The kanban runtime root holding the intent queue.
        wait: When set, block on the daemon's result up to a timeout.
        project: The ``--project`` node-id selector (multi-project roots; ignored when N=1).
        repo: The ``--repo`` selector (multi-project roots; alternative to ``--project``).
    """
    deps = build_deps(_resolve_wiring(root, project, repo))
    typer.echo(move_cmd.move(deps.store, issue=issue, to_col=column, wait=wait))


@app.command()
def logs(
    issue: int = typer.Argument(
        None,
        help="Optional issue number to filter the structured log by.",
    ),
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root holding the log directory (default ~/.kanban).",
    ),
    tail: int = typer.Option(
        logs_cmd.DEFAULT_TAIL,
        "--tail",
        help="How many trailing log entries to show.",
    ),
) -> None:
    """Read the structured JSONL daemon log, optionally filtered by issue (DESIGN §5).

    Args:
        issue: When given, keep only entries for that issue and surface its per-ticket log path.
        root: The kanban runtime root holding the ``log`` directory.
        tail: The maximum number of trailing entries to show.
    """
    typer.echo(logs_cmd.logs(root, issue=issue, tail=tail))


@app.command()
def reset(
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root to archive aside (default ~/.kanban).",
    ),
) -> None:
    """Archive the kanban root aside so the operator starts clean (DESIGN §11).

    Non-destructive: renames ``~/.kanban`` to a timestamped ``~/.kanban.bak-<...>`` backup (a real
    token is preserved). A subsequent ``kanban install`` re-creates a pristine root.

    Args:
        root: The kanban runtime root to archive aside.
    """
    typer.echo(reset_cmd.render_reset(reset_cmd.reset(root)))


@app.command()
def poll(
    once: bool = typer.Option(
        False,
        "--once",
        help="Run a single reconciliation tick and exit (no daemon).",
    ),
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root holding config.yml (default ~/.kanban).",
    ),
) -> None:
    """Run the poll loop, or a single tick with ``--once`` (DESIGN §3.1 / §5).

    The continuous form is equivalent to :func:`run`; ``--once`` runs exactly one
    :func:`~kanbanmate.app.wiring.run_one_tick` and exits — a debugging dry run, no daemon, no lock.

    Args:
        once: When ``True``, run exactly one tick and exit instead of looping.
        root: The kanban runtime root holding ``config.yml``.
    """
    if once:
        result = poll_cmd.poll_once(root=root)
        typer.echo(poll_cmd.render_poll(result))
        return
    daemon_loop.main()


@ticket_app.command("create")
def ticket_create(
    title: str = typer.Option(..., "--title", help="The new issue title."),
    body: str = typer.Option("", "--body", help="The issue body."),
    label: list[str] = typer.Option(None, "--label", help="Label to apply (repeatable)."),
    column: str = typer.Option(
        None, "--column", help="Optional initial column KEY (must be non-triggering)."
    ),
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root holding config.yml + state (default ~/.kanban).",
    ),
    wait: bool = typer.Option(
        False, "--wait", help="Block on the daemon's result up to a timeout."
    ),
    project: str = _PROJECT_OPTION,
    repo: str = _REPO_OPTION,
) -> None:
    """Enqueue an operator ticket-create — executed by the daemon (cockpit PR3).

    Writes a ``ticket_create`` intent (create issue + add to the project + optional initial move) the
    daemon applies idempotently. ``--wait`` blocks on the result.

    Args:
        title: The new issue title.
        body: The issue body.
        label: Labels to apply (repeatable ``--label``).
        column: Optional initial column KEY (refused if it is a launch column).
        root: The kanban runtime root holding the intent queue.
        wait: When set, block on the daemon's result.
        project: The ``--project`` node-id selector (multi-project roots; ignored when N=1).
        repo: The ``--repo`` selector (multi-project roots; alternative to ``--project``).
    """
    deps = build_deps(_resolve_wiring(root, project, repo))
    typer.echo(
        ticket_cmd.create(
            deps.store,
            title=title,
            body=body,
            labels=label or [],
            column=column or None,
            wait=wait,
        )
    )


@ticket_app.command("edit")
def ticket_edit(
    issue: int = typer.Argument(..., help="The issue number whose body to replace."),
    body: str = typer.Option(..., "--body", help="The new issue body (markdown)."),
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root holding config.yml + state (default ~/.kanban).",
    ),
    wait: bool = typer.Option(
        False, "--wait", help="Block on the daemon's result up to a timeout."
    ),
    project: str = _PROJECT_OPTION,
    repo: str = _REPO_OPTION,
) -> None:
    """Enqueue an operator ticket-edit (replace the issue body) — executed by the daemon (cockpit PR3).

    Args:
        issue: The issue number whose body to replace.
        body: The new issue body.
        root: The kanban runtime root holding the intent queue.
        wait: When set, block on the daemon's result.
        project: The ``--project`` node-id selector (multi-project roots; ignored when N=1).
        repo: The ``--repo`` selector (multi-project roots; alternative to ``--project``).
    """
    deps = build_deps(_resolve_wiring(root, project, repo))
    typer.echo(ticket_cmd.edit(deps.store, issue=issue, body=body, wait=wait))


@ticket_app.command("close")
def ticket_close(
    issue: int = typer.Argument(..., help="The issue number to close."),
    root: Path = typer.Option(
        _DEFAULT_ROOT,
        "--root",
        help="Kanban runtime root holding config.yml + state (default ~/.kanban).",
    ),
    wait: bool = typer.Option(
        False, "--wait", help="Block on the daemon's result up to a timeout."
    ),
    project: str = _PROJECT_OPTION,
    repo: str = _REPO_OPTION,
) -> None:
    """Enqueue an operator ticket-close — executed by the daemon (cockpit PR3).

    Args:
        issue: The issue number to close.
        root: The kanban runtime root holding the intent queue.
        wait: When set, block on the daemon's result.
        project: The ``--project`` node-id selector (multi-project roots; ignored when N=1).
        repo: The ``--repo`` selector (multi-project roots; alternative to ``--project``).
    """
    deps = build_deps(_resolve_wiring(root, project, repo))
    typer.echo(ticket_cmd.close(deps.store, issue=issue, wait=wait))


@pill_app.command("set-health")
def pill_set_health(
    enum: str = typer.Argument(..., help="Health: INACTIVE|BLOCKED|WAITING|ACTIVE|COMPLETE."),
    note: str = typer.Option("", "--note", help="Optional operator note shown on the dashboard."),
    root: Path = typer.Option(
        _DEFAULT_ROOT, "--root", help="Kanban runtime root (default ~/.kanban)."
    ),
    wait: bool = typer.Option(
        False, "--wait", help="Block on the daemon's result up to a timeout."
    ),
    project: str = _PROJECT_OPTION,
    repo: str = _REPO_OPTION,
) -> None:
    """Force the rolling status pill to <enum> until cleared — applied by the daemon (cockpit PR3).

    Args:
        enum: The health enum to pin.
        note: Optional operator note rendered on the dashboard.
        root: The kanban runtime root holding the intent queue.
        wait: When set, block on the daemon's result.
        project: The ``--project`` node-id selector (multi-project roots; ignored when N=1).
        repo: The ``--repo`` selector (multi-project roots; alternative to ``--project``).
    """
    deps = build_deps(_resolve_wiring(root, project, repo))
    typer.echo(pill_cmd.set_health(deps.store, enum=enum, note=note or None, wait=wait))


@pill_app.command("note")
def pill_note(
    text: str = typer.Argument(..., help="The operator note to show on the dashboard."),
    root: Path = typer.Option(
        _DEFAULT_ROOT, "--root", help="Kanban runtime root (default ~/.kanban)."
    ),
    wait: bool = typer.Option(
        False, "--wait", help="Block on the daemon's result up to a timeout."
    ),
    project: str = _PROJECT_OPTION,
    repo: str = _REPO_OPTION,
) -> None:
    """Set the operator dashboard note — applied by the daemon (cockpit PR3).

    Args:
        text: The operator note to display.
        root: The kanban runtime root holding the intent queue.
        wait: When set, block on the daemon's result.
        project: The ``--project`` node-id selector (multi-project roots; ignored when N=1).
        repo: The ``--repo`` selector (multi-project roots; alternative to ``--project``).
    """
    deps = build_deps(_resolve_wiring(root, project, repo))
    typer.echo(pill_cmd.note(deps.store, text=text, wait=wait))


@pill_app.command("clear")
def pill_clear(
    root: Path = typer.Option(
        _DEFAULT_ROOT, "--root", help="Kanban runtime root (default ~/.kanban)."
    ),
    wait: bool = typer.Option(
        False, "--wait", help="Block on the daemon's result up to a timeout."
    ),
    project: str = _PROJECT_OPTION,
    repo: str = _REPO_OPTION,
) -> None:
    """Clear the operator pill override + note (revert to the computed health) — cockpit PR3.

    Args:
        root: The kanban runtime root holding the intent queue.
        wait: When set, block on the daemon's result.
        project: The ``--project`` node-id selector (multi-project roots; ignored when N=1).
        repo: The ``--repo`` selector (multi-project roots; alternative to ``--project``).
    """
    deps = build_deps(_resolve_wiring(root, project, repo))
    typer.echo(pill_cmd.clear(deps.store, wait=wait))


def main() -> None:
    """Console-script entry point for ``kanban`` — invoke the Typer application.

    Named by ``pyproject``'s ``kanban = "kanbanmate.cli.app:main"``; calling the Typer ``app``
    parses ``sys.argv`` and dispatches to the matching command.
    """
    app()
