"""NativeBoardBackend: a decorator that repatriates board placement off GitHub (anchor §4.3).

Composes a forge client (``GithubClient``) for forge ops — issue state, comments,
PRs — and a ``FsBoardStateStore`` for placement authority. Only ``cheap_probe``,
``snapshot``, and ``move_card`` are overridden; every other ``BoardReader`` /
``BoardWriter`` method delegates to the forge client so the daemon tick sees a
structurally identical interface regardless of the selected backend.

The one-way GitHub mirror (§5): on ``move_card`` the native placement is written
first (authority), then mirrored to GitHub via the forge client's ``move_card``
with the **display name** (Status option name) resolved via ``option_name_for_key``.
A mirror failure is logged and swallowed — the native store is already updated.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from kanbanmate.adapters.github.types import CommentRef, IssueContext
from kanbanmate.adapters.store.fs_board import FsBoardStateStore
from kanbanmate.core.domain import BoardSnapshot, Ticket

logger = logging.getLogger(__name__)


class NativeBoardBackend:
    """Decorator over GithubClient — placement authority is the native store (anchor §4.3).

    Satisfies ``BoardReader``, ``BoardWriter``, and ``BoardOrdering``.

    Attributes:
        _forge: The underlying GithubClient (comment/issue/PR ops).
        _store: The native placement store (``FsBoardStateStore``).
        _columns: Ordered column key list (seeded from ``columns.yml`` order).
        _option_name_for_key: Callable resolving a column key → GitHub Status display name.
        _mirror: Optional forge client to mirror placements to GitHub (same as ``_forge``
            when enabled; ``None`` when ``board_mirror=False``).
    """

    def __init__(
        self,
        forge: Any,
        store: FsBoardStateStore,
        columns: list[str],
        option_name_for_key: Callable[[str], str],
        mirror: Any | None = None,
        hybrid: bool = False,
    ) -> None:
        """Construct the native backend.

        Args:
            forge: The GithubClient satisfying ``BoardReader``+``BoardWriter`` for forge ops.
            store: The native placement store.
            columns: Ordered column key list (entry column = ``columns[0]``).
            option_name_for_key: Maps a column key to the GitHub Status option display name.
            mirror: When non-``None``, move operations also call ``mirror.move_card``
                with the resolved display name (one-way mirror, §5).
            hybrid: When ``True`` (board-sync hybrid mode), ``snapshot`` also reconciles a move made
                on the GitHub board back INTO native placement (bidirectional). Combined with the
                ``mirror`` (native→GitHub), the operator can move on EITHER surface. Default ``False``
                = anchor's one-way native (GitHub drift only reconciled via explicit ``import``).
        """
        self._forge = forge
        self._store = store
        self._columns = columns
        self._option_name_for_key = option_name_for_key
        self._mirror = mirror
        self._hybrid = hybrid
        # Inverse of option_name_for_key: GitHub Status display NAME → native column KEY. Used in
        # hybrid mode to map a forge Status (a name) back to the native column key for drift detect.
        self._key_for_name: dict[str, str] = {option_name_for_key(k): k for k in columns}
        # columns.yml does not enforce UNIQUE display names (only non-empty), so two keys could share
        # a display name and silently collapse this inverse map — making hybrid drift detection
        # mis-map a forge Status. Detect + warn (hybrid only) rather than fail silently.
        if hybrid and len(self._key_for_name) < len(set(columns)):
            logger.warning(
                "anchor hybrid: duplicate column display names collapse the Status→key map "
                "(%d names for %d columns) — GitHub→native reconcile may mis-map; make names unique",
                len(self._key_for_name),
                len(set(columns)),
            )

    # ------------------------------------------------------------------
    # BoardReader — overridden
    # ------------------------------------------------------------------

    def cheap_probe(self) -> str:
        """Combined change-detection token: native store version + forge issue probe (anchor §4.4).

        Returns:
            ``"{store_version}:{forge_probe}"`` — changes when the native store is mutated
            (any move/reorder/import) OR when the forge change-token moves (the newest-items
            ``updatedAt`` probe — a GitHub issue created, closed, or otherwise edited).
        """
        doc = self._store.load()
        store_version = doc.get("version", 0)
        try:
            forge_probe = self._forge.cheap_probe()
        except Exception:  # noqa: BLE001 — a forge-probe failure must NOT mask a native change
            # The native store is the placement authority: a move/reorder/import via the HTTP API
            # bumps store_version and MUST still wake the tick even when the forge is unreachable.
            # Use a constant sentinel so a forge outage alone does not churn the token tick-to-tick.
            logger.warning(
                "anchor cheap_probe: forge probe failed; using native-only token (store v%s)",
                store_version,
                exc_info=True,
            )
            forge_probe = "?"
        return f"{store_version}:{forge_probe}"

    def snapshot(self) -> BoardSnapshot:
        """JOIN the forge issue set with the native placement store (anchor §4.5).

        Rules:
        - Issue in forge + in store → ``Ticket(column_key = store placement)``.
        - Issue in forge, NOT in store → register at entry column (``columns[0]``), emit there.
        - Issue closed on GitHub → reflected via forge's closed state (placement irrelevant).
        - Item in store but absent from the forge snapshot → omitted this tick and LOGGED (the
          store retains its placement; it reappears on the next complete forge snapshot — a partial
          forge read must be observable, not a silent card disappearance).

        Returns:
            A ``BoardSnapshot`` structurally identical to the GitHub path so ``diff``/
            ``decide``/``tick`` consume it unchanged.
        """
        # Fetch the forge issue set (identity + open/closed + body). We call the forge's
        # own snapshot to reuse its pagination logic, then DISCARD the column_key (we only
        # want the identity fields). Under native, GitHub's Status is not authoritative.
        forge_snap = self._forge.snapshot()
        doc = self._store.load()
        placement: dict[str, str] = doc.get("placement", {})
        entry_col = self._columns[0] if self._columns else ""
        # Hybrid board-sync bookkeeping (anchor §5.3). Two per-item maps, rebuilt fresh each tick
        # from this forge snapshot (so items gone from GitHub are pruned) and persisted only if they
        # changed (a non-version-bumping write):
        #   * ``shadow``  — the last SYNCED forge value (where native and GitHub last AGREED). The
        #     baseline the reconcile compares against.
        #   * ``pending`` — a divergent forge value seen on the PREVIOUS tick, awaiting a second
        #     confirming tick before it is adopted (the debounce candidate).
        # A GitHub→native adoption fires ONLY when native sits at the synced baseline AND the SAME
        # divergent forge value is seen on two consecutive ticks. That two-tick confirmation is what
        # makes a self-mirror echo (incl. an A→B→A bounce, where GitHub transiently replays an
        # intermediate value of our own mirror writes) indistinguishable-yet-harmless: the transient
        # value never persists for two ticks once native has settled, so the card is never reverted.
        shadow: dict[str, str] = doc.get("shadow", {})
        pending: dict[str, str] = doc.get("pending", {})
        new_shadow: dict[str, str] = {}
        new_pending: dict[str, str] = {}

        tickets: list[Ticket] = []
        for ft in forge_snap.tickets:
            col_key = placement.get(ft.item_id)
            # Map the forge Status display NAME → native column key (hybrid drift detection).
            forge_key = self._key_for_name.get(ft.column_key, ft.column_key)
            if col_key is None:
                # First-sight: register at entry column, emit there.
                if entry_col:
                    try:
                        self._store.place_card(ft.item_id, entry_col)
                        col_key = entry_col
                    except Exception:  # noqa: BLE001 — one bad write must not abort the whole tick
                        # A store write failure (disk full, lock, transient corruption) for ONE
                        # first-sight card must not take down the entire snapshot. Log loud and fall
                        # back to the forge column for this tick; re-register next tick.
                        logger.error(
                            "anchor snapshot: failed to register %s at entry column %r; "
                            "using forge column this tick",
                            ft.item_id,
                            entry_col,
                            exc_info=True,
                        )
                        col_key = ft.column_key
                else:
                    # Misconfiguration: no native columns → cannot register. Fall back to GitHub's
                    # Status (NOT authoritative under native, §4.5) but make it LOUD — a silent
                    # revert to forge placement would mask an empty/broken columns.yml.
                    logger.error(
                        "anchor snapshot: native backend has no columns; falling back to GitHub "
                        "Status for %s — check columns.yml or run 'kanban board import'",
                        ft.item_id,
                    )
                    col_key = ft.column_key
                # Seed the shadow to the forge value; first contact NEVER adopts.
                new_shadow[ft.item_id] = forge_key
            elif self._hybrid:
                # Bidirectional reconcile with two-tick debounce (anchor §5.3).
                synced = shadow.get(ft.item_id)
                cand = pending.get(ft.item_id)
                if synced is None:
                    # First time we track this already-placed item: seed the baseline, never adopt.
                    new_shadow[ft.item_id] = forge_key
                elif forge_key == col_key:
                    # Native and forge agree → settled. Advance the baseline, drop any pending
                    # candidate (the divergence is gone — e.g. our mirror write reached GitHub).
                    new_shadow[ft.item_id] = forge_key
                elif col_key == synced:
                    # Native is at the synced baseline and the forge value diverged → this is a
                    # candidate external GitHub move (not a native move in flight).
                    if cand == forge_key:
                        # The SAME divergent value confirmed on two consecutive ticks → adopt it.
                        if forge_key in self._columns:
                            try:
                                self._store.place_card(ft.item_id, forge_key)
                                col_key = forge_key
                                new_shadow[ft.item_id] = forge_key
                            except Exception:  # noqa: BLE001 — one bad write must not abort the tick
                                logger.error(
                                    "anchor hybrid: failed to reconcile GitHub move of %s → %r",
                                    ft.item_id,
                                    forge_key,
                                    exc_info=True,
                                )
                                # Keep the baseline and the candidate so the next tick retries.
                                new_shadow[ft.item_id] = synced
                                new_pending[ft.item_id] = forge_key
                        else:
                            # Moved on GitHub into a Status with no matching native column
                            # (columns.yml drift). Cannot adopt — make it LOUD rather than silently
                            # swallow the GitHub move. Keep the baseline (do not re-arm the candidate).
                            logger.warning(
                                "anchor hybrid: GitHub move of %s to unknown Status %r ignored — "
                                "not a native column; reconcile columns.yml or run "
                                "'kanban board import'",
                                ft.item_id,
                                forge_key,
                            )
                            new_shadow[ft.item_id] = synced
                    else:
                        # First sighting of this divergence → debounce one tick before adopting. This
                        # is what neutralises a self-mirror echo / A→B→A bounce: a transient forge
                        # value that does not persist into the next tick is never adopted.
                        new_pending[ft.item_id] = forge_key
                        new_shadow[ft.item_id] = synced
                else:
                    # Native has moved away from the synced baseline (a native move whose mirror has
                    # not yet reached GitHub, or a genuine both-sides conflict). NATIVE is the
                    # placement authority: ignore the forge value, hold the baseline, drop any pending
                    # candidate. The baseline advances once GitHub catches up (the settled branch).
                    new_shadow[ft.item_id] = synced
            else:
                # Non-hybrid: track the forge value for observability only — never persisted, never
                # adopted (GitHub drift is reconciled only by an explicit 'kanban board import').
                new_shadow[ft.item_id] = forge_key
            tickets.append(
                Ticket(
                    item_id=ft.item_id,
                    issue_number=ft.issue_number,
                    title=ft.title,
                    column_key=col_key,
                    body=ft.body,
                )
            )

        # Persist the refreshed bookkeeping (hybrid only) iff it changed — no version bump.
        # Fail-soft like the per-item writes: a write hiccup must not abort the whole tick (it
        # self-corrects next tick; an adopted move already bumped the version via place_card).
        if self._hybrid and (new_shadow != shadow or new_pending != pending):
            try:
                self._store.set_sync_state(new_shadow, new_pending)
            except Exception:  # noqa: BLE001 — bookkeeping write; never abort the tick
                logger.error("anchor hybrid: failed to persist forge sync state", exc_info=True)
        # Observability: a placed item absent from the forge snapshot is omitted this tick. The
        # store KEEPS its placement (no deletion here), so it reappears on the next complete forge
        # snapshot — but a partial/truncated forge read could omit many at once, so LOG it rather
        # than let cards silently vanish from the board (un-debuggable "my board lost cards").
        forge_ids = {ft.item_id for ft in forge_snap.tickets}
        omitted = [iid for iid in placement if iid not in forge_ids]
        if omitted:
            logger.warning(
                "anchor snapshot: %d placed item(s) absent from the forge snapshot, omitted this "
                "tick (placement retained in the store): %s",
                len(omitted),
                omitted,
            )
        return BoardSnapshot(tickets=tuple(tickets), fetched_at=time.time())

    # ------------------------------------------------------------------
    # BoardReader — delegated to forge
    # ------------------------------------------------------------------

    def issue_state(self, number: int) -> bool:
        """Delegate to forge — open/closed is GitHub's (anchor §4.3).

        Args:
            number: The issue number whose open/closed state to probe.

        Returns:
            ``True`` when the issue is closed/merged; ``False`` otherwise.
        """
        return self._forge.issue_state(number)  # type: ignore[no-any-return]

    def issue_context(self, number: int) -> IssueContext:
        """Delegate to forge — body/comments are GitHub's (anchor §4.3).

        Args:
            number: The GitHub issue number whose rich context to fetch.

        Returns:
            An ``IssueContext`` from the forge client.
        """
        return self._forge.issue_context(number)  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # BoardWriter — overridden
    # ------------------------------------------------------------------

    def move_card(self, item_id: str, column_key: str) -> None:
        """Write native placement (tail append) and optionally mirror to GitHub (anchor §5).

        Args:
            item_id: The ``ProjectV2Item`` node id to move.
            column_key: The destination column key.

        Raises:
            ValueError: Unknown ``column_key`` (propagated from the native store; the mirror write
                is fail-soft and never raises).
        """
        self._store.place_card(item_id, column_key)
        if self._mirror is not None:
            try:
                display_name = self._option_name_for_key(column_key)
                self._mirror.move_card(item_id, display_name)
            except Exception:  # noqa: BLE001
                # Mirror failure is observability, not a board-authority failure (§5.2).
                logger.warning(
                    "anchor mirror: failed to mirror move %s → %s to GitHub",
                    item_id,
                    column_key,
                    exc_info=True,
                )

    # ------------------------------------------------------------------
    # BoardWriter — delegated to forge
    # ------------------------------------------------------------------

    def comment(self, issue_number: int, body: str) -> None:
        """Delegate to forge (anchor §4.3).

        Args:
            issue_number: The GitHub issue number to comment on.
            body: The markdown comment body.
        """
        self._forge.comment(issue_number, body)

    def list_issue_comments(self, issue_number: int) -> list[CommentRef]:
        """Delegate to forge (anchor §4.3).

        Args:
            issue_number: The GitHub issue number whose comments to list.

        Returns:
            Comment refs from the forge client.
        """
        return self._forge.list_issue_comments(issue_number)  # type: ignore[no-any-return]

    def update_comment(self, comment_id: int, body: str) -> None:
        """Delegate to forge (anchor §4.3).

        Args:
            comment_id: The integer REST comment id to edit.
            body: The new markdown comment body.
        """
        self._forge.update_comment(comment_id, body)

    # ------------------------------------------------------------------
    # BoardOrdering — native only, NOT mirrored
    # ------------------------------------------------------------------

    def reorder_column(
        self,
        column_key: str,
        ordered_item_ids: list[str],
        *,
        if_version: int | None = None,
    ) -> int:
        """Delegate to the native store — order is NEVER mirrored (anchor §4.6).

        Args:
            column_key: The column whose order to set.
            ordered_item_ids: The new full ordered item id list.
            if_version: Optimistic-concurrency precondition.

        Returns:
            The new store version.

        Raises:
            ValueError: Unknown column; unknown/duplicate/missing item id; stale ``if_version``
                (a :class:`~kanbanmate.adapters.store.fs_board.VersionConflict`).
        """
        return self._store.reorder_column(column_key, ordered_item_ids, if_version=if_version)

    def place_card(
        self,
        item_id: str,
        column_key: str,
        index: int | None = None,
        *,
        if_version: int | None = None,
    ) -> int:
        """Place card at an explicit ``(column, index)`` — native only (anchor §4.6).

        Args:
            item_id: The item to place.
            column_key: The destination column key.
            index: Position within the column; ``None`` appends.
            if_version: Optimistic-concurrency precondition.

        Returns:
            The new store version.

        Raises:
            ValueError: Unknown ``column_key``; out-of-range ``index``; stale ``if_version``
                (a :class:`~kanbanmate.adapters.store.fs_board.VersionConflict`).
        """
        return self._store.place_card(item_id, column_key, index, if_version=if_version)
