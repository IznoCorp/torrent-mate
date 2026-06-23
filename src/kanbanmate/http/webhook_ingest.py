"""External-move ingestion for the ``kanban serve`` webhook receiver (keel step 5 B).

Under the native ONE-WAY backend (keel step 5 A), the local ``board.json`` store is the placement
authority and the daemon mirrors native → GitHub. The GitHub board is the SECONDARY surface
(KanbanMateUI is primary). A drag on the GitHub board is therefore NOT auto-adopted by the daemon's
normal tick — the native snapshot reads placement from ``board.json``, not from GitHub's Status. This
module closes that gap: on a ``projects_v2_item`` event for a registered, native-backed project, it
INGESTS the external Status into ``board.json`` (a first-sighting / re-placement adopt), so the next
daemon tick's ``diff(persisted, snapshot)`` sees the move and fires the launch.

**Echo safety (the own-writes ledger).** The daemon's own native → GitHub mirror writes generate
``projects_v2_item`` events too. Those are SELF-ECHOES and must not be re-adopted. The own-writes
ledger here is the native store's CURRENT placement: the placement is exactly what the daemon last
mirrored to GitHub, so an incoming Status that equals the current native placement is our own echo
and is DROPPED (no write, no false adoption). Only a Status that DIFFERS from the current native
placement (a genuine external drag) — or a first sighting of an unplaced item — is ingested. This is
a SINGLE-tick decision keyed on the durable placement (NOT a 2-tick debounce): the placement is
authoritative the instant the daemon writes it, so a self-echo is recognisable immediately.

**No lost trigger.** After a genuine ingest the caller nudges the daemon, whose interruptible sleep
early-returns and re-snapshots; the diff against the now-updated ``board.json`` fires the launch.

**Flock safety.** The ``board.json`` write goes through :meth:`FsBoardStateStore.place_card`, which
holds the same exclusive advisory ``flock`` the daemon's writes hold — so a concurrent daemon move
and a webhook ingest serialise cleanly (no torn document).

Layering: ``http`` is a top entrypoint (DESIGN §3.2) — it may import ``app`` / ``adapters`` / ``core``.
The payload-parsing helpers are pure; only :func:`ingest_external_move` does I/O (it resolves the
store root + columns and writes ``board.json``). The GitHub payload shape is parsed defensively:
ANY shape mismatch yields a no-op outcome, never a crash (the receiver must never 5xx a webhook).
"""

from __future__ import annotations

import enum
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# The webhook payload's single-select field-type marker. GitHub tags a Status (single-select) field
# value change with this ``field_type``; used as the fallback Status discriminator when the registry
# entry has no recorded ``status_field_node_id`` to match ``field_node_id`` against.
_SINGLE_SELECT_FIELD_TYPE = "single_select"


class IngestOutcome(enum.Enum):
    """The result of an external-move ingestion attempt (for the receiver's log + response).

    Attributes:
        ADOPTED: The external Status differed from the native placement (or first sighting) and was
            written into ``board.json`` — the caller should nudge so the diff fires the launch.
        ECHO_DROPPED: The external Status equalled the current native placement (our own mirror
            echo) — no write was made (echo-safe). The caller still nudges (a harmless no-op diff).
        NO_STATUS: The payload carried no resolvable Status change (not a single-select edit, or a
            different field) — nothing to ingest; the caller falls back to nudge-only (today's path).
        NOT_NATIVE: The project is not native-backed (``board_backend`` ``"github"``) — there is no
            native store to ingest into; the caller falls back to nudge-only (today's path).
        ERROR: A defensive catch — resolution or the store write failed; logged, never raised. The
            caller still nudges so the daemon's safety sweep reconciles.
    """

    ADOPTED = "adopted"
    ECHO_DROPPED = "echo_dropped"
    NO_STATUS = "no_status"
    NOT_NATIVE = "not_native"
    ERROR = "error"


def extract_item_id(payload: dict[str, Any]) -> str | None:
    """Extract the ``ProjectV2Item`` node id from a ``projects_v2_item`` payload (best-effort).

    The native store keys placement by the ``ProjectV2Item`` node id (the same id the forge snapshot
    emits as ``Ticket.item_id``). GitHub carries it as ``projects_v2_item.node_id``.

    Args:
        payload: The decoded webhook JSON body.

    Returns:
        The item node id when present and non-empty, else ``None`` (a malformed shape is a no-op).
    """
    item = payload.get("projects_v2_item")
    if isinstance(item, dict):
        node_id = item.get("node_id")
        if isinstance(node_id, str) and node_id:
            return node_id
    return None


def extract_status_name(payload: dict[str, Any], status_field_node_id: str) -> str | None:
    """Extract the NEW Status option name from a ``projects_v2_item`` field-value change (best-effort).

    GitHub nests a single-select field-value change under ``changes.field_value`` with the new value
    at ``.to.name``. This adopts it ONLY when the changed field is the project's Status field:

    * When ``status_field_node_id`` is set, the change's ``field_node_id`` MUST match it (the precise
      discriminator — a non-Status single-select edit is correctly ignored).
    * When the entry has no recorded ``status_field_node_id`` (``""`` — an old-shaped registry entry),
      fall back to accepting any ``field_type == "single_select"`` change (the board's only
      single-select field is the Status field in the bootstrapped layout).

    Args:
        payload: The decoded webhook JSON body.
        status_field_node_id: The project's Status single-select field node id, or ``""`` when the
            registry entry does not record it (the single-select fallback then applies).

    Returns:
        The new Status option name when this is a Status-field change carrying one, else ``None``
        (any shape mismatch → ``None``, so a non-Status edit / add / archive is a no-op here).
    """
    changes = payload.get("changes")
    if not isinstance(changes, dict):
        return None
    field_value = changes.get("field_value")
    if not isinstance(field_value, dict):
        return None
    # Discriminate the Status field: prefer the exact field-node-id match; fall back to the
    # single-select field-type when the entry has no recorded id (old-shaped registry entry).
    field_node_id = field_value.get("field_node_id")
    field_type = field_value.get("field_type")
    if status_field_node_id:
        if field_node_id != status_field_node_id:
            return None
    elif field_type != _SINGLE_SELECT_FIELD_TYPE:
        return None
    to = field_value.get("to")
    if not isinstance(to, dict):
        # A cleared single-select (``to`` null) has no destination column — nothing to ingest.
        return None
    name = to.get("name")
    return name if isinstance(name, str) and name else None


def _board_store_root(root: Path, entry: Any, *, multi: bool) -> Path:
    """Resolve the per-project ``board.json`` store root (mirrors the daemon wiring).

    The native board store lives at the SAME root the daemon's ``build_deps`` roots it at: the
    per-project sub-root (``<root>/projects/<safe(pid)>``) in a MULTI-project deployment, else the
    bare runtime ``root`` (the N=1 flat layout). Reproduced here so the webhook writes the EXACT
    ``board.json`` the daemon reads — never a divergent path.

    Args:
        root: The runtime root holding ``projects.json`` + (N=1) ``board.json``.
        entry: The resolved registry entry (carries ``project_id``).
        multi: Whether the daemon drives >1 enabled project (the store-layout switch).

    Returns:
        The directory holding this project's ``board.json``.
    """
    from kanbanmate.core.registry_resolve import safe_project_id

    if multi:
        return root / "projects" / safe_project_id(entry.project_id)
    return root


def _name_to_key(entry: Any) -> dict[str, str]:
    """Build the Status display NAME → native column KEY map from the entry's clone ``columns.yml``.

    The webhook payload carries the Status DISPLAY NAME (``changes.field_value.to.name``); the native
    store is keyed by column KEY. The clone's ``columns.yml`` is the source of truth for the name↔key
    mapping (the same file the daemon wiring loads). Read here so the ingest places at the correct
    native column key.

    Args:
        entry: The resolved registry entry (carries ``clone``).

    Returns:
        ``{status_display_name: column_key}`` for the project's columns (empty when the clone has no
        readable ``columns.yml`` — the caller then cannot map the Status and skips the ingest).
    """
    from kanbanmate.cli.init import CLONE_COLUMNS_RELPATH
    from kanbanmate.core.columns import load_columns

    columns_path = Path(entry.clone) / CLONE_COLUMNS_RELPATH
    columns = load_columns(columns_path.read_text(encoding="utf-8"))
    # Column.name is the GitHub Status display name; Column key is the native store key.
    return {col.name: key for key, col in columns.items()}


def ingest_external_move(root: Path, entry: Any, payload: dict[str, Any]) -> IngestOutcome:
    """Ingest an external GitHub drag into ``board.json`` (echo-safe, flock-safe) — keel step 5 B.

    For a registered, NATIVE-backed project, parse the new Status out of the ``projects_v2_item``
    change, map it to a native column key, and write it into ``board.json`` UNLESS it matches the
    current native placement (our own mirror echo — the own-writes ledger). A genuine external drag
    (or a first sighting of an unplaced item) is placed; the caller then nudges so the daemon's diff
    fires the launch.

    Every failure mode is a fail-soft outcome (never an exception): a non-native project, a payload
    with no Status change, an unmappable Status, a missing item id, or a store-write error all return
    a non-``ADOPTED`` outcome and the caller still nudges (so the slow safety sweep / daemon tick
    reconciles). The receiver must never 5xx a webhook.

    Args:
        root: The runtime root holding ``projects.json`` + the (per-project) ``board.json``.
        entry: The resolved registry entry for the project the event hit.
        payload: The decoded, HMAC-VERIFIED webhook JSON body.

    Returns:
        The :class:`IngestOutcome` describing what happened (for the receiver's log + response body).
    """
    # Only native-backed projects have a native store to ingest into. A "github"-backed project keeps
    # the legacy forge-authority path — the daemon reads GitHub's Status directly, so nudge-only.
    backend = getattr(entry, "board_backend", "native")
    if backend not in ("native", "hybrid"):
        return IngestOutcome.NOT_NATIVE

    status_name = extract_status_name(payload, getattr(entry, "status_field_node_id", ""))
    item_id = extract_item_id(payload)
    if status_name is None or item_id is None:
        # Not a Status-field change (an add / archive / a different field) → nothing to ingest. The
        # caller nudges so the daemon still reconciles (today's nudge-only path).
        return IngestOutcome.NO_STATUS

    try:
        from kanbanmate.adapters.store.fs_board import FsBoardStateStore
        from kanbanmate.cli.init import _load_registry, _projects_path
        from kanbanmate.core.registry_resolve import enabled_entries

        # Map the Status display name → native column key (the store is key-indexed).
        name_to_key = _name_to_key(entry)
        column_key = name_to_key.get(status_name)
        if column_key is None:
            # The forge Status has no matching native column (columns.yml drift). Cannot place it —
            # make it loud rather than silently swallow the external move. Nudge-only fallback.
            logger.warning(
                "kanban serve: external Status %r for item %s has no matching native column "
                "(columns.yml drift); skipping ingest — run 'kanban board import'",
                status_name,
                item_id,
            )
            return IngestOutcome.NO_STATUS

        # Resolve the per-project board.json root EXACTLY as the daemon wiring does (N>1 → the
        # per-project sub-root; N=1 → the flat root) so we read/write the daemon's own board.json.
        registry = _load_registry(_projects_path(root))
        multi = len(enabled_entries(registry)) > 1
        store = FsBoardStateStore(_board_store_root(root, entry, multi=multi))

        # The own-writes ledger: the CURRENT native placement is exactly what the daemon last
        # mirrored to GitHub. An incoming Status that equals it is our own mirror echo → DROP (no
        # write, no false adoption). Read under no lock for the cheap compare; the authoritative
        # write below re-checks nothing destructive (place_card is idempotent for a same-column move).
        current = store.load().get("placement", {}).get(item_id)
        if current == column_key:
            return IngestOutcome.ECHO_DROPPED

        # Genuine external drag (or first sighting) → place into board.json under the flock. This
        # bumps the store version, so the daemon's cheap_probe changes and the next (nudged) tick
        # re-snapshots, diffs the move, and launches.
        store.place_card(item_id, column_key)
        logger.info(
            "kanban serve: ingested external move of item %s → %r (was %r) into board.json",
            item_id,
            column_key,
            current,
        )
        return IngestOutcome.ADOPTED
    except Exception:  # noqa: BLE001 — fail-soft: never 5xx a webhook; the safety sweep reconciles
        logger.warning(
            "kanban serve: external-move ingest failed for item %s; nudging for the safety sweep",
            item_id,
            exc_info=True,
        )
        return IngestOutcome.ERROR
