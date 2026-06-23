"""Tests for NativeBoardBackend — import check, snapshot JOIN, combined probe, move+mirror (anchor §12.2-4)."""

from __future__ import annotations

import pathlib
from unittest.mock import MagicMock

import pytest

from kanbanmate.adapters.board.native import NativeBoardBackend
from kanbanmate.adapters.store.fs_board import FsBoardStateStore, seed_board
from kanbanmate.core.domain import BoardSnapshot, Ticket


def test_board_ordering_importable_from_ports_board() -> None:
    from kanbanmate.ports.board import BoardOrdering  # noqa: F401


def _forge_snapshot(*tickets: Ticket) -> MagicMock:
    """Return a fake forge client whose snapshot() returns the given tickets."""
    forge = MagicMock()
    forge.snapshot.return_value = BoardSnapshot(tickets=tuple(tickets), fetched_at=0.0)
    return forge


def _ticket(item_id: str, col: str = "Backlog") -> Ticket:
    return Ticket(item_id=item_id, issue_number=1, title="T", column_key=col, body="")


COLUMNS = [
    "Backlog",
    "Brainstorming",
    "Spec",
    "Plan",
    "ReadyToDev",
    "PrepareFeature",
    "InProgress",
    "PRCI",
    "Review",
    "Merge",
    "Done",
    "Cancel",
    "Blocked",
]


def _make_backend(
    tmp_path: pathlib.Path,
    forge: MagicMock,
    mirror: MagicMock | None = None,
) -> NativeBoardBackend:
    store = FsBoardStateStore(tmp_path)
    seed_board(
        store,
        columns=COLUMNS,
        placement={"item1": "Backlog"},
        order={"Backlog": ["item1"], **{c: [] for c in COLUMNS if c != "Backlog"}},
    )
    return NativeBoardBackend(
        forge=forge,
        store=store,
        columns=COLUMNS,
        option_name_for_key=lambda key: key,  # identity for tests
        mirror=mirror,
    )


# ---------------------------------------------------------------------------
# §12.2 — snapshot JOIN
# ---------------------------------------------------------------------------


def test_snapshot_uses_native_column_not_forge(tmp_path: pathlib.Path) -> None:
    """The snapshot uses the NATIVE column_key, not the forge's GitHub Status."""
    forge = _forge_snapshot(
        # forge says "InProgress" but native store has "Backlog"
        Ticket(item_id="item1", issue_number=1, title="T", column_key="InProgress", body="")
    )
    backend = _make_backend(tmp_path, forge)
    snap = backend.snapshot()
    assert len(snap.tickets) == 1
    assert snap.tickets[0].column_key == "Backlog", "native placement must win over forge Status"


def test_snapshot_new_issue_lands_in_entry_column(tmp_path: pathlib.Path) -> None:
    """A forge issue absent from the native store is registered at columns[0] = 'Backlog'."""
    forge = _forge_snapshot(
        _ticket("item1"),  # already in store
        _ticket("brand_new"),  # NOT in store
    )
    backend = _make_backend(tmp_path, forge)
    snap = backend.snapshot()
    by_id = {t.item_id: t for t in snap.tickets}
    assert "brand_new" in by_id
    assert by_id["brand_new"].column_key == "Backlog", "new issue must land at entry column"


def test_snapshot_store_only_item_dropped(tmp_path: pathlib.Path) -> None:
    """An item in the native store but absent from GitHub is dropped from the snapshot."""
    # Forge only returns one ticket; native store has "item1" but forge has "item2" only.
    store = FsBoardStateStore(tmp_path)
    seed_board(
        store,
        columns=COLUMNS,
        placement={"item1": "Backlog"},  # in store, NOT in forge
        order={"Backlog": ["item1"], **{c: [] for c in COLUMNS if c != "Backlog"}},
    )
    forge = _forge_snapshot(_ticket("item2", "Done"))  # only item2 in forge
    backend = NativeBoardBackend(
        forge=forge,
        store=store,
        columns=COLUMNS,
        option_name_for_key=lambda k: k,
    )
    snap = backend.snapshot()
    item_ids = {t.item_id for t in snap.tickets}
    assert "item1" not in item_ids, "store-only item must be dropped (GC'd lazily)"
    assert "item2" in item_ids


# ---------------------------------------------------------------------------
# §12.3 — combined cheap_probe
# ---------------------------------------------------------------------------


def test_cheap_probe_changes_on_native_move(tmp_path: pathlib.Path) -> None:
    """A native move (store version bump) changes the probe; forge probe unchanged."""
    forge = MagicMock()
    forge.cheap_probe.return_value = "frozen-forge-token"
    forge.snapshot.return_value = BoardSnapshot(tickets=(), fetched_at=0.0)

    store = FsBoardStateStore(tmp_path)
    seed_board(
        store,
        columns=COLUMNS,
        placement={"item1": "Backlog"},
        order={"Backlog": ["item1"], **{c: [] for c in COLUMNS if c != "Backlog"}},
    )
    backend = NativeBoardBackend(
        forge=forge,
        store=store,
        columns=COLUMNS,
        option_name_for_key=lambda k: k,
    )
    probe_before = backend.cheap_probe()
    store.place_card("item1", "InProgress")  # native move
    probe_after = backend.cheap_probe()
    assert probe_before != probe_after, "native move must change the combined probe"
    assert "frozen-forge-token" in probe_after


def test_cheap_probe_changes_on_forge_change(tmp_path: pathlib.Path) -> None:
    """A forge change (new/closed/edited issue) changes the probe even when the store is frozen.

    Guards the trigger-inversion top risk (DESIGN §15): a refactor that dropped the forge half of
    the combined token would silently stop waking the daemon on GitHub-side issue create/close.
    """
    forge = MagicMock()
    forge.snapshot.return_value = BoardSnapshot(tickets=(), fetched_at=0.0)
    # Store untouched between the two probes; only the forge token moves.
    forge.cheap_probe.side_effect = ["forge-token-A", "forge-token-B"]

    store = FsBoardStateStore(tmp_path)
    seed_board(
        store,
        columns=COLUMNS,
        placement={"item1": "Backlog"},
        order={"Backlog": ["item1"], **{c: [] for c in COLUMNS if c != "Backlog"}},
    )
    backend = NativeBoardBackend(
        forge=forge,
        store=store,
        columns=COLUMNS,
        option_name_for_key=lambda k: k,
    )
    probe_before = backend.cheap_probe()
    probe_after = backend.cheap_probe()
    assert probe_before != probe_after, "a forge change alone must change the combined probe"


def test_snapshot_first_sight_registration_is_idempotent(tmp_path: pathlib.Path) -> None:
    """A second snapshot of the same forge set must NOT re-register / re-bump the store version.

    First-sight registration writes (version bump) the first time only; a snapshot that re-registered
    every tick would bump the version on every poll → cheap_probe perpetually "changed" → busy-loop.
    """
    forge = _forge_snapshot(_ticket("brand_new"))
    backend = _make_backend(tmp_path, forge)

    backend.snapshot()
    version_after_first = backend._store.load()["version"]
    backend.snapshot()
    version_after_second = backend._store.load()["version"]

    assert version_after_second == version_after_first, (
        "re-snapshotting a known issue must not bump the store version"
    )
    # And the registration is durable: the item stays at the entry column.
    assert backend._store.load()["placement"]["brand_new"] == "Backlog"


def test_cheap_probe_stable_when_nothing_changes(tmp_path: pathlib.Path) -> None:
    """When neither store nor forge changes, the combined probe is stable."""
    forge = MagicMock()
    forge.cheap_probe.return_value = "stable"
    forge.snapshot.return_value = BoardSnapshot(tickets=(), fetched_at=0.0)

    store = FsBoardStateStore(tmp_path)
    seed_board(store, columns=COLUMNS, placement={}, order={c: [] for c in COLUMNS})
    backend = NativeBoardBackend(
        forge=forge,
        store=store,
        columns=COLUMNS,
        option_name_for_key=lambda k: k,
    )
    assert backend.cheap_probe() == backend.cheap_probe()


# ---------------------------------------------------------------------------
# §12.4 — move_card + mirror
# ---------------------------------------------------------------------------


def test_move_card_writes_native_and_mirrors(tmp_path: pathlib.Path) -> None:
    """move_card writes native placement AND calls forge.move_card with the option NAME."""
    mirror = MagicMock()
    forge = _forge_snapshot(_ticket("item1"))
    backend = _make_backend(tmp_path, forge, mirror=mirror)

    backend.move_card("item1", "InProgress")

    doc = backend._store.load()
    assert doc["placement"]["item1"] == "InProgress"
    # Mirror must receive the display name (identity for this test)
    mirror.move_card.assert_called_once_with("item1", "InProgress")


def test_move_card_accepts_display_name_when_key_differs(tmp_path: pathlib.Path) -> None:
    """move_card resolves a Status display NAME → column KEY (prod #55 'Prepare feature' bug).

    The engine's intent path passes the Column NAME (``to_column.name``). For a column whose name
    differs from its key (``PrepareFeature`` / 'Prepare feature'), the native store — keyed by KEY —
    must resolve the name; passing it raw raised 'unknown column_key' and the move-intent failed with
    'internal error processing intent'.
    """
    mirror = MagicMock()
    forge = _forge_snapshot(_ticket("item1"))
    store = FsBoardStateStore(tmp_path)
    seed_board(
        store,
        columns=COLUMNS,
        placement={"item1": "Backlog"},
        order={"Backlog": ["item1"], **{c: [] for c in COLUMNS if c != "Backlog"}},
    )
    # Names differ from keys for the multi-word columns (mirrors a real columns.yml).
    names = {"ReadyToDev": "Ready to dev", "PrepareFeature": "Prepare feature"}
    backend = NativeBoardBackend(
        forge=forge,
        store=store,
        columns=COLUMNS,
        option_name_for_key=lambda key: names.get(key, key),
        mirror=mirror,
    )

    backend.move_card("item1", "Prepare feature")  # the DISPLAY NAME — must not raise

    assert backend._store.load()["placement"]["item1"] == "PrepareFeature"
    # The mirror still receives the GitHub display name.
    mirror.move_card.assert_called_once_with("item1", "Prepare feature")


def test_move_card_mirror_error_swallowed_native_lands(tmp_path: pathlib.Path) -> None:
    """A mirror write error is swallowed; native placement is already correct (§5.2)."""
    mirror = MagicMock()
    mirror.move_card.side_effect = RuntimeError("GitHub down")

    forge = _forge_snapshot(_ticket("item1"))
    backend = _make_backend(tmp_path, forge, mirror=mirror)

    backend.move_card("item1", "Done")  # must NOT raise

    doc = backend._store.load()
    assert doc["placement"]["item1"] == "Done", "native must be updated despite mirror failure"


def test_reorder_does_not_call_mirror(tmp_path: pathlib.Path) -> None:
    """reorder_column is native-only; the mirror must never be called (anchor §4.6)."""
    mirror = MagicMock()
    forge = MagicMock()
    store = FsBoardStateStore(tmp_path)
    seed_board(
        store,
        columns=["Backlog", "InProgress"],
        placement={"a": "Backlog", "b": "Backlog"},
        order={"Backlog": ["a", "b"], "InProgress": []},
    )
    backend = NativeBoardBackend(
        forge=forge,
        store=store,
        columns=["Backlog", "InProgress"],
        option_name_for_key=lambda k: k,
        mirror=mirror,
    )
    backend.reorder_column("Backlog", ["b", "a"])
    mirror.move_card.assert_not_called()


# ---------------------------------------------------------------------------
# Robustness (review hardening): probe/snapshot must not be hostage to the forge
# ---------------------------------------------------------------------------


def test_cheap_probe_survives_forge_failure_and_still_tracks_native(
    tmp_path: pathlib.Path,
) -> None:
    """A forge cheap_probe failure must NOT mask a native change (H3).

    The native store is the placement authority — a move via the HTTP API bumps store_version and
    MUST still wake the tick even when GitHub is unreachable. The forge half degrades to a sentinel.
    """
    forge = MagicMock()
    forge.cheap_probe.side_effect = RuntimeError("GitHub unreachable")
    forge.snapshot.return_value = BoardSnapshot(tickets=(), fetched_at=0.0)

    store = FsBoardStateStore(tmp_path)
    seed_board(
        store,
        columns=COLUMNS,
        placement={"item1": "Backlog"},
        order={"Backlog": ["item1"], **{c: [] for c in COLUMNS if c != "Backlog"}},
    )
    backend = NativeBoardBackend(
        forge=forge, store=store, columns=COLUMNS, option_name_for_key=lambda k: k
    )

    probe_before = backend.cheap_probe()  # must NOT raise despite the forge error
    assert probe_before.endswith(":?"), "forge failure → native-only sentinel token"
    store.place_card("item1", "InProgress")  # a purely native change during the forge outage
    probe_after = backend.cheap_probe()
    assert probe_before != probe_after, "native change must still be detected during a forge outage"


def test_snapshot_first_sight_write_failure_falls_back_to_forge_column(
    tmp_path: pathlib.Path,
) -> None:
    """If registering a first-sight card raises, the snapshot uses the forge column, not abort (H2)."""
    forge = _forge_snapshot(_ticket("brand_new", col="Spec"))  # not in store
    backend = _make_backend(tmp_path, forge)

    # Force the first-sight registration write to fail.
    def _boom(*_args: object, **_kwargs: object) -> int:
        raise OSError("disk full")

    backend._store.place_card = _boom  # type: ignore[method-assign]

    snap = backend.snapshot()  # must NOT raise
    by_id = {t.item_id: t for t in snap.tickets}
    assert by_id["brand_new"].column_key == "Spec", (
        "a failed first-sight write must fall back to the forge column for this tick, not abort"
    )


def test_snapshot_omitted_store_item_is_logged(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A placed item absent from the forge snapshot is omitted AND logged (C1 — observable, not silent)."""
    import logging

    store = FsBoardStateStore(tmp_path)
    seed_board(
        store,
        columns=COLUMNS,
        placement={"gone": "Backlog"},  # in store, absent from forge
        order={"Backlog": ["gone"], **{c: [] for c in COLUMNS if c != "Backlog"}},
    )
    forge = _forge_snapshot(_ticket("present", "Done"))
    backend = NativeBoardBackend(
        forge=forge, store=store, columns=COLUMNS, option_name_for_key=lambda k: k
    )
    with caplog.at_level(logging.WARNING):
        snap = backend.snapshot()
    assert {t.item_id for t in snap.tickets} == {"present"}
    assert "gone" in caplog.text, "the omitted item must be logged (observable lazy GC)"
    # The store retains the placement (no deletion) — it reappears on a complete forge snapshot.
    assert backend._store.load()["placement"]["gone"] == "Backlog"


# ---------------------------------------------------------------------------
# board-sync (hybrid): bidirectional reconcile GitHub → native
# ---------------------------------------------------------------------------


def _hybrid_backend(tmp_path: pathlib.Path, forge: MagicMock) -> NativeBoardBackend:
    store = FsBoardStateStore(tmp_path)
    seed_board(
        store,
        columns=COLUMNS,
        placement={"item1": "Backlog"},
        order={"Backlog": ["item1"], **{c: [] for c in COLUMNS if c != "Backlog"}},
    )
    return NativeBoardBackend(
        forge=forge,
        store=store,
        columns=COLUMNS,
        option_name_for_key=lambda k: k,  # identity → forge Status name == column key
        mirror=MagicMock(),
        hybrid=True,
    )


def test_hybrid_reconciles_github_move_into_native(tmp_path: pathlib.Path) -> None:
    """In hybrid mode, a move made on GitHub (forge Status drift) is adopted after a confirming tick.

    The two-tick debounce means a genuine external move is adopted on the SECOND consecutive tick
    that shows the same divergent value (the first tick only arms the pending candidate).
    """
    forge = MagicMock()
    # Tick 1: forge agrees with native (Backlog) → seeds the shadow, no adoption.
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Backlog"),), fetched_at=0.0
    )
    backend = _hybrid_backend(tmp_path, forge)
    snap1 = backend.snapshot()
    assert snap1.tickets[0].column_key == "Backlog"

    # Tick 2: the operator moved the card to "Review" ON GitHub → forge Status drifts. First sighting
    # of the divergence only arms the debounce candidate — native is NOT moved yet.
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Review"),), fetched_at=0.0
    )
    snap2 = backend.snapshot()
    assert snap2.tickets[0].column_key == "Backlog", "first divergent tick only debounces"
    assert backend._store.load()["placement"]["item1"] == "Backlog"

    # Tick 3: the SAME divergent value persists → confirmed external move, adopted into native.
    snap3 = backend.snapshot()
    assert snap3.tickets[0].column_key == "Review", "confirmed GitHub move must be reconciled"
    assert backend._store.load()["placement"]["item1"] == "Review", "native store must be updated"


def test_hybrid_native_move_not_reverted_by_mirror_lag(tmp_path: pathlib.Path) -> None:
    """A native move must NOT be reverted while the GitHub mirror is still catching up.

    The shadow holds the PREVIOUS forge value, so while GitHub still shows the old Status the snapshot
    sees forge == shadow (no drift) → native authority wins.
    """
    forge = MagicMock()
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Backlog"),), fetched_at=0.0
    )
    backend = _hybrid_backend(tmp_path, forge)
    backend.snapshot()  # seed shadow = Backlog

    # Operator moves the card in KanbanMate (native → Done); GitHub mirror not yet applied.
    backend._store.place_card("item1", "Done")
    # Next snapshot: forge STILL shows Backlog (mirror lag) == shadow → no drift → native wins.
    snap = backend.snapshot()
    assert snap.tickets[0].column_key == "Done", "native move must survive the mirror-lag window"
    assert backend._store.load()["placement"]["item1"] == "Done"


def test_native_mode_ignores_github_move(tmp_path: pathlib.Path) -> None:
    """In one-way native mode (hybrid=False), a GitHub Status change is NOT reconciled."""
    forge = MagicMock()
    store = FsBoardStateStore(tmp_path)
    seed_board(
        store,
        columns=COLUMNS,
        placement={"item1": "Backlog"},
        order={"Backlog": ["item1"], **{c: [] for c in COLUMNS if c != "Backlog"}},
    )
    backend = NativeBoardBackend(
        forge=forge, store=store, columns=COLUMNS, option_name_for_key=lambda k: k, hybrid=False
    )
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Review"),), fetched_at=0.0
    )
    snap = backend.snapshot()
    assert snap.tickets[0].column_key == "Backlog", "native (one-way) ignores GitHub Status"


def test_set_sync_state_does_not_bump_version(tmp_path: pathlib.Path) -> None:
    """Persisting the sync state is bookkeeping — it must NOT bump the store version (no probe churn)."""
    store = FsBoardStateStore(tmp_path)
    seed_board(store, columns=COLUMNS, placement={}, order={c: [] for c in COLUMNS})
    v0 = store.load()["version"]
    store.set_sync_state({"item1": "Backlog"}, {"item1": "Review"})
    assert store.load()["version"] == v0, "set_sync_state must not bump version"
    assert store.load()["shadow"] == {"item1": "Backlog"}
    assert store.load()["pending"] == {"item1": "Review"}


def test_hybrid_bounce_back_not_falsely_adopted(tmp_path: pathlib.Path) -> None:
    """REGRESSION (Cycle 2 HIGH): an A→B→A native bounce must not be reverted by a mirror echo of B.

    Net native move is a no-op (Backlog→Review→Backlog), but the GitHub mirror transiently replays
    the intermediate value (Review). With a single-valued shadow and 1-tick adoption, the daemon
    could mistake that transient echo for an external move and revert the card to Review. The
    two-tick debounce defeats it: the transient value does not persist into the next tick, so it is
    never adopted.
    """
    forge = MagicMock()
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Backlog"),), fetched_at=0.0
    )
    backend = _hybrid_backend(tmp_path, forge)
    backend.snapshot()  # seed shadow=Backlog (settled)

    # Operator bounces the card on native: Backlog→Review→Backlog. Net placement = Backlog.
    backend._store.place_card("item1", "Review")
    backend._store.place_card("item1", "Backlog")  # native authority back at Backlog

    # GitHub transiently echoes the intermediate mirrored value (Review) for ONE tick.
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Review"),), fetched_at=0.0
    )
    snap = backend.snapshot()
    assert snap.tickets[0].column_key == "Backlog", "a transient mirror echo must NOT be adopted"
    assert backend._store.load()["placement"]["item1"] == "Backlog"

    # GitHub catches up to the net value (Backlog) → settled, still Backlog. Echo never adopted.
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Backlog"),), fetched_at=0.0
    )
    assert backend.snapshot().tickets[0].column_key == "Backlog"


def test_hybrid_multi_move_not_reverted_by_mirror_echo(tmp_path: pathlib.Path) -> None:
    """REGRESSION: two native moves in flight must not be reverted by GitHub echoing an intermediate.

    GitHub replaying an intermediate column of our OWN mirror writes (Review) while native authority
    is already at Done must not revert the card. Native-moved-away-from-baseline holds native.
    """
    forge = MagicMock()
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Backlog"),), fetched_at=0.0
    )
    backend = _hybrid_backend(tmp_path, forge)
    backend.snapshot()  # seed shadow=Backlog

    # Operator makes TWO native moves before GitHub catches up: Backlog→Review→Done.
    backend._store.place_card("item1", "Review")
    backend._store.place_card("item1", "Done")  # native authority = Done

    # GitHub is still replaying the FIRST mirrored value (Review) — must NOT revert Done→Review.
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Review"),), fetched_at=0.0
    )
    snap = backend.snapshot()
    assert snap.tickets[0].column_key == "Done", "mirror echo of an intermediate must not revert"
    assert backend._store.load()["placement"]["item1"] == "Done"

    # GitHub finally catches up to Done → settled, still Done.
    forge.snapshot.return_value = BoardSnapshot(tickets=(_ticket("item1", "Done"),), fetched_at=0.0)
    assert backend.snapshot().tickets[0].column_key == "Done"


def test_hybrid_arming_candidate_bumps_probe_self_wake(tmp_path: pathlib.Path) -> None:
    """P1: arming a fresh debounce candidate bumps the store version so the next cheap_probe differs.

    Without the self-wake bump, an external GitHub move that moves the forge probe exactly once arms
    the pending candidate on tick 1, then the probe is stable → the daemon never re-snapshots → the
    2-tick debounce never reaches its confirming tick (the probe-starves-debounce stall). The arming
    write must therefore bump the version so the combined probe changes and the next tick re-evaluates.
    """
    forge = MagicMock()
    forge.cheap_probe.return_value = "frozen-forge"  # forge token frozen → only the version moves
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Backlog"),), fetched_at=0.0
    )
    backend = _hybrid_backend(tmp_path, forge)
    backend.snapshot()  # seed shadow=Backlog (settled), no candidate

    probe_settled = backend.cheap_probe()
    # External GitHub move: forge now shows Review (native still Backlog) → ARMS the candidate.
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Review"),), fetched_at=0.0
    )
    backend.snapshot()
    probe_after_arm = backend.cheap_probe()
    assert probe_after_arm != probe_settled, (
        "arming a fresh candidate must change the combined probe (P1 self-wake)"
    )


def test_hybrid_settled_tick_does_not_bump_probe(tmp_path: pathlib.Path) -> None:
    """P1 guard: a settled tick (no fresh candidate armed) must NOT bump the probe (no busy-loop).

    The self-wake bump is gated to candidate-arming only; a tick where forge and native agree (or
    re-confirms an existing candidate value) must leave the version untouched so a quiescent hybrid
    board does not churn cheap_probe every poll.
    """
    forge = MagicMock()
    forge.cheap_probe.return_value = "frozen-forge"
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Backlog"),), fetched_at=0.0
    )
    backend = _hybrid_backend(tmp_path, forge)
    backend.snapshot()  # seed shadow

    probe_a = backend.cheap_probe()
    backend.snapshot()  # forge still agrees → settled, nothing armed
    probe_b = backend.cheap_probe()
    assert probe_a == probe_b, "a settled hybrid tick must not bump the probe (no busy-loop)"


def test_hybrid_self_mirror_echo_arms_then_drops_without_false_adoption(
    tmp_path: pathlib.Path,
) -> None:
    """P1 + debounce: the self-wake bump on a transient echo must NOT cause a false adoption.

    A native A→B→A bounce makes GitHub transiently replay the intermediate value (Review). The first
    divergent tick arms the candidate (and bumps the probe — self-wake), but the value does not
    persist into the confirming tick (GitHub catches up to Backlog), so the debounce drops it and the
    card is NEVER adopted to Review. This proves the self-wake does not weaken the echo guard.
    """
    forge = MagicMock()
    forge.cheap_probe.return_value = "frozen-forge"
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Backlog"),), fetched_at=0.0
    )
    backend = _hybrid_backend(tmp_path, forge)
    backend.snapshot()  # seed shadow=Backlog (settled)

    # Native bounce Backlog→Review→Backlog (net Backlog); GitHub echoes the intermediate Review once.
    backend._store.place_card("item1", "Review")
    backend._store.place_card("item1", "Backlog")
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Review"),), fetched_at=0.0
    )
    snap_arm = backend.snapshot()  # arms candidate (bumps probe), but does NOT adopt
    assert snap_arm.tickets[0].column_key == "Backlog"

    # GitHub catches up to the net value (Backlog) → the transient Review never persists → dropped.
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Backlog"),), fetched_at=0.0
    )
    snap_confirm = backend.snapshot()
    assert snap_confirm.tickets[0].column_key == "Backlog", "transient echo must never be adopted"
    assert backend._store.load()["placement"]["item1"] == "Backlog"


def test_hybrid_conflict_native_wins(tmp_path: pathlib.Path) -> None:
    """On a simultaneous conflict (both sides moved since settle), native (the authority) wins."""
    forge = MagicMock()
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Backlog"),), fetched_at=0.0
    )
    backend = _hybrid_backend(tmp_path, forge)
    backend.snapshot()  # seed shadow=Backlog

    backend._store.place_card("item1", "Done")  # native moved (authority)
    # forge ALSO moved externally to Review since settle → conflict.
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Review"),), fetched_at=0.0
    )
    snap = backend.snapshot()
    assert snap.tickets[0].column_key == "Done", "native wins the simultaneous conflict"


def test_hybrid_unknown_github_status_logged_not_adopted(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A GitHub move into a Status with no native column is NOT adopted but IS logged (no silent drop)."""
    import logging

    forge = MagicMock()
    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "Backlog"),), fetched_at=0.0
    )
    backend = _hybrid_backend(tmp_path, forge)
    backend.snapshot()  # seed shadow=Backlog (native quiescent)

    forge.snapshot.return_value = BoardSnapshot(
        tickets=(_ticket("item1", "NoSuchStatus"),), fetched_at=0.0
    )
    # Tick 1 of the divergence only arms the debounce candidate (no warning yet).
    snap_debounce = backend.snapshot()
    assert snap_debounce.tickets[0].column_key == "Backlog"
    # Tick 2: the same unknown Status persists → adoption is ATTEMPTED, found unadoptable, logged.
    with caplog.at_level(logging.WARNING):
        snap = backend.snapshot()
    assert snap.tickets[0].column_key == "Backlog", "unknown Status must NOT be adopted"
    assert "NoSuchStatus" in caplog.text, "an unadoptable GitHub move must be logged, not swallowed"
