"""One-shot board import: seed the native store from a live GitHub snapshot (anchor §8).

Idempotent: a re-run reconciles ``placement`` against the live GitHub Status and
preserves any existing native ``order`` for cards still in the same column (only
newly-seen cards are appended to their column tail). ``--dry-run`` computes the
result without writing.

Layering: ``app`` — may import ``adapters`` and ``core``.
"""

from __future__ import annotations

from typing import Any

from kanbanmate.adapters.store.fs_board import FsBoardStateStore, seed_board


def import_board(
    forge: Any,
    store: FsBoardStateStore,
    columns: list[str],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Seed the native board store from the live GitHub Projects v2 snapshot (anchor §8).

    1. Fetch the live snapshot from ``forge``.
    2. Build ``placement`` from each ticket's current GitHub Status ``column_key``.
    3. Build ``order``: for each column, append items in GitHub board (POSITION) page order
       (the snapshot's ``board_items`` query carries no ``orderBy``, so items arrive in GitHub's
       default POSITION order — a deterministic initial order). For a re-run, preserve existing
       native order for items still in the same column; append newly-seen items to the column tail.
    4. Write atomically bumping the store's single monotonic ``version`` by one
       (``existing_version + 1``) — ``import`` is a version-bumping mutating write like
       ``move_card`` / ``reorder_column`` (anchor §6.2), so the combined ``cheap_probe``
       (anchor §4.4) always observes the import as a change.
    5. On ``dry_run=True``, skip the write and return the computed data.

    Args:
        forge: A ``BoardReader`` (``GithubClient`` or a fake for tests) for ``snapshot()``.
        store: The native board store to seed.
        columns: Ordered column key list (from ``columns.yml`` order).
        dry_run: When ``True``, compute but do not write; return the data.

    Returns:
        ``{"version": int, "dry_run": bool, "summary": {"total": int, "per_column": {col: count}}}``.
    """
    snap = forge.snapshot()
    existing = store.load()
    existing_version: int = existing.get("version", 0)
    existing_order: dict[str, list[str]] = existing.get("order", {})
    existing_placement: dict[str, str] = existing.get("placement", {})

    # ``import`` bumps the single monotonic store version (anchor §6.2) so a re-run is
    # strictly greater than any intervening native move/reorder — never equal (which would
    # make cheap_probe miss the import, anchor §4.4).
    new_version = existing_version + 1

    # Build placement map from the live GitHub snapshot.
    placement: dict[str, str] = {}
    for ticket in snap.tickets:
        col = ticket.column_key if ticket.column_key in columns else (columns[0] if columns else "")
        placement[ticket.item_id] = col

    # Build order: for each column, preserve existing native order for items still there,
    # then append newly-seen items (items in the live snapshot that are newly assigned to
    # this column or didn't exist in the native store before).
    order: dict[str, list[str]] = {col: [] for col in columns}
    for col in columns:
        # Existing order entries that are still in this column (stable order preserved).
        still_here = [iid for iid in existing_order.get(col, []) if placement.get(iid) == col]
        # Newly-seen items assigned to this column (in snapshot page order = GitHub POSITION order).
        existing_set = set(existing_placement.keys())
        newly_seen = [
            ticket.item_id
            for ticket in snap.tickets
            if ticket.item_id not in existing_set and placement.get(ticket.item_id) == col
        ]
        # Re-run: items that moved INTO this column from another.
        moved_in = [
            iid
            for iid, assigned_col in placement.items()
            if assigned_col == col and iid not in still_here and iid not in newly_seen
        ]
        order[col] = still_here + newly_seen + moved_in

    if not dry_run:
        seed_board(store, columns=columns, placement=placement, order=order, version=new_version)

    per_column = {col: len(order[col]) for col in columns}
    return {
        "version": new_version,
        "dry_run": dry_run,
        "summary": {
            "total": len(placement),
            "per_column": per_column,
        },
    }
