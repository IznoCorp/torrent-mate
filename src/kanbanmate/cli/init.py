"""Per-repo tier of the installer: ``kanban init`` (DESIGN §4.3).

``kanban init --repo org/repo`` bootstraps one target project so the polling
daemon can drive it:

1. **Project** — find-or-create a fresh org Project v2 (reusing one of the same
   title if present); a transferred repo does *not* migrate a personal Project,
   so ``init`` always materialises a clean org board. A default one-line short
   description is set on the board when it has none (idempotent — phase-33).
2. **Columns** — reuse the auto-created Status single-select field and make its
   option set exactly the columns from the per-repo ``columns.yml`` template, in
   board order, preserving existing option ids (cards are never orphaned).
3. **Labels** — ensure the ``wave:*`` / ``prio:*`` routing labels exist on the
   repo (the seed step applies them).
4. **Config** — copy the ``columns.yml`` template into the clone at
   ``<clone>/.claude/kanban/columns.yml`` so the daemon reads the board's column
   model from the project's own working tree.
5. **Registry** — register the project in ``<root>/projects.json``, keyed by the
   Project v2 node id (what the daemon routes by).

There is **no webhook / n8n step** — polling is the sole ingress (DESIGN §4.3).
Every step is idempotent where GitHub allows it, so a re-run converges rather
than duplicating.

Layering: ``cli`` is an entrypoint at the top of the import hierarchy (DESIGN
§3.2); it composes the concrete GitHub :class:`~kanbanmate.adapters.github.client.GithubClient`
(a :class:`~kanbanmate.ports.board.Seeder`) and writes runtime state under the
kanban root. The ``Seeder`` is injectable so tests drive a fake and never touch
the network.
"""

from __future__ import annotations

import importlib.resources
import json
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from kanbanmate.adapters.github.client import GithubClient
from kanbanmate.adapters.github.token import load_token
from kanbanmate.adapters.workspace.worktree import GitWorktreeWorkspace
from kanbanmate.core.columns import load_columns
from kanbanmate.core.transitions_defaults import render_transitions_yaml
from kanbanmate.ports.board import Seeder

logger = logging.getLogger(__name__)

# The package and resource locating the bundled ``columns.yml`` template. Loaded
# via ``importlib.resources`` so it resolves from installed package data (a wheel
# or ``pip install -e .``), not a computed repo-root path (DESIGN §9).
_ASSET_PACKAGE = "kanbanmate.assets"
_COLUMNS_TEMPLATE_RESOURCE = "columns.yml.tmpl"

# The default kanban runtime root (DESIGN §4.1 / §5). Configurable via the
# ``root`` parameter so tests pass a ``tmp_path`` and never touch the real home.
DEFAULT_KANBAN_ROOT = Path("~/.kanban/").expanduser()

# The integration base branch ``ensure_clone`` fetches at init time (phase 14).
# Matches the daemon's worktree base default; the clone fetches ``origin/main`` so
# the first agent launch finds the integration base already present.
DEFAULT_INIT_BASE = "main"

# The projects registry filename under the kanban root (DESIGN §4.3 — keyed by
# the Project v2 node id, which the daemon routes by).
PROJECTS_FILENAME = "projects.json"

# The default project short-description ``init`` sets on a fresh board (phase-33).
# Idempotent: the seeder only writes it when the project has no description yet,
# so an operator-authored one is never overwritten. ``{repo}`` is the slug.
DEFAULT_PROJECT_DESCRIPTION = (
    "Kanban orchestrated by KanbanMate — autonomous Claude agents launched per transition ({repo})"
)

# Where the per-repo column model is written inside the clone (DESIGN §4.3). The
# daemon watches ``config.yml``'s ``mtime`` and reloads the whole config (including
# the referenced ``columns.yml``) on change; it does NOT watch this file directly.
CLONE_COLUMNS_RELPATH = Path(".claude") / "kanban" / "columns.yml"
# Where the per-repo transition whitelist is rendered inside the clone (DESIGN §9,
# phase 12.7). Unlike columns.yml (a static .tmpl asset), transitions.yml is
# RENDERED — it carries the project slug — so the renderer in
# core/transitions_defaults is the source of truth.
CLONE_TRANSITIONS_RELPATH = Path(".claude") / "kanban" / "transitions.yml"


@dataclass(frozen=True)
class ProjectEntry:
    """One project's GitHub binding, keyed in the registry by its project node id.

    A lean, fresh-genesis shape (no webhook fields — polling is the sole
    ingress, DESIGN §4.3). The daemon resolves the board, the Status field, and
    the option map from this entry.

    Attributes:
        repo: The ``owner/name`` slug (clone resolution, comments, protection).
        clone: Absolute path to the local clone (base of the ticket worktrees).
        project_id: The Project v2 node id (same as the registry key).
        status_field_node_id: The Status single-select field node id.
        option_map: ``{column_name: option_id}`` for the Status field.
        config_dir: The project's ``.claude`` directory — the source of
            ``skills``/``commands``/``agents`` the launcher's
            :func:`~kanbanmate.adapters.perms.provision_worktree_skills` COPIES
            into each worktree so a launched agent can resolve the ``/implement:*``
            skills its column prompt invokes (they live in the gitignored config
            repo, absent from the clone checkout). Defaults to ``""`` (provisioning
            disabled); ``init`` defaults it to ``<clone>/.claude`` when not
            overridden. Port of PoC ``cli/registry.py:29-39``.
        dev_repo_path: The operator's dev-clone path — the post-merge ff-only
            update target (DESIGN §10). Configured once at init; the daemon's
            post-merge ``kanban-update-main`` path resolves it from the registry
            instead of demanding it on every call. Defaults to ``""`` (no dev-clone
            update). Port of PoC ``cli/registry.py:40``.
    """

    repo: str
    clone: str
    project_id: str
    status_field_node_id: str
    option_map: dict[str, str] = field(default_factory=dict)
    # Both fields default to "" so an OLD-shaped projects.json (written before this
    # phase, without the keys) still loads via ``_load_registry`` below.
    config_dir: str = ""
    dev_repo_path: str = ""


def _engine_assets_template() -> str:
    """Return the text of the bundled ``columns.yml`` template (DESIGN §9).

    The template ships as **package data** under ``kanbanmate/assets`` and is
    read via :mod:`importlib.resources`, so it resolves from the installed
    package — a wheel or ``pip install -e .`` — rather than a computed repo-root
    path that would not exist in a site-packages install. This is the generic
    default the per-repo clone copies and the operator then edits.

    Returns:
        The text content of ``kanbanmate/assets/columns.yml.tmpl``.
    """
    resource = importlib.resources.files(_ASSET_PACKAGE) / _COLUMNS_TEMPLATE_RESOURCE
    return resource.read_text(encoding="utf-8")


def _projects_path(root: Path) -> Path:
    """Return the ``projects.json`` registry path under *root*.

    Args:
        root: The kanban runtime root.

    Returns:
        The path to ``<root>/projects.json``.
    """
    return root / PROJECTS_FILENAME


def _load_registry(path: Path) -> dict[str, ProjectEntry]:
    """Load the ``{project_node_id: ProjectEntry}`` registry (empty when absent).

    Args:
        path: The ``projects.json`` path.

    Returns:
        The deserialised registry, or an empty mapping when the file is absent.
    """
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8") or "{}")
    return {
        key: ProjectEntry(
            repo=val["repo"],
            clone=val["clone"],
            project_id=val["project_id"],
            status_field_node_id=val["status_field_node_id"],
            option_map=dict(val.get("option_map", {})),
            # ``.get(..., "")`` so an OLD-shaped entry (written before this phase,
            # WITHOUT these keys) still loads with the defaults applied — the
            # registry format stays backward-compatible.
            config_dir=val.get("config_dir", ""),
            dev_repo_path=val.get("dev_repo_path", ""),
        )
        for key, val in raw.items()
    }


def _upsert_project(path: Path, project_node_id: str, entry: ProjectEntry) -> None:
    """Insert/replace the entry keyed by ``project_node_id`` and write back.

    Idempotent: re-running ``init`` for the same project overwrites its entry in
    place (it is keyed by the stable project node id).

    Args:
        path: The ``projects.json`` path.
        project_node_id: The registry key (the Project v2 node id).
        entry: The entry to persist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    registry = _load_registry(path)
    registry[project_node_id] = entry
    serialisable = {key: asdict(val) for key, val in registry.items()}
    path.write_text(json.dumps(serialisable, indent=2, sort_keys=True), encoding="utf-8")


def _resolve_status_field_id(seeder: Seeder, project_id: str, option_map: dict[str, str]) -> str:
    """Resolve the Status field node id for the registry entry.

    The :class:`~kanbanmate.ports.board.Seeder` returns the option map but not
    the field id; the concrete :class:`GithubClient` exposes the cached field via
    its private resolver. We read it through the public board path so the entry
    records the field node id the daemon matches Status moves by.

    Args:
        seeder: The Seeder (a :class:`GithubClient` in production).
        project_id: The project node id.
        option_map: The ``{column_name: option_id}`` map from ``ensure_columns``.

    Returns:
        The Status single-select field node id, or ``""`` when the seeder does
        not expose one (a fake in tests).
    """
    # The concrete client knows its project's Status field; a fake Seeder may not.
    resolver = getattr(seeder, "status_field_node_id", None)
    if callable(resolver):
        return str(resolver(project_id))
    return ""


def init(
    repo: str,
    *,
    root: Path | str | None = None,
    clone: Path | str | None = None,
    project_title: str | None = None,
    seeder: Seeder | None = None,
    template_path: Path | str | None = None,
    dev_repo_path: str = "",
    config_dir: str | None = None,
    ensure_clone: Callable[..., object] | None = None,
) -> ProjectEntry:
    """Bootstrap one target project for the daemon (DESIGN §4.3).

    Args:
        repo: The ``owner/name`` slug of the target repository.
        root: The kanban runtime root (default ``~/.kanban``). Pass a ``tmp_path``
            in tests so no real runtime root is touched.
        clone: The local clone path written into the registry and used as the
            ``.claude/kanban/columns.yml`` destination; defaults to the cwd.
        project_title: The Project v2 title to find-or-create; defaults to the
            repo name.
        seeder: The :class:`~kanbanmate.ports.board.Seeder` to drive; defaults to a
            real :class:`GithubClient` built from the loaded token. Tests inject a
            fake so no network call is made.
        template_path: Override for the ``columns.yml`` template source; defaults
            to the engine-bundled ``kanbanmate/assets/columns.yml.tmpl`` package
            resource (read via :mod:`importlib.resources`).
        dev_repo_path: The operator's dev-clone path persisted on the
            :class:`ProjectEntry` (the post-merge ff-only update target, DESIGN
            §10). Configured ONCE at init; the daemon's post-merge update then
            resolves the dev clone from ``projects.json`` rather than demanding it
            on every ``kanban-update-main`` call. Defaults to ``""`` (disabled).
        config_dir: Override for the project's ``.claude`` directory recorded on
            the entry (the launcher's skill-provisioning source). When ``None``
            (the default) it resolves to ``<clone>/.claude`` — the clone's own
            config dir.
        ensure_clone: Injectable clone-bootstrap callable (for tests so ``init``
            never shells to git). When ``None``, defaults to the real
            :meth:`~kanbanmate.adapters.workspace.worktree.GitWorktreeWorkspace.ensure_clone`
            bound to ``(clone, repo, kanban_root=root)``. Called as
            ``ensure_clone(repo_url, base=..., token_path=...)`` BEFORE the
            ``columns.yml`` write so the clone exists to write into.

    Returns:
        The persisted :class:`ProjectEntry` (also written to ``projects.json``).

    Raises:
        ValueError: When ``repo`` is not an ``owner/name`` slug.
    """
    if "/" not in repo:
        raise ValueError(f"--repo must be 'owner/name', got {repo!r}")
    org, name = repo.split("/", 1)

    resolved_root = DEFAULT_KANBAN_ROOT if root is None else Path(root)
    clone_path = Path.cwd() if clone is None else Path(clone)
    title = project_title or name
    # config_dir defaults to the clone's own ``.claude`` dir (where the launcher
    # COPIES skills/commands/agents from); an operator may override it.
    resolved_config_dir = config_dir if config_dir is not None else str(clone_path / ".claude")
    # Template source: a test override reads the given file as text; production
    # reads the packaged resource text (DESIGN §9 — bundled as package data).
    template_text = (
        Path(template_path).read_text(encoding="utf-8")
        if template_path is not None
        else _engine_assets_template()
    )

    # Build the Seeder lazily: a real GithubClient needs only the token (the
    # project does not exist yet, so no project_id/repo is baked in).
    active_seeder: Seeder = seeder if seeder is not None else GithubClient(load_token())

    # 1. Project (find-or-create). The node id is the registry key + daemon route.
    project_id = active_seeder.ensure_project(org, title)

    # 1b. Link the project to the target repo so it shows in the repo's Projects tab
    #     (the canonical repo↔project association — GitHub does not link an org project
    #     to a repo automatically just because issues are added to both).
    active_seeder.link_to_repo(project_id, repo)

    # 1c. Set a default project short description (phase-33). Idempotent on the
    #     seeder's side: it reads the current value first and SKIPS the write when
    #     the project already has a description, so an operator-authored one is
    #     never clobbered and a re-run of ``init`` is a no-op.
    active_seeder.update_project_description(
        project_id, DEFAULT_PROJECT_DESCRIPTION.format(repo=repo)
    )

    # 2. Columns: read the template's column model and shape the Status field.
    columns = load_columns(template_text)
    column_names = [col.name for col in columns.values()]
    option_map = active_seeder.ensure_columns(project_id, column_names)

    # 2b. Health field (health-field): best-effort find-or-create the per-card "Health"
    #     single-select chip at init so a fresh board carries it immediately. NOT required
    #     — the daemon self-heals on its first tick (``apply_health`` ensures the field) —
    #     so a failure here is logged, never fatal (mirrors update_project_description's
    #     non-fatal posture). The Seeder Protocol does not declare ensure_health_field, so
    #     it is invoked via getattr (the production GithubClient implements it; a seeder
    #     fake without it simply skips this best-effort step).
    ensure_health = getattr(active_seeder, "ensure_health_field", None)
    if callable(ensure_health):
        try:
            ensure_health(project_id)
        except Exception:  # noqa: BLE001 — best-effort; the daemon self-heals on tick 1
            logger.warning(
                "init: best-effort Health field ensure failed; the daemon will create it on "
                "its first tick",
                exc_info=True,
            )

    # 3. Labels: the wave:* / prio:* routing labels the seed step applies.
    label_names = _default_labels()
    active_seeder.ensure_labels(repo, label_names)

    # 3b. Clone bootstrap (phase 14): create/repair the per-repo clone IN PLACE so
    #     the config writes below land in a real working tree (``git init`` is
    #     non-destructive — it preserves the columns.yml we write next). This runs
    #     UNCONDITIONALLY and BEFORE the columns.yml write (port of PoC
    #     plan_init.py:74-76 / executors.py:170-176 ordering — ensure_clone was
    #     outside the n8n org-setup block). The ``repo_url`` is the TOKENLESS
    #     public URL; the ``token`` file under the kanban root installs the
    #     credential helper (14.2) so the long-lived PAT is never written into the
    #     clone's ``.git/config``. Injectable so tests drive a fake (no real git).
    clone_ensure = ensure_clone
    if clone_ensure is None:
        clone_ensure = GitWorktreeWorkspace(
            clone_path, repo=repo, kanban_root=resolved_root
        ).ensure_clone
    repo_url = f"https://github.com/{repo}.git"
    clone_ensure(repo_url, base=DEFAULT_INIT_BASE, token_path=str(resolved_root / "token"))

    # 4. Config: copy the template into the clone so the daemon reads it there.
    clone_columns = clone_path / CLONE_COLUMNS_RELPATH
    clone_columns.parent.mkdir(parents=True, exist_ok=True)
    clone_columns.write_text(template_text, encoding="utf-8")

    # 4b. Transitions: render the per-repo whitelist into the clone (DESIGN §9,
    #     phase 12.7). Divergence from the columns.yml pattern above:
    #     transitions.yml is RENDERED (carries the project slug), not a static
    #     .tmpl asset — the renderer in core/transitions_defaults is the source
    #     of truth.
    write_transitions_yml(clone_path, repo)

    # 5. Registry: persist the binding keyed by the project node id (idempotent).
    #     config_dir/dev_repo_path are recorded so the launcher can provision skills
    #     (config_dir) and the post-merge update can resolve the dev clone
    #     (dev_repo_path) without re-supplying them per call.
    status_field_id = _resolve_status_field_id(active_seeder, project_id, option_map)
    entry = ProjectEntry(
        repo=repo,
        clone=str(clone_path),
        project_id=project_id,
        status_field_node_id=status_field_id,
        option_map=dict(option_map),
        config_dir=resolved_config_dir,
        dev_repo_path=dev_repo_path,
    )
    _upsert_project(_projects_path(resolved_root), project_id, entry)
    return entry


def _default_labels() -> list[str]:
    """Return the default ``wave:*`` / ``prio:*`` routing labels to ensure.

    A small, fixed bootstrap set (DESIGN §4.3). The seed step creates any further
    label on demand when a roadmap item references a new ``wave``/``prio`` value,
    so this set need only cover the common defaults.

    Returns:
        The label names to ensure on the repo at ``init`` time.
    """
    waves = [f"wave:{n}" for n in range(1, 5)]
    prios = [f"prio:P{n}" for n in range(1, 4)]
    return [*waves, *prios]


def write_transitions_yml(clone_dir: Path, project: str) -> Path:
    """Write ``<clone>/.claude/kanban/transitions.yml`` for *project*.

    Creates parent directories as needed. Idempotent (overwrites on repeat
    calls). The content is the rendered whitelist produced by
    :func:`~kanbanmate.core.transitions_defaults.render_transitions_yaml`.

    This function does I/O (``Path.write_text``) — it lives in the CLI
    layer, NOT ``core/``, per the hexagonal layering guard.

    Args:
        clone_dir: Root of the project clone directory.
        project: The GitHub project slug (e.g. ``"owner/repo"``).

    Returns:
        The ``Path`` that was written.
    """
    dest = clone_dir / CLONE_TRANSITIONS_RELPATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render_transitions_yaml(project), encoding="utf-8")
    return dest
