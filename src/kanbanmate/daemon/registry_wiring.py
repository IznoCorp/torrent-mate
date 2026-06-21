"""Registry → :class:`WiringConfig` resolution shared by the daemon sweep + the CLI (§3.1 / §8, #1).

Split out of ``daemon/loop.py`` for two reasons: it keeps ``loop.py`` under the 1000-LOC hard
ceiling, and it gives the project-AWARE CLI resolution a clean home. The single entry→wiring builder
(:func:`wiring_for_entry`) is reused by the daemon's plural ``_wirings_from_registry`` AND by the
CLI's :func:`wiring_for_selection` so a project's wiring is constructed identically everywhere (one
source of truth). The CLI selection logic resolves WHICH board a command acts on through the SAME
pure resolvers the daemon + webhook receiver use (``core/registry_resolve``) — no second resolver.

Layering: ``daemon`` is a top entrypoint (DESIGN §3.2) — it may import ``app`` / ``core`` freely and
the ``cli.init`` registry loader (as ``daemon/loop`` already does). It does NOT import a sibling
entrypoint at module scope.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from kanbanmate.app.wiring import WiringConfig

# The daemon's YAML config + PAUSE sentinel filenames under the kanban root. They live HERE (the
# resolution module) and are re-exported by ``daemon/loop`` for back-compat (many modules import
# ``daemon.loop.CONFIG_FILENAME`` / ``PAUSE_FILENAME``). One definition, no drift.
CONFIG_FILENAME = "config.yml"
PAUSE_FILENAME = "PAUSE"


class ProjectSelectionError(RuntimeError):
    """Raised when a CLI command cannot resolve WHICH project to act on (ingress-multiproject §8, #1).

    Two cases: a MULTI-project root with no ``--project``/``--repo`` selector (ambiguous — never
    silently pick the wrong board), or a selector that matches zero / >1 entries. The message names
    the available projects so the operator re-runs with the right selector. The CLI catches this and
    exits non-zero with the message (a clean fail-loud, never a wrong-board silent pick).
    """


def wiring_for_entry(
    root: Path,
    entry: object,
    *,
    multi: bool,
    kill_switch: bool,
) -> WiringConfig:
    """Build ONE :class:`WiringConfig` from a registry entry (shared by the sweep + CLI, §3.1 / §8).

    The SINGLE entry→wiring construction path so the daemon sweep
    (:func:`~kanbanmate.daemon.loop._wirings_from_registry`) and the CLI read-and-act commands
    (:func:`wiring_for_selection`) build a project's wiring the SAME way. ``multi`` drives the store
    layout: N=1 → ``state_root=""`` (the legacy flat layout) + ``multi_project=False`` (byte-identical
    to the deployed single-project daemon); N>1 → the per-project store sub-root
    (``<root>/projects/<safe(pid)>``) + ``multi_project=True``.

    Args:
        root: The runtime root holding the token(s) + the per-project store sub-roots.
        entry: The registry entry (a :class:`~kanbanmate.cli.init.ProjectEntry`; typed ``object`` to
            avoid an eager cli import at module scope — its attributes are read below).
        multi: Whether the daemon drives >1 enabled project (the multi-project store layout switch).
        kill_switch: Whether the PAUSE sentinel is present (threaded onto the wiring).

    Returns:
        The :class:`WiringConfig` for ``entry``.
    """
    from kanbanmate.adapters.github.token import load_entry_token
    from kanbanmate.cli.init import CLONE_COLUMNS_RELPATH, CLONE_TRANSITIONS_RELPATH
    from kanbanmate.core.registry_resolve import safe_project_id

    columns_yaml = (Path(entry.clone) / CLONE_COLUMNS_RELPATH).read_text(encoding="utf-8")  # type: ignore[attr-defined]
    transitions_path = Path(entry.clone) / CLONE_TRANSITIONS_RELPATH  # type: ignore[attr-defined]
    transitions_yaml: str | None = (
        transitions_path.read_text(encoding="utf-8") if transitions_path.exists() else None
    )
    # Multi-org token model (§6): ``token_ref==""`` → the shared <root>/token (today's path, zero
    # behaviour change); a non-empty ref → <root>/tokens/<ref> so org A and org B can use distinct
    # PATs without a GitHub App. Routed through the SHARED resolver (#4) so the daemon and the agent
    # helpers resolve the per-entry token identically.
    token = load_entry_token(root, entry.token_ref)  # type: ignore[attr-defined]
    # Per-project store sub-root for N>1 (§3.2); empty for N=1 → the legacy flat layout.
    state_root = str(root / "projects" / safe_project_id(entry.project_id)) if multi else ""  # type: ignore[attr-defined]
    return WiringConfig(
        token=token,
        project_id=entry.project_id,  # type: ignore[attr-defined]
        repo=entry.repo,  # type: ignore[attr-defined]
        clone_dir=entry.clone,  # type: ignore[attr-defined]
        columns_yaml=columns_yaml,
        kanban_root=str(root),
        kill_switch=kill_switch,
        transitions_yaml=transitions_yaml,
        config_dir=entry.config_dir,  # type: ignore[attr-defined]
        state_root=state_root,
        multi_project=multi,
        ingress=entry.ingress or "webhook",  # type: ignore[attr-defined]
        board_backend=getattr(entry, "board_backend", "github"),  # anchor §9
        board_mirror=bool(getattr(entry, "board_mirror", True)),  # anchor §5 — honour the switch
    )


def wiring_for_selection(
    root: Path,
    *,
    project: str | None = None,
    repo: str | None = None,
) -> WiringConfig:
    """Resolve the ONE project a CLI command acts on, project-aware (ingress-multiproject §8, #1).

    The fix for the half-shipped multi-project CLI: every operator read-and-act command
    (``status``/``state``/``sessions``/``cancel``/``move``/``ticket``/``pill``) resolves WHICH board
    to act on through this single function, reusing the SAME pure resolvers the daemon + webhook
    receiver use (:func:`~kanbanmate.core.registry_resolve.resolve_by_project_id` /
    :func:`~kanbanmate.core.registry_resolve.resolve_by_repo`) — no second resolver. Resolution:

    * **N=1** (one enabled project) — the sole entry, NO selector needed (zero behaviour change for
      the deployed single-project roots; the flat store layout via ``multi=False``).
    * **N>1 + ``project`` (a project node id)** — exact lookup.
    * **N>1 + ``repo`` only** — resolve by repo; the sole match wins, an ambiguous repo (>1 board) →
      fail loud (the operator passes ``--project``).
    * **N>1 + NO selector** — FAIL LOUD with the candidate list (never silently pick the wrong board).

    Args:
        root: The runtime root holding ``projects.json`` + the token(s).
        project: The Project v2 node id selector (``--project``), or ``None``.
        repo: The ``owner/name`` repo selector (``--repo``), or ``None``.

    Returns:
        The :class:`WiringConfig` for the resolved project (flat layout for N=1, the per-project
        sub-root for N>1 — so a CLI read targets the SAME store the daemon writes).

    Raises:
        FileNotFoundError: When no project is registered, or all registered projects are disabled.
        ProjectSelectionError: When N>1 and the selector is missing / matches zero / matches >1.
    """
    from kanbanmate.cli.init import _load_registry, _projects_path
    from kanbanmate.core.registry_resolve import (
        enabled_entries,
        resolve_by_project_id,
        resolve_by_repo,
    )

    projects_path = _projects_path(root)
    registry = _load_registry(projects_path) if projects_path.exists() else {}
    if not registry:
        raise FileNotFoundError(
            f"no {root / CONFIG_FILENAME} and no project registered in {projects_path} — "
            "run `kanban init --repo owner/name` first"
        )
    enabled = enabled_entries(registry)
    if not enabled:
        raise FileNotFoundError(
            f"no ENABLED project in {projects_path} — every registered project has enabled=false"
        )
    multi = len(enabled) > 1
    enabled_by_pid = {e.project_id: e for e in enabled}

    if not multi:
        # N=1 fast-path: the sole enabled entry, no selector required (back-compat — a deployed
        # single-project root keeps the FLAT store layout, byte-identical to before).
        entry: object = enabled[0]
    else:
        entry = _select_entry(
            list(enabled),
            enabled_by_pid,
            project,
            repo,
            resolve_by_project_id,
            resolve_by_repo,
            projects_path,
        )

    kill_switch = (root / PAUSE_FILENAME).exists()
    return wiring_for_entry(root, entry, multi=multi, kill_switch=kill_switch)


def _select_entry(
    enabled: list[object],
    enabled_by_pid: Mapping[str, object],
    project: str | None,
    repo: str | None,
    resolve_by_project_id: Callable[..., object],
    resolve_by_repo: Callable[..., list[object]],
    projects_path: Path,
) -> object:
    """Pick the ONE enabled entry a selector names, else FAIL LOUD (the N>1 branch of selection).

    Split out of :func:`wiring_for_selection` to keep both small + readable. ``project`` (a node id)
    is the precise selector; ``repo`` resolves by slug (its sole match wins). No selector, or a
    selector that matches zero / >1, raises :class:`ProjectSelectionError` naming the candidates.

    Args:
        enabled: The enabled entries (for the candidate list on failure).
        enabled_by_pid: ``{project_id: entry}`` of the enabled entries (the resolver input).
        project: The ``--project`` node-id selector, or ``None``.
        repo: The ``--repo`` slug selector, or ``None``.
        resolve_by_project_id: The pure by-id resolver (injected — the core helper).
        resolve_by_repo: The pure by-repo resolver (injected — the core helper).
        projects_path: The registry path (named in the error for the operator).

    Returns:
        The single resolved entry.

    Raises:
        ProjectSelectionError: When the selector is missing / matches zero / matches >1.
    """
    candidates = sorted(f"{e.project_id} ({e.repo})" for e in enabled)  # type: ignore[attr-defined]
    if project is not None:
        entry = resolve_by_project_id(enabled_by_pid, project)
        if entry is None:
            raise ProjectSelectionError(
                f"--project {project!r} matches no enabled project in {projects_path}. "
                f"Available: {candidates}"
            )
        return entry
    if repo is not None:
        matches = resolve_by_repo(enabled_by_pid, repo)
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ProjectSelectionError(
                f"--repo {repo!r} matches no enabled project in {projects_path}. "
                f"Available: {candidates}"
            )
        raise ProjectSelectionError(
            f"--repo {repo!r} backs {len(matches)} boards in {projects_path} — pass --project "
            f"<project_id> to disambiguate. Available: {candidates}"
        )
    raise ProjectSelectionError(
        f"{len(enabled)} projects registered in {projects_path} and no selector given. "
        f"Pass --project <project_id> (or --repo <owner/name>). Available: {candidates}"
    )


__all__ = [
    "CONFIG_FILENAME",
    "PAUSE_FILENAME",
    "ProjectSelectionError",
    "wiring_for_entry",
    "wiring_for_selection",
]
