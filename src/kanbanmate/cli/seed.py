"""Per-repo tier of the installer: ``kanban seed`` (DESIGN §4.3).

``kanban seed <ROADMAP.md>`` turns a roadmap document into a seeded Backlog:

1. **Parse** the roadmap into ordered :class:`SeedItem` records (one per
   ``## [CODE] Title`` heading, with optional ``wave``/``prio``/``depends``
   metadata) — a pure port of the PoC ``cli/roadmap.py``.
2. **Order** the items so every dependency is created before its dependents
   (a topological sort; a cycle or unknown dependency fails loud).
3. **Create** an issue per item (creating any missing ``wave:*``/``prio:*``
   labels first), add it to the project, and set its Status to ``Backlog``
   explicitly — Projects v2 adds items with NO Status (there is no "default
   column on add"), so the column is set per item via ``move_card``.
4. **Rewrite** ``Depends on RPx`` references to the real ``Depends on #N`` issue
   numbers (known only after creation) via a second body patch.

There is **no webhook / n8n step** (polling is the sole ingress, DESIGN §4.3).

Layering: ``cli`` is an entrypoint (DESIGN §3.2); it composes the concrete
:class:`~kanbanmate.adapters.github.client.GithubClient` (a
:class:`~kanbanmate.ports.board.Seeder`), injectable so tests drive a fake and
never touch the network. The roadmap parsing and ordering are pure helpers in
this module (no I/O), exercised directly in tests.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from kanbanmate.adapters.github.client import GithubClient
from kanbanmate.adapters.github.token import load_token
from kanbanmate.cli.init import (
    DEFAULT_KANBAN_ROOT,
    ProjectEntry,
    _load_registry,
    _projects_path,
)
from kanbanmate.ports.board import Seeder

# The Status column freshly-seeded cards land in. Set explicitly per item because
# Projects v2 adds items with NO Status (no "default column on add"). It MUST exist on
# the board's Status field; the seed verifies that up front and fails clean rather than
# half-seeding (port of the PoC ``cli/runners.py`` ``SEED_LANDING_COLUMN`` + the
# landing-option pre-check at runners.py:248-262 / executors.py:235).
SEED_LANDING_COLUMN = "Backlog"

# A roadmap item heading: ``## [CODE] Title``.
_HEADING = re.compile(r"^##\s+\[(?P<code>[^\]]+)\]\s+(?P<title>.+?)\s*$")

# A metadata line under a heading: ``wave: 1`` / ``prio: P1`` / ``depends: A, B``.
_META = re.compile(r"^(?P<key>wave|prio|depends)\s*:\s*(?P<val>.+?)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class SeedItem:
    """One roadmap item to be created as a Backlog issue.

    Attributes:
        code: The roadmap code (e.g. ``RP1``); the dependency key.
        title: The issue title (``[CODE] Title``).
        body: The issue body (description + a ``Depends on <codes>`` line).
        labels: The ``wave:*`` / ``prio:*`` labels derived from the metadata.
        depends: The codes this item depends on (creation order + body rewrite).
    """

    code: str
    title: str
    body: str
    labels: list[str] = field(default_factory=list)
    depends: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CreatedIssue:
    """A created issue, mapping a roadmap code to its issue number/node.

    Attributes:
        code: The roadmap code the issue was created from.
        issue_number: The GitHub issue number assigned on creation.
        issue_node_id: The issue's global node id (for the body patch).
    """

    code: str
    issue_number: int
    issue_node_id: str


def _flush(
    code: str,
    title: str,
    wave: str | None,
    prio: str | None,
    depends: list[str],
    desc_lines: list[str],
) -> SeedItem:
    """Assemble a :class:`SeedItem` from the accumulated heading + metadata.

    Args:
        code: The roadmap code.
        title: The heading title.
        wave: The ``wave`` metadata value, or ``None``.
        prio: The ``prio`` metadata value, or ``None``.
        depends: The dependency codes.
        desc_lines: The free-form description lines under the heading.

    Returns:
        The assembled :class:`SeedItem` (body carries a ``Depends on`` line when
        the item has dependencies).
    """
    labels: list[str] = []
    if wave:
        labels.append(f"wave:{wave}")
    if prio:
        labels.append(f"prio:{prio}")
    desc = "\n".join(desc_lines).strip()
    # The **roadmap** marker is the FIRST body element (§29.2): it is the durable ticket↔roadmap
    # binding the hardened prompts read (IDENTITY-THEN-STATE) and kanban-update-body validates. It
    # is its OWN paragraph (blank-line separated), so ``ticket_fields``'s anchored regex parses it
    # and the ``Depends on …`` line stays byte-identical — ``_rewrite_depends``'s exact-string
    # replace still matches (the marker precedes the description + depends line, never splicing it).
    body_parts = [f"**roadmap**: {code}"]
    if desc:
        body_parts.append(desc)
    if depends:
        body_parts.append("Depends on " + ", ".join(depends))
    body = "\n\n".join(body_parts)
    return SeedItem(
        code=code,
        title=f"[{code}] {title}",
        body=body,
        labels=labels,
        depends=list(depends),
    )


def parse_roadmap(text: str) -> list[SeedItem]:
    """Parse a ``ROADMAP.md`` document into ordered :class:`SeedItem` records (pure).

    Recognised shape (one item per heading)::

        ## [RP1] Bootstrap dispatcher
        wave: 1
        prio: P1
        depends: RP2, RP3        # optional, comma-separated codes

        Free-form description until the next ``## `` heading.

    Args:
        text: The raw roadmap document.

    Returns:
        The roadmap items in document order.
    """
    items: list[SeedItem] = []
    code: str | None = None
    title: str = ""
    wave: str | None = None
    prio: str | None = None
    depends: list[str] = []
    desc_lines: list[str] = []

    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            if code is not None:
                items.append(_flush(code, title, wave, prio, depends, desc_lines))
            code = heading.group("code").strip()
            title = heading.group("title").strip()
            wave = prio = None
            depends = []
            desc_lines = []
            continue
        if code is None:
            # Pre-amble before the first heading is ignored.
            continue
        meta = _META.match(line)
        if meta:
            key, val = meta.group("key").lower(), meta.group("val").strip()
            if key == "wave":
                wave = val
            elif key == "prio":
                prio = val
            elif key == "depends":
                depends = [d.strip() for d in val.split(",") if d.strip()]
            continue
        desc_lines.append(line)

    if code is not None:
        items.append(_flush(code, title, wave, prio, depends, desc_lines))
    return items


def topo_order(items: list[SeedItem]) -> list[SeedItem]:
    """Order ``items`` so every dependency precedes its dependents.

    A depth-first topological sort. Items keep their relative document order
    where dependencies allow it.

    Args:
        items: The roadmap items to order.

    Returns:
        The items in dependency-respecting order.

    Raises:
        ValueError: On a dependency cycle or a reference to an unknown code.
    """
    by_code = {item.code: item for item in items}
    visited: dict[str, int] = {}  # 0 = visiting (on stack), 1 = done
    order: list[SeedItem] = []

    def visit(code: str) -> None:
        state = visited.get(code)
        if state == 1:
            return
        if state == 0:
            raise ValueError(f"dependency cycle detected at '{code}'")
        if code not in by_code:
            raise ValueError(f"unknown dependency '{code}'")
        visited[code] = 0
        for dep in by_code[code].depends:
            if dep not in by_code:
                raise ValueError(f"unknown dependency '{dep}' (required by '{code}')")
            visit(dep)
        visited[code] = 1
        order.append(by_code[code])

    for item in items:
        visit(item.code)
    return order


def _rewrite_depends(body: str, depends: list[str], numbers: dict[str, int]) -> str:
    """Rewrite ``Depends on <codes>`` to ``Depends on #N1, #N2`` in ``body``.

    The roadmap carries dependencies as codes (``Depends on RP2, RP3``) because
    the real issue numbers are unknown until creation. This replaces each code
    with its now-known ``#N``.

    Args:
        body: The issue body created from the roadmap item.
        depends: The dependency codes for this item.
        numbers: The ``{code: issue_number}`` map of created issues.

    Returns:
        The body with the ``Depends on`` line rewritten to ``#N`` references.
    """
    refs = ", ".join(f"#{numbers[dep]}" for dep in depends if dep in numbers)
    code_line = "Depends on " + ", ".join(depends)
    return body.replace(code_line, f"Depends on {refs}")


def _resolve_project_entry(repo: str, root: Path) -> ProjectEntry:
    """Resolve the registered :class:`ProjectEntry` for ``repo`` from ``projects.json`` (#12).

    Restores the PoC's init→seed handoff (``cli/runners.py:244-258``): when the
    operator omits ``--project-id``, ``seed`` looks the project up in the registry
    by its ``repo`` slug — recovering the project node id (and, on the entry, the
    status-field node id + option map the PoC also carried). The registry is keyed
    by the project node id, so we scan the entries for the first whose ``repo``
    matches.

    Args:
        repo: The ``owner/name`` slug to resolve.
        root: The kanban runtime root holding ``projects.json``.

    Returns:
        The matching :class:`ProjectEntry`.

    Raises:
        ValueError: When no project is registered for ``repo`` (the operator must
            run ``kanban init`` first) — the PoC's "run kanban init first" error.
    """
    registry = _load_registry(_projects_path(root))
    for entry in registry.values():
        if entry.repo == repo:
            return entry
    raise ValueError(f"no project registered for {repo} — run `kanban init` first")


def _known_status_options(
    seeder: Seeder, project_id: str, entry: ProjectEntry | None
) -> dict[str, str] | None:
    """Resolve the project's known Status options for the landing pre-check (#3).

    Two sources, in precedence order, mirroring the PoC's landing-option lookup
    (``cli/runners.py:248-258`` read ``entry.option_map``):

    1. a live ``status_options(project_id)`` capability the seeder may expose
       (the concrete production client / a test fake) — read through a
       ``getattr``-optional probe, the same pattern :func:`_resolve_status_field_id`
       uses, so a fake Seeder without it is not forced to implement it;
    2. the registry :class:`ProjectEntry`'s ``option_map`` recorded by ``kanban
       init`` (the PoC's source of truth) when no live probe is available.

    Returns ``None`` when NEITHER source can name the options — the pre-check then
    cannot decide and is skipped (back-compat: an explicit ``--project-id`` with a
    bare fake Seeder is not blocked, exactly as before this guard existed).

    Args:
        seeder: The Seeder driving the seed (a :class:`GithubClient` in production).
        project_id: The resolved Project v2 node id.
        entry: The registry entry resolved for the repo, or ``None`` when the
            caller passed an explicit ``--project-id`` (no registry lookup).

    Returns:
        A ``{column_name: option_id}``-style mapping of known options, or ``None``
        when the options cannot be determined from either source.
    """
    probe = getattr(seeder, "status_options", None)
    if callable(probe):
        return dict(probe(project_id))
    if entry is not None and entry.option_map:
        return dict(entry.option_map)
    return None


def _write_seed_map(root: Path, repo: str, created: list[CreatedIssue]) -> Path:
    """Persist the code→issue map to ``<root>/seed-map/<owner>-<repo>.json`` (§29.2).

    The seed previously DISCARDED the :class:`CreatedIssue` list (cli/app.py only echoed a count),
    losing the roadmap-code → issue-number binding. The hardened identity check + future ops want
    that binding durable, so it is written here as a JSON object ``{code: issue_number}`` plus the
    node id, keyed by the slug-safe ``<owner>-<repo>`` filename. Creates ``<root>/seed-map/`` if
    missing; overwriting an existing map (a re-seed) is fine and deterministic (sorted keys).

    Args:
        root: The kanban runtime root (default ``~/.kanban``).
        repo: The ``owner/name`` slug the issues were created in.
        created: The created issues, in creation (dependency) order.

    Returns:
        The path to the written map file.
    """
    map_dir = root / "seed-map"
    map_dir.mkdir(parents=True, exist_ok=True)
    # ``owner/repo`` → ``owner-repo`` so the slug is a single safe filename component.
    path = map_dir / f"{repo.replace('/', '-')}.json"
    payload = {
        "repo": repo,
        "issues": {
            c.code: {"issue_number": c.issue_number, "issue_node_id": c.issue_node_id}
            for c in created
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def seed(
    roadmap: Path | str,
    *,
    repo: str,
    project_id: str | None = None,
    root: Path | str | None = None,
    seeder: Seeder | None = None,
) -> list[CreatedIssue]:
    """Seed the board from a roadmap (DESIGN §4.3).

    Creates issues in dependency order, adds each to the project (landing in
    Backlog), then rewrites every ``Depends on`` line to the real ``#N``
    references via a body patch.

    The Project v2 node id is resolved with a two-step precedence (#12 PoC parity,
    ``cli/runners.py:244-258``):

    1. an explicit ``project_id`` (the CLI ``--project-id`` override) wins; else
    2. it is auto-resolved from ``projects.json`` by ``repo`` (the init→seed
       handoff) — erroring "run ``kanban init`` first" when the repo is unregistered.

    Args:
        roadmap: Path to the ``ROADMAP.md`` to seed from (or its text path).
        repo: The target repository as ``owner/name``.
        project_id: The Project v2 node id (from ``kanban init``) to add issues to.
            Optional: when ``None`` (no ``--project-id``), it is resolved from the
            registry by ``repo``. An explicit value is the override.
        root: The kanban runtime root holding ``projects.json`` (default
            ``~/.kanban``). Only consulted when ``project_id`` is omitted.
        seeder: The :class:`~kanbanmate.ports.board.Seeder` to drive; defaults to a
            real :class:`GithubClient` built from the loaded token. Tests inject a
            fake so no network call is made.

    Returns:
        The created issues, in creation (dependency) order.

    Raises:
        ValueError: On a dependency cycle, an unknown dependency code, or — when
            ``project_id`` is omitted — an unregistered ``repo`` (run init first).
    """
    text = Path(roadmap).read_text(encoding="utf-8")
    items = parse_roadmap(text)
    ordered = topo_order(items)

    # Resolve the project id: an explicit --project-id overrides; otherwise look it
    # up in the registry by repo (the init→seed handoff). Resolution happens BEFORE
    # any issue is created so an unregistered repo fails clean rather than mid-seed.
    resolved_project_id = project_id
    resolved_entry: ProjectEntry | None = None
    # The runtime root holds the persisted code→issue map (§29.2). Computed once at function
    # scope (not just inside the registry-resolve branch) so the map write below has it even when
    # an explicit --project-id is passed.
    resolved_root = DEFAULT_KANBAN_ROOT if root is None else Path(root)
    if resolved_project_id is None:
        resolved_entry = _resolve_project_entry(repo, resolved_root)
        resolved_project_id = resolved_entry.project_id

    # The default client needs ``project_id`` so ``move_card`` can resolve the
    # Status field (the Seeder-only ctor leaves it blank; seeding now also sets Status).
    active_seeder: Seeder = (
        seeder if seeder is not None else GithubClient(load_token(), project_id=resolved_project_id)
    )

    # Pre-check the landing column EXISTS before creating ANY issue (#3, PoC parity). Without
    # this a seed would create issue 1, then crash on its ``move_card(item, "Backlog")`` — a
    # half-seed leaving orphaned issues. The guard fails clean up front. When the options cannot
    # be determined (a bare fake Seeder + explicit --project-id) the check is skipped (back-compat).
    known_options = _known_status_options(active_seeder, resolved_project_id, resolved_entry)
    if known_options is not None and SEED_LANDING_COLUMN not in known_options:
        raise ValueError(
            f"project for {repo} has no '{SEED_LANDING_COLUMN}' Status option "
            f"(the seed landing column) — re-run `kanban init` to create the board columns"
        )

    created: list[CreatedIssue] = []
    numbers: dict[str, int] = {}
    nodes: dict[str, str] = {}
    # 1. Create each issue (dependencies first), add it to the project, and place it
    #    in Backlog. Projects v2 adds items with NO Status, so Backlog must be set
    #    explicitly — without this the cards land in "No Status" and the daemon logs
    #    "unknown column ''" for each (DESIGN §9: Backlog is the inert seed target).
    for item in ordered:
        node_id, number = active_seeder.create_issue(repo, item.title, item.body, item.labels)
        item_id = active_seeder.add_to_project(resolved_project_id, node_id)
        active_seeder.move_card(item_id, SEED_LANDING_COLUMN)
        created.append(CreatedIssue(code=item.code, issue_number=number, issue_node_id=node_id))
        numbers[item.code] = number
        nodes[item.code] = node_id

    # 2. Rewrite the Depends-on codes to real #N now that all numbers are known.
    for item in ordered:
        if item.depends:
            new_body = _rewrite_depends(item.body, item.depends, numbers)
            active_seeder.update_issue_body(nodes[item.code], new_body)

    # 3. Persist the code→issue map (§29.2) so the binding is not discarded after the seed.
    _write_seed_map(resolved_root, repo, created)

    return created
