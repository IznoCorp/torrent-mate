"""Label operations for the GitHub Projects v2 board adapter (extracted mixin).

Extracted from :mod:`kanbanmate.adapters.github.client` (the skiff fast-track ``track:*`` methods
landed it at the 1000-LOC hard ceiling — a behaviour-preserving move, mirroring the
:mod:`kanbanmate.adapters.store.fs_breadcrumbs` extraction off ``fs_store`` and the earlier
``_transport`` / ``_health`` carve-outs off this same client). The bodies, docstrings, GraphQL
builders, parsers, and error handling are byte-identical to the methods that lived inline.

Three label methods live here, all mixed into :class:`~kanbanmate.adapters.github.client.GithubClient`
so its public board surface is unchanged:

* :meth:`GithubLabelsMixin.ensure_labels` — Seeder idempotent find-or-create over a repo's labels
  (``{name: id}``); reused by ``create_issue`` and ``set_issue_track_label``.
* :meth:`GithubLabelsMixin.set_issue_track_label` — the skiff manual fast-track override: stamp (or
  clear) a single ``track:full|lite|express`` label on an issue, idempotently.
* :meth:`GithubLabelsMixin.board_item_tracks` — a UI-only read returning ``{issue_number:
  track_value}`` for every board card carrying a ``track:*`` label.

Layering: imports only sibling adapter modules (:mod:`._queries`, :mod:`._parsers`) and core
defaults (:data:`kanbanmate.core.transitions_defaults.TRACK_VALUES`) — the same downward-only
dependencies the host client already carries (adapters→adapters / adapters→core).
"""

from __future__ import annotations

from kanbanmate.adapters.github import _parsers, _queries
from kanbanmate.adapters.github._parsers import raise_for_errors
from kanbanmate.adapters.github._transport import GraphQLTransport
from kanbanmate.adapters.github.types import IssueRef
from kanbanmate.core.transitions_defaults import TRACK_VALUES


class GithubLabelsMixin:
    """Label operations mixed into :class:`~kanbanmate.adapters.github.client.GithubClient`.

    A behaviour-preserving carve-out of the three ``track:*`` / label methods. Operates on the host
    client's GraphQL seam (:attr:`_graphql`), the resolved repo/project ids (:attr:`_repo` /
    :attr:`_project_id`), and the host's :meth:`fetch_issue` REST read — every member the methods
    relied on inline. They are declared here as class-level annotations / a stub so mypy-strict sees
    the members the mixin uses; the concrete implementations live on the host client.

    Attributes:
        _graphql: The GraphQL transport seam (set by the host client's ``__init__``).
        _repo: The ``owner/name`` slug of the client's repository.
        _project_id: The ``ProjectV2`` node id of the board.
    """

    _graphql: GraphQLTransport
    _repo: str
    _project_id: str

    def fetch_issue(self, issue_number: int) -> IssueRef:  # pragma: no cover - provided by host
        """Read an issue's identity + body (host-client method the mixin relies on).

        Declared here only so mypy sees the member the mixin calls; the concrete implementation is
        :meth:`~kanbanmate.adapters.github.client.GithubClient.fetch_issue`.
        """
        raise NotImplementedError

    def ensure_labels(self, repo: str, labels: list[str]) -> dict[str, str]:
        """Idempotently ensure ``labels`` exist on ``repo``; return ``{name: id}``.

        Existing labels are reused; missing ones are created (a neutral grey
        ``ededed``). The returned map covers exactly the requested ``labels``.

        Args:
            repo: The ``owner/name`` repository slug.
            labels: The label names to find-or-create.

        Returns:
            A ``{label_name: label_id}`` map for every requested label.
        """
        owner, name = repo.split("/", 1)
        repo_node, existing = _parsers.parse_repo(self._graphql(_queries.repo_id(owner, name)))
        result = dict(existing)
        for label in labels:
            if label in result:
                continue
            node_id, label_name = _parsers.parse_created_label(
                self._graphql(_queries.create_label(repo_node, label, "ededed"))
            )
            result[label_name] = node_id
        return {label: result[label] for label in labels}

    def set_issue_track_label(self, issue_number: int, track_value: str | None) -> None:
        """Set (or clear) the skiff fast-track ``track:*`` manual-override label on an issue.

        The operator/triage forces a lane by stamping a single ``track:full|lite|express``
        label on the issue. This writes that override idempotently: any existing
        ``track:*`` labels except the target are removed, then the target is (re)added.
        Passing ``track_value=None`` CLEARS the override — every ``track:*`` label is
        removed and none is added.

        Resolves the issue's node id + current labels via :meth:`fetch_issue`, then maps
        the label NAMES it needs (the target plus every stale ``track:*``) to their node
        ids via :meth:`ensure_labels` (find-or-create — the target is created if absent;
        stale labels already exist since they are on the issue). The remove then add
        mutations run through :attr:`_graphql`, inheriting the client's mandatory
        connect + read timeouts.

        Args:
            issue_number: The issue number in the client's repository.
            track_value: A value in :data:`kanbanmate.core.transitions_defaults.TRACK_VALUES`
                (``"full"`` / ``"lite"`` / ``"express"``) to force that lane, or ``None``
                to clear the override.

        Raises:
            ValueError: When ``track_value`` is neither ``None`` nor in ``TRACK_VALUES``.
            GraphQLError: When a label mutation response carries errors.
            GitHubHTTPError: When the issue read fails.
        """
        # Fail loud BEFORE any network write on an unknown lane value.
        if track_value is not None and track_value not in TRACK_VALUES:
            raise ValueError(
                f"unknown track value {track_value!r} — expected one of {TRACK_VALUES} or None"
            )

        ref = self.fetch_issue(issue_number)
        target_name = f"track:{track_value}" if track_value is not None else None
        # Every ``track:*`` label currently on the issue that is NOT the target → remove.
        stale_names = [
            name for name in ref.labels if name.startswith("track:") and name != target_name
        ]

        # Resolve the node ids for exactly the names we touch in ONE find-or-create call:
        # the target (created if absent) plus every stale track label (already exist).
        names_to_resolve = list(stale_names)
        if target_name is not None:
            names_to_resolve.append(target_name)
        label_ids = self.ensure_labels(self._repo, names_to_resolve) if names_to_resolve else {}

        if stale_names:
            remove_ids = [label_ids[name] for name in stale_names]
            data = self._graphql(_queries.remove_labels_from_issue(ref.node_id, remove_ids))
            raise_for_errors(data)
        if target_name is not None:
            data = self._graphql(
                _queries.add_labels_to_issue(ref.node_id, [label_ids[target_name]])
            )
            raise_for_errors(data)

    def board_item_tracks(self) -> dict[int, str]:
        """Return ``{issue_number: track_value}`` for board items carrying a ``track:*`` label.

        A UI-only read (the config/monitoring SPA shows which cards carry a manual
        fast-track override). Paginates :func:`kanbanmate.adapters.github._queries.project_item_labels`,
        and for each Issue item with a ``track:<value>`` label records ``{number: value}``
        (the ``track:`` prefix stripped). Items with no ``track:*`` label — and draft /
        PR items with no issue content — are omitted. Does NOT touch the daemon snapshot.

        Each page is fetched through :attr:`_graphql`, so the mandatory connect + read
        timeouts are preserved on every request.

        Returns:
            A ``{issue_number: track_value}`` map for every board card carrying a
            ``track:*`` label.
        """
        result: dict[int, str] = {}
        after: str | None = None
        max_pages = 10  # 1000 items — well beyond any realistic board (mirrors snapshot)

        for _ in range(max_pages):
            data = self._graphql(_queries.project_item_labels(self._project_id, after=after))
            raise_for_errors(data)
            items = (((data.get("data") or {}).get("node") or {}).get("items")) or {}
            for node in items.get("nodes") or []:
                content = node.get("content") or {}
                number = content.get("number")
                if number is None:
                    continue  # a draft / PR item — no issue number.
                for label in (content.get("labels") or {}).get("nodes") or []:
                    name = str(label.get("name", ""))
                    if name.startswith("track:"):
                        result[int(number)] = name[len("track:") :]
                        break  # at most one track label per card (the writer enforces it).
            page_info = items.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            end_cursor = page_info.get("endCursor")
            if not end_cursor or end_cursor == after:
                break  # malformed / non-advancing cursor — stop rather than loop forever.
            after = end_cursor
        return result
