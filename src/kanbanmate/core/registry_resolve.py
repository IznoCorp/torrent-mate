"""Pure registry-resolution helpers for the multi-project / multi-org daemon (DESIGN §2.2).

The runtime registry (``<root>/projects.json``) generalises from "exactly one project" to
N entries (still keyed by the stable ``project_id`` node id). Three callers need to resolve
the RIGHT entry out of the registry: the daemon (which entries to tick), the bin helpers
(``kanban-move`` / ``kanban-session-end`` — which board does this issue belong to), and the
``kanban serve`` webhook receiver (which project did this event hit). The selection logic is
the SAME everywhere, so it lives here once.

This module is **pure** (DESIGN §3.2 — ``core`` imports nothing with I/O and nothing from an
upper layer). It operates on the ALREADY-LOADED registry mapping the I/O caller passes in
(``cli.init._load_registry`` reads the file; ``bin``/``daemon`` call these resolvers on the
result). The :class:`ProjectEntryLike` Protocol describes the read shape the resolvers need
without importing the concrete :class:`~kanbanmate.cli.init.ProjectEntry` (which lives in the
``cli`` entrypoint above ``core``) — so ``core`` stays leaf and the layering guard is satisfied.

Issue-number collisions are real: two repos can both carry issue ``#5``. So
:func:`resolve_by_issue` requires a ``repo`` hint when the registry holds more than one entry;
with N=1 the hint is ignored (the sole entry is returned — the back-compat fast-path).
"""

from __future__ import annotations

import hashlib
from typing import Protocol, TypeVar, runtime_checkable

# The hex length of the deterministic id-hash appended by :func:`safe_project_id` (#6 collision
# resistance). 12 hex chars = 48 bits of the sha256 digest — short enough to keep the slug tidy yet
# making a collision between distinct ids astronomically unlikely (it is for uniqueness, not
# security). Kept a module constant so the slug format has one source of truth.
_PROJECT_SLUG_HASH_LEN = 12


@runtime_checkable
class ProjectEntryLike(Protocol):
    """The minimal read shape the registry resolvers need (structural typing).

    A :class:`~kanbanmate.cli.init.ProjectEntry` satisfies this Protocol, but ``core`` must
    not import that ``cli``-layer class (downward-only imports, DESIGN §3.2). Declaring the
    shape here keeps the resolvers fully typed without an upward import. Only the attributes
    the selection logic reads are listed.

    The attributes are declared as READ-ONLY :func:`property` so a FROZEN dataclass
    (:class:`~kanbanmate.cli.init.ProjectEntry` is ``frozen=True``) structurally satisfies the
    Protocol — a plain settable attribute declaration would reject a frozen (read-only) field as a
    non-subtype under the resolver TypeVar bound. The resolvers only READ these, never write them.

    Attributes:
        repo: The ``owner/name`` slug (the repo-hint disambiguator).
        project_id: The Project v2 node id (the registry key + the by-id selector).
        enabled: Whether the daemon drives this project (the enabled filter).
    """

    @property
    def repo(self) -> str:
        """The ``owner/name`` slug (read-only — the repo-hint disambiguator)."""

    @property
    def project_id(self) -> str:
        """The Project v2 node id (read-only — the registry key + by-id selector)."""

    @property
    def enabled(self) -> bool:
        """Whether the daemon drives this project (read-only — the enabled filter)."""


# Generic over the concrete entry type so the resolvers PRESERVE it (a ``dict[str, ProjectEntry]``
# in → a ``ProjectEntry`` / ``list[ProjectEntry]`` out), rather than widening to the Protocol. The
# bound keeps the resolvers reading only the Protocol's attributes while callers keep their type.
_E = TypeVar("_E", bound=ProjectEntryLike)


def resolve_by_project_id(
    registry: dict[str, _E],
    project_id: str,
) -> _E | None:
    """Return the entry whose ``project_id`` matches, or ``None`` when absent.

    The registry is keyed by ``project_id``, so this is an exact, unambiguous lookup — the
    launched-agent path (the worktree carries a project pin) and the webhook receiver
    (the payload carries ``project_node_id``) both resolve through here with zero ambiguity.

    Args:
        registry: The loaded ``{project_id: entry}`` registry.
        project_id: The Project v2 node id to look up.

    Returns:
        The matching entry, or ``None`` when no entry carries that ``project_id``.
    """
    # Prefer the keyed lookup (the registry IS keyed by project_id), but fall back to a value
    # scan so a registry whose key drifted from its entry's project_id still resolves (defensive
    # — the upsert keeps them in lock-step, but a hand-edited file might not).
    entry = registry.get(project_id)
    if entry is not None:
        return entry
    for candidate in registry.values():
        if candidate.project_id == project_id:
            return candidate
    return None


def resolve_by_repo(
    registry: dict[str, _E],
    repo: str,
) -> list[_E]:
    """Return every entry bound to ``repo`` (may be >1 — one repo, several boards).

    A single repo can back more than one Project v2 board, so this returns a LIST (sorted by
    ``project_id`` for a stable order). The match is case-insensitive on the slug (GitHub
    treats ``owner/Name`` and ``owner/name`` as the same repo).

    Args:
        registry: The loaded ``{project_id: entry}`` registry.
        repo: The ``owner/name`` slug to match.

    Returns:
        The entries bound to ``repo``, sorted by ``project_id`` (empty when none match).
    """
    needle = repo.casefold()
    matches = [entry for entry in registry.values() if entry.repo.casefold() == needle]
    return sorted(matches, key=lambda entry: entry.project_id)


def resolve_by_issue(
    registry: dict[str, _E],
    issue: int,
    *,
    repo_hint: str | None = None,
) -> _E | None:
    """Resolve the entry an ``issue`` belongs to, disambiguated by ``repo_hint`` when N>1.

    The hard problem is the issue-number collision: ``owner/r1#5`` and ``owner/r2#5`` are two
    different tickets on two different boards. Issue NUMBER alone cannot identify the board, so:

    * **N=1** (one enabled entry) — return it (the back-compat fast-path; the hint is ignored,
      so an existing single-project root resolves exactly as before, with or without a hint).
    * **N>1, ``repo_hint`` given** — resolve via :func:`resolve_by_repo`; return the sole match,
      or ``None`` when the hint is ambiguous (the repo backs >1 board — the caller must pass a
      ``project_id`` instead) or matches nothing.
    * **N>1, no ``repo_hint``** — ``None`` (ambiguous — the caller must supply a hint or fail
      loud with the candidate list).

    The ``issue`` argument is accepted for symmetry + future use (e.g. a cross-board index); the
    current resolution keys on the enabled-count + repo hint, NOT the number itself, because the
    registry does not record per-issue ownership (issues live on the board, resolved at tick time).

    Args:
        registry: The loaded ``{project_id: entry}`` registry.
        issue: The issue number the helper/CLI was invoked for (accepted for symmetry).
        repo_hint: The ``owner/name`` slug disambiguating which board when N>1 (``None`` → no hint).

    Returns:
        The resolved entry, or ``None`` when the registry is empty, the hint is missing/ambiguous,
        or it matches nothing.
    """
    enabled = enabled_entries(registry)
    if not enabled:
        return None
    if len(enabled) == 1:
        # N=1 fast-path: the sole enabled entry, hint ignored (back-compat).
        return enabled[0]
    if repo_hint is None:
        # Ambiguous: more than one board and no disambiguator. The caller fails loud.
        return None
    matches = resolve_by_repo({e.project_id: e for e in enabled}, repo_hint)
    if len(matches) == 1:
        return matches[0]
    # Zero matches → not found; >1 → the repo backs several boards (need a project_id, not a repo).
    return None


def safe_project_id(project_id: str) -> str:
    """Sanitise a Project v2 node id into a COLLISION-RESISTANT filesystem-safe slug (DESIGN §3.2).

    Project node ids are base64-ish (e.g. ``PVT_kwHOA...=``) and may carry ``=`` / ``/`` /
    other characters that are unsafe or path-escaping as a directory name. The per-project
    store sub-root (``<root>/projects/<safe(project_id)>/``) must confine each project's state
    to ONE directory and never escape to a parent/sibling. This applies the SAME alphanumeric /
    ``._-`` filter the store's :meth:`~kanbanmate.adapters.store.fs_store.FsStateStore.bump_retry`
    sanitisation invariant uses (any other character → ``_``), so the slug is deterministic and
    contained.

    Collision resistance (#6): the char-by-char filter alone is LOSSY — two DISTINCT ids that
    differ only in unsafe characters (e.g. ``"a/b"`` and ``"a+b"`` → both ``"a_b"``) would collapse
    to the SAME slug and so share a store sub-root, silently cross-contaminating their per-project
    state. To make the slug injective enough for the filesystem, a short, deterministic hash of the
    FULL original id is appended (``<sanitised>-<hash>``), so two distinct ids can never share a
    sub-root even when their sanitised stems match. The hash is :func:`hashlib.sha256` truncated to
    :data:`_PROJECT_SLUG_HASH_LEN` hex chars — purely for uniqueness (not security), keeping the slug
    short while making a collision astronomically unlikely. The function stays PURE + deterministic,
    so the daemon (which WRITES the sub-root) and the agent helpers (which READ it) always agree.

    Args:
        project_id: The Project v2 node id to slugify.

    Returns:
        A filesystem-safe, collision-resistant slug ``<sanitised>-<hash>`` (the sanitised stem is
        confined to ``[A-Za-z0-9._-]``, ``"_"`` when nothing survives; the hash disambiguates).
    """
    sanitised = "".join(c if c.isalnum() or c in "._-" else "_" for c in project_id) or "_"
    # Append a short deterministic hash of the FULL id so two distinct ids whose sanitised stems
    # collide still get distinct sub-roots (the lossy char filter alone is not injective).
    digest = hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:_PROJECT_SLUG_HASH_LEN]
    return f"{sanitised}-{digest}"


def enabled_entries(registry: dict[str, _E]) -> list[_E]:
    """Return the enabled entries, sorted by ``project_id`` for a deterministic sweep order.

    The daemon ticks only enabled projects (an operator may pause one with ``enabled=False``
    without de-registering it, DESIGN §3.1). Sorting by ``project_id`` gives the sweep a stable,
    reproducible order (so the GitHub rate budget and the per-project heartbeat ordering are
    deterministic across restarts).

    Args:
        registry: The loaded ``{project_id: entry}`` registry.

    Returns:
        The entries whose ``enabled`` is truthy, sorted by ``project_id``.
    """
    return sorted(
        (entry for entry in registry.values() if entry.enabled),
        key=lambda entry: entry.project_id,
    )


__all__ = [
    "ProjectEntryLike",
    "enabled_entries",
    "resolve_by_issue",
    "resolve_by_project_id",
    "resolve_by_repo",
    "safe_project_id",
]
