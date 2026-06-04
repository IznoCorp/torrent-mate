# torrent-write Implementation Plan — Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface a write capability on the torrent-client family: add a torrent (magnet or .torrent bytes) with category + tags, apply transfer limits where supported (qBit only), and boot-wire the client into `AppContext` with a capability fail-fast.

**Architecture:** Contract layer first (value objects + Protocols + model field), then client implementations (qBit: add + limits; Transmission: add only, raises on limits), then boot-wiring (AppContext promotion + `_build_app_context()` fail-fast + removal of two lazy inline fallbacks). Final phases: docs + executable acceptance criteria + ROADMAP flip.

**Tech Stack:** Python 3.11, `dataclasses`, `hashlib`, `typing.Protocol` (`@runtime_checkable`), `qbittorrentapi`, `transmission_rpc`, pytest, `make lint/test/check`

---

## Phases

| #   | Phase                                                                      | File                              | Status |
| --- | -------------------------------------------------------------------------- | --------------------------------- | ------ |
| 1   | `TorrentSource` + `TorrentLimits` value objects                            | phase-01-value-objects.md         | [ ]    |
| 2   | `TorrentAdder` + `TorrentLimiter` Protocols + `UnsupportedCapabilityError` | phase-02-protocols.md             | [ ]    |
| 3   | `TorrentItem.tags` field + mapper updates (qBit CSV + Transmission D5)     | phase-03-torrentitem-tags.md      | [ ]    |
| 4   | `QBitClient.add()` + `_limit_kwargs()`                                     | phase-04-qbit-add.md              | [ ]    |
| 5   | `QBitClient.apply_limits()` + composition assertions                       | phase-05-qbit-apply-limits.md     | [ ]    |
| 6   | `TransmissionClient.add()` + `_labels()` + composition assertions          | phase-06-transmission-add.md      | [ ]    |
| 7   | `AppContext.torrent_client` field                                          | phase-07-appcontext-field.md      | [ ]    |
| 8   | Fail-fast in `_build_app_context()` (D3/D9)                                | phase-08-boot-failfast.md         | [ ]    |
| 9   | Remove lazy inline `QBitClient` fallbacks                                  | phase-09-remove-lazy-fallbacks.md | [ ]    |
| 10  | Reference docs updates                                                     | phase-10-docs.md                  | [ ]    |
| 11  | Executable `ACCEPTANCE.md` + ROADMAP flip                                  | phase-11-acceptance-roadmap.md    | [ ]    |

---

## ACCEPTANCE Criteria Mapping

Every criterion is an executable shell command with a documented expected output. Full commands live in `docs/features/torrent-write/ACCEPTANCE.md` (written in Phase 11).

| ACC    | Command                                                                                                                                                                     | Expected         | Phase      |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- | ---------- |
| ACC-01 | `python -c "from personalscraper.api.torrent import TorrentAdder, TorrentLimiter; from personalscraper.api.torrent._base import TorrentSource, TorrentLimits; print('ok')"` | `ok`, exits 0    | Phase 1–2+ |
| ACC-02 | `python -c "from personalscraper.api.torrent._base import TorrentItem; i=TorrentItem(hash='h',name='n',size_bytes=0,progress=0.0,state='up'); assert i.tags==[]"`           | exits 0          | Phase 3+   |
| ACC-03 | `pytest tests/unit/test_torrent_source.py -q`                                                                                                                               | all pass         | Phase 1    |
| ACC-04 | `pytest tests/unit/test_torrent_write_contracts.py -q`                                                                                                                      | all pass         | Phase 2    |
| ACC-05 | `pytest tests/unit/test_qbittorrent_add.py -q`                                                                                                                              | all pass         | Phase 4–5  |
| ACC-06 | `pytest tests/unit/test_transmission_add.py -q`                                                                                                                             | all pass         | Phase 6    |
| ACC-07 | `pytest tests/unit/test_torrent_capabilities_composition.py -q`                                                                                                             | all pass         | Phase 5–6  |
| ACC-08 | `pytest tests/unit/test_build_app_context_torrent.py -q`                                                                                                                    | all pass         | Phase 8    |
| ACC-09 | `rg -t py "QBitClient\(" personalscraper/ingest/ingest.py personalscraper/commands/pipeline.py`                                                                             | rc=1, no matches | Phase 9    |
| ACC-10 | `python -c "import personalscraper; print('ok')"`                                                                                                                           | `ok`, exits 0    | Each gate  |
| ACC-11 | `make check`                                                                                                                                                                | rc=0, all pass   | Each gate  |

---

## Frozen design decisions (quick reference)

| #   | Decision                                                                                               |
| --- | ------------------------------------------------------------------------------------------------------ |
| D1  | `add(source, *, category, tags, paused, limits) -> str`; `TorrentSource` is discriminated value object |
| D2  | `TorrentLimiter` separate Protocol; qBit only. `TorrentAdder` composed by both                         |
| D3  | Torrent client promoted to `AppContext`; fail-fast in `_build_app_context()` via `RegistryConfigError` |
| D4  | `TorrentItem.tags: list[str] = field(default_factory=list)`                                            |
| D5  | Transmission labels: write `[category, *tags]`; read `category=labels[0]`, `tags=labels[1:]`           |
| D6  | `add()` returns `info_hash` (magnet → parse btih; bytes → stdlib SHA-1 of info dict)                   |
| D7  | Duplicate add = idempotent success                                                                     |
| D8  | `limits` on Transmission client RAISES `UnsupportedCapabilityError` — no silent ignore                 |
| D9  | No client configured → `torrent_client=None`, no boot error                                            |
| D10 | No limit defaults in config; `TorrentClientEntry.save_path` only if needed                             |

---

## Per-gate quality checklist (CLAUDE.md §Phase Gate)

Each phase gate commit MUST pass all of:

1. `make lint` → 0 errors (ruff + mypy)
2. `make test` → all pass, 0 collection ERROR
3. `make check` → rc=0
4. Residual-import grep for deleted/moved symbols → 0 matches
5. `python -c "import personalscraper"` → exits 0

---

## Key code anchors

| Symbol                                                                       | File                                                                               |
| ---------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `TorrentSource`, `TorrentLimits`, `_parse_magnet_hash`, `_bencode_info_hash` | `personalscraper/api/torrent/_base.py`                                             |
| `TorrentAdder`, `TorrentLimiter` (new) + 5 existing Protocols                | `personalscraper/api/torrent/_contracts.py`                                        |
| `UnsupportedCapabilityError` (new)                                           | `personalscraper/api/torrent/_errors.py`                                           |
| `QBitClient.add()`, `QBitClient.apply_limits()`, `_limit_kwargs()`           | `personalscraper/api/torrent/qbittorrent.py`                                       |
| `TransmissionClient.add()`, `_labels()`                                      | `personalscraper/api/torrent/transmission.py`                                      |
| `AppContext.torrent_client`                                                  | `personalscraper/core/app_context.py`                                              |
| `_build_app_context()` torrent boot block                                    | `personalscraper/cli_helpers/__init__.py`                                          |
| Lazy build removed → reads `ctx.torrent_client`                              | `personalscraper/ingest/ingest.py:294`, `personalscraper/commands/pipeline.py:641` |
