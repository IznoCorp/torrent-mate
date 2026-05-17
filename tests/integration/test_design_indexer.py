"""Design-contract tests for the media indexer (codename: ``indexer``).

Pin points for ``docs/reference/indexer.md`` — schema versioning contract —
and ``docs/reference/indexer-json-shapes.md`` — JSON column shape invariants.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations, open_db
from personalscraper.indexer.schema import (
    ArtworkInventory,
    OutboxPayload,
    ScanStats,
)

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


class TestIndexerSchemaContract:
    """Schema versioning — DESIGN indexer.md §Schema Overview."""

    def test_each_migration_registers_in_schema_version_table(self, tmp_path: Path) -> None:
        """Every migration inserts a row into the ``schema_version`` audit table.

        Design: docs/reference/indexer.md#schema-overview
        Contract: Each migration script that bumps ``PRAGMA user_version``
        must also insert a row into the ``schema_version`` table so
        ``library-status`` and downgrade tooling can reason about the
        migration chain. A migration that forgets this insertion is a bug
        (regression captured in fc7d16c).
        """
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path, event_bus=EventBus())
        apply_migrations(conn, _MIGRATIONS_DIR)

        rows = conn.execute("SELECT version FROM schema_version ORDER BY version").fetchall()
        recorded_versions = [r[0] for r in rows]

        user_version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert user_version > 0
        for v in range(1, user_version + 1):
            assert v in recorded_versions, f"migration {v} did not record in schema_version"


class TestArtworkInventoryShapeContract:
    """``media_item.artwork_json`` — DESIGN indexer-json-shapes.md §media_itemartwork_json."""

    def test_artwork_inventory_defaults_all_false_and_rejects_unknown_keys(self) -> None:
        """ArtworkInventory has 8 boolean fields defaulting to False; extras forbidden.

        Design: docs/reference/indexer-json-shapes.md#media_itemartwork_json
        Contract: Per the documented schema, a freshly-indexed item is
        written with every artwork flag at False (the model can be
        instantiated with no arguments). The schema is closed
        (``extra="forbid"``) so a typo in a column-write does not
        silently survive into the JSON column. The eight tracked
        artwork kinds match the documented field list verbatim.
        """
        inv = ArtworkInventory()
        assert inv.poster is False
        assert inv.fanart is False
        assert inv.landscape is False
        assert inv.banner is False
        assert inv.clearlogo is False
        assert inv.clearart is False
        assert inv.discart is False
        assert inv.characterart is False

        with pytest.raises(ValidationError):
            ArtworkInventory(unknown_kind=True)  # type: ignore[call-arg]


class TestOutboxPayloadShapeContract:
    """``index_outbox.payload_json`` — DESIGN indexer-json-shapes.md §index_outboxpayload_json."""

    def test_outbox_payload_envelope_requires_op_and_allows_per_op_extras(self) -> None:
        """OutboxPayload pins ``op`` as required and tolerates op-specific keys.

        Design: docs/reference/indexer-json-shapes.md#index_outboxpayload_json
        Contract: The payload-envelope model documents ``op`` as the
        required discriminator (parent row's ``op`` column must match)
        with optional ``source_path`` / ``dest_path`` / ``item_id``
        slots. Per-op fields (``disk_id``, ``rel_path``, ``tmdb_id``,
        ``size_bytes`` and similar — see the doc tables) flow through
        via ``extra="allow"`` because runtime apply functions read them
        directly. A payload missing ``op`` is therefore malformed at
        the envelope level.
        """
        payload = OutboxPayload(
            op="move",
            source_path=None,
            dest_path="films/Inception (2010)",
            item_id=42,
            disk_id=1,
            size_bytes=8589934592,
        )
        assert payload.op == "move"
        # Extras survive on the model so producer/consumer agree.
        dumped = payload.model_dump()
        assert dumped["disk_id"] == 1
        assert dumped["size_bytes"] == 8589934592

        with pytest.raises(ValidationError):
            OutboxPayload()  # type: ignore[call-arg]


class TestScanStatsShapeContract:
    """``scan_run.stats_json`` — DESIGN indexer-json-shapes.md §scan_runstats_json."""

    def test_scan_stats_defaults_zero_and_forbids_unknown_keys(self) -> None:
        """ScanStats counters default to 0 and the schema is closed.

        Design: docs/reference/indexer-json-shapes.md#scan_runstats_json
        Contract: A scan run that completes without surfacing any
        items can persist ``ScanStats()`` directly — every counter
        defaults to 0 and ``budget_exhausted`` to False. The schema is
        ``extra="forbid"`` so a typo in a stats field cannot silently
        survive into the JSON column where downstream consumers would
        miss it.
        """
        stats = ScanStats()
        assert stats.items_added == 0
        assert stats.items_updated == 0
        assert stats.items_deleted == 0
        assert stats.files_walked == 0
        assert stats.bytes_read == 0
        assert stats.budget_exhausted is False

        with pytest.raises(ValidationError):
            ScanStats(items_addded=5)  # type: ignore[call-arg]
