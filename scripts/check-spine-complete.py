#!/usr/bin/env python3
"""Executable spine-completeness gate — « tout doit être daté, et différenciable ».

This guardrail exists because of a method failure, not a code defect: the same bug
(« Récupéré · inconnue », « Ingéré · inconnue ») was reported **three times** by the
operator, and declared fixed three times — because each verification looked at the fields
that had just been touched, never at the four stages together nor at the screen.
``grabbed_at`` had quite simply never been measured.

So the script asks the only two questions the operator asks in front of the screen:

1. **Is it dated?** For every unknown stage of a journey, it goes looking for whether a
   source exists nonetheless. A stage that is unknown **while it is recoverable** is an
   anomaly: the repair is not finished. A stage that is unknown **with no source at all**
   is a proven finding, and is not counted.
2. **Is it distinguishable?** Two acquisitions of the same show must be tellable apart on
   screen. A series row with no season/episode while its ``wanted`` row carries them is an
   anomaly: four identical « Silo » cards read as duplicates.

The sources queried, per stage:

==================  ==========================================================
``grabbed_at``      ``seed_obligation.added_at`` (written at grab time), else
                    ``wanted.last_search_at`` — the grab immediately follows the
                    search that produced it (measured gap ≤ 25 s over 35 cases).
``ingested_at``     ``ingested_torrents.json`` (exact date per hash), else the
                    ``ingest`` stage of the run that carried the release.
``scraped_at``      the ``scrape`` stage of that same run.
``season/episode``  the ``wanted`` row of the hash.
==================  ==========================================================

Exit code = number of anomalies; 0 = the spine is complete and readable.

Usage:
    python scripts/check-spine-complete.py
    python scripts/check-spine-complete.py --json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass


@dataclass
class Gap:
    """A REPAIRABLE gap on a journey (one counted anomaly).

    Attributes:
        info_hash: The journey concerned.
        title: The follow's title, as the card displays it.
        field: The missing field (``grabbed_at`` / ``ingested_at`` / ``scraped_at`` /
            ``identity``).
        source: The source that could fill it — hence the proof that it is not
            lost, merely not picked back up yet.
    """

    info_hash: str
    title: str
    field: str
    source: str

    def line(self) -> str:
        """Renders the anomaly as one readable line."""
        return f"❌ [{self.field}] {self.title} ({self.info_hash[:12]}…) : recoverable via {self.source}"


def _iso_to_epoch(raw: object) -> int | None:
    """Parses an ISO-8601 date into an epoch, or None when unreadable."""
    import datetime as _dt

    if not isinstance(raw, str):
        return None
    try:
        return int(_dt.datetime.fromisoformat(raw).timestamp())
    except ValueError:
        return None


def _runs_by_release(indexer_conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """Indexes ``{release name: {stage: epoch}}`` from the run journal.

    Each run's ingest stage names, in its ``reasons``, the releases it copied; the same
    run then scraped them. The release name therefore ties a torrent to its run, and
    that run's per-stage instants date its journey.

    Args:
        indexer_conn: An open connection on ``library.db``.

    Returns:
        The index by release name; empty on a read error.
    """
    index: dict[str, dict[str, int]] = {}
    try:
        rows = indexer_conn.execute(
            "SELECT steps_json FROM pipeline_run WHERE steps_json IS NOT NULL ORDER BY started_at ASC"
        ).fetchall()
    except sqlite3.Error:
        return index
    for (steps_json,) in rows:
        try:
            steps = json.loads(steps_json)
        except (TypeError, ValueError):
            continue
        if not isinstance(steps, list):
            continue
        stages: dict[str, int] = {}
        reasons: list[str] = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            ended = step.get("ended_at")
            if isinstance(ended, (int, float)):
                stages[str(step.get("name"))] = int(ended)
            if step.get("name") == "ingest":
                reasons = [str(r) for r in (step.get("reasons") or [])]
        for reason in reasons:
            name = reason.split(" → ")[0].split(":")[0].strip()
            if name:
                index.setdefault(name, stages)
    return index


def collect_gaps(
    acquire_conn: sqlite3.Connection,
    indexer_conn: sqlite3.Connection,
    ingest_tracker: dict[str, dict[str, object]] | None = None,
) -> list[Gap]:
    """Confronts every journey with its sources and returns the REPAIRABLE gaps.

    A pure core — no configuration, no I/O beyond the open connections — so that the
    tests exercise it directly on temporary databases.

    Args:
        acquire_conn: A connection on ``acquire.db``.
        indexer_conn: A connection on ``library.db`` (the run journal).
        ingest_tracker: ``ingested_torrents.json`` already loaded, or None.

    Returns:
        The repairable gaps, in journey order.
    """
    acquire_conn.row_factory = sqlite3.Row
    tracker = {k.lower(): v for k, v in (ingest_tracker or {}).items()}
    runs = _runs_by_release(indexer_conn)

    obligations: dict[str, int] = {}
    for row in acquire_conn.execute("SELECT info_hash, added_at FROM seed_obligation"):
        h = (row["info_hash"] or "").lower()
        obligations[h] = min(obligations.get(h, row["added_at"]), row["added_at"])

    wanted: dict[str, sqlite3.Row] = {}
    for row in acquire_conn.execute(
        "SELECT grabbed_hash, kind, season, episode, last_search_at FROM wanted "
        "WHERE grabbed_hash IS NOT NULL AND grabbed_hash != ''"
    ):
        wanted.setdefault(row["grabbed_hash"].lower(), row)

    titles = {r["id"]: r["title"] for r in acquire_conn.execute("SELECT id, title FROM followed_series")}
    columns = {r[1] for r in acquire_conn.execute("PRAGMA table_info('staging_provenance')")}

    gaps: list[Gap] = []
    for row in acquire_conn.execute("SELECT * FROM staging_provenance ORDER BY rowid"):
        h = (row["info_hash"] or "").lower()
        title = titles.get(row["followed_id"], "(no follow)") if row["followed_id"] is not None else "(no follow)"
        w = wanted.get(h)
        entry = tracker.get(h) or {}
        release = entry.get("name")
        stages = runs.get(release, {}) if isinstance(release, str) else {}

        if row["grabbed_at"] is None:
            if h in obligations:
                gaps.append(Gap(h, title, "grabbed_at", "seed_obligation.added_at"))
            elif w is not None and w["last_search_at"] is not None:
                gaps.append(Gap(h, title, "grabbed_at", "wanted.last_search_at"))
        if row["ingested_at"] is None:
            if _iso_to_epoch(entry.get("date")) is not None:
                gaps.append(Gap(h, title, "ingested_at", "ingested_torrents.json"))
            elif "ingest" in stages:
                gaps.append(Gap(h, title, "ingested_at", "pipeline_run (ingest stage)"))
        if row["scraped_at"] is None and "scrape" in stages:
            gaps.append(Gap(h, title, "scraped_at", "pipeline_run (scrape stage)"))

        # The workflow's ORDER (§14.2): an instant, measured or estimated, cannot
        # contradict the sequence. An estimate that placed the ingestion after the
        # dispatch would be worse than the emptiness it replaces.
        sequence = [row["grabbed_at"], row["ingested_at"], row["scraped_at"], row["dispatched_at"]]
        known = [value for value in sequence if value is not None]
        if known != sorted(known):
            gaps.append(Gap(h, title, "ordre", "the instants contradict the workflow sequence"))

        # Distinguishable: a series whose wanted row carries a season MUST carry it
        # too, otherwise two acquisitions of the same show are indistinguishable.
        if w is not None and w["season"] is not None:
            has_columns = {"season", "episode"} <= columns
            if not has_columns or row["season"] is None:
                gaps.append(Gap(h, title, "identity", "wanted.season / wanted.episode"))

    return gaps


def _open_ro(path: str) -> sqlite3.Connection:
    """Opens a SQLite database strictly read-only."""
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def main() -> int:
    """Runs the check on the configured databases.

    Returns:
        The number of anomalies (0 = complete), or 2 when a database is missing.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="Dump JSON instead of the readable lines.")
    args = parser.parse_args()

    from personalscraper.conf.loader import load_config

    config = load_config()
    acquire_path, indexer_path = config.acquire.db_path, config.indexer.db_path
    if acquire_path is None or not acquire_path.exists() or indexer_path is None or not indexer_path.exists():
        print("acquire.db or library.db not found", file=sys.stderr)
        return 2

    tracker: dict[str, dict[str, object]] = {}
    try:
        tracker = json.loads((config.paths.data_dir / "ingested_torrents.json").read_text())
    except (OSError, ValueError):
        pass

    acquire_conn, indexer_conn = _open_ro(str(acquire_path)), _open_ro(str(indexer_path))
    try:
        gaps = collect_gaps(acquire_conn, indexer_conn, tracker)
    finally:
        acquire_conn.close()
        indexer_conn.close()

    if args.json:
        print(json.dumps([asdict(g) for g in gaps], indent=2, ensure_ascii=False))
    else:
        for gap in gaps:
            print(gap.line())
        by_field: dict[str, int] = {}
        for gap in gaps:
            by_field[gap.field] = by_field.get(gap.field, 0) + 1
        detail = ", ".join(f"{n} {field}" for field, n in sorted(by_field.items())) or "none"
        print(f"\n{len(gaps)} REPAIRABLE gap(s) — {detail}.")
        if gaps:
            print("The repair is not finished: these stages have a source and are empty all the same.")
    return len(gaps)


if __name__ == "__main__":
    raise SystemExit(main())
