# watch-seed — Implementation Plan Index

> **Feature**: Combined Watcher Service daemon + native cross-seeding engine
> **Codename**: `watch-seed` · **Type**: feat · **Branch**: `feat/watch-seed`
> **Design**: `docs/features/watch-seed/DESIGN.md` (frozen decisions D1–D11 + W1–W8)

## Phases

| #   | Phase                                                | File                                                                               | Status |
| --- | ---------------------------------------------------- | ---------------------------------------------------------------------------------- | ------ |
| 1   | RP10a — TorrentLayout parser + structural match      | [phase-01-rp10a-torrent-layout-parser.md](phase-01-rp10a-torrent-layout-parser.md) | [ ]    |
| 2   | RP10b — TorrentInjector protocol + QBitClient inject | [phase-02-rp10b-torrent-injector.md](phase-02-rp10b-torrent-injector.md)           | [ ]    |
| 3   | Cross-seed + watch configuration                     | [phase-03-cross-seed-config.md](phase-03-cross-seed-config.md)                     | [ ]    |
| 4   | CrossSeedService — X1 core + X2 sweep                | [phase-04-cross-seed-service.md](phase-04-cross-seed-service.md)                   | [ ]    |
| 5   | Cross-seed CLI + events                              | [phase-05-cross-seed-cli-events.md](phase-05-cross-seed-cli-events.md)             | [ ]    |
| 6   | WatcherService pure state machine                    | [phase-06-watcher-state-machine.md](phase-06-watcher-state-machine.md)             | [ ]    |
| 7   | Watch command loop + watch-now + run flags           | [phase-07-watch-loop.md](phase-07-watch-loop.md)                                   | [ ]    |
| 8   | PM2 ecosystem + launchd decommission                 | [phase-08-pm2-launchd-cutover.md](phase-08-pm2-launchd-cutover.md)                 | [ ]    |
| 9   | E2E roundtrip + ACCEPTANCE gate                      | [phase-09-e2e-acceptance-gate.md](phase-09-e2e-acceptance-gate.md)                 | [ ]    |

## Dependencies

```
Phase 1 (RP10a) ──┐
                   ├──> Phase 4 (CrossSeedService) ──> Phase 5 (CLI+Events)
Phase 2 (RP10b) ──┘                                      │
                                                         │
Phase 3 (Config) ────────────────────────────────────────┘
                                                         │
Phase 6 (WatcherService) ──> Phase 7 (Watch Loop) ───────┤
                                                         │
                                                         v
                                              Phase 8 (PM2+launchd)
                                                         │
                                                         v
                                              Phase 9 (E2E+ACC Gate)
```

## ACC Coverage

| ACC    | Phase | Description                                                                |
| ------ | ----- | -------------------------------------------------------------------------- |
| ACC-1  | 1     | RP10a parses real `.torrent` file-list + piece_length                      |
| ACC-2  | 1     | `structural_match` rejects piece_length mismatch + renamed root            |
| ACC-3  | 2     | `TorrentInjector` protocol exists; qBit composes it, Transmission does not |
| ACC-4  | 3     | Per-tracker `cross_seed` gate exists, defaults off (both overlays)         |
| ACC-5  | 5     | CLI sweep + single-hash commands registered                                |
| ACC-6  | 4     | Confirmed cross-seed tagged SEED_PURE + obligation written                 |
| ACC-7  | 9     | Ingest skips a SEED_PURE cross-seed injection (E2E)                        |
| ACC-8  | 7     | Watcher CLI commands registered (watch + watch-now)                        |
| ACC-9  | 7     | `watch-now` writes sentinel consumed by loop                               |
| ACC-10 | 6     | WatcherService state machine fully covered                                 |
| ACC-11 | 7     | `run --no-console` exists (Rich off, Telegram on)                          |
| ACC-12 | 8     | launchd machinery gone, PM2 ecosystem ships                                |
| ACC-13 | 9     | Full suite green (`make test`)                                             |

## Global Constraints

- **Docstrings**: Google-style on all public modules/classes/functions/methods.
- **Logger**: `personalscraper.logger.get_logger` — never `structlog.get_logger` (enforced by `make lint`'s `check_logging.py`).
- **Layering**: `acquire/` never imports `commands/`/`pipeline/` (guarded by `tests/architecture/test_layering.py`).
- **AppContext boundary**: new modules touching `AppContext` must be added to `test_app_context_boundary.py` allowlist.
- **Module size**: soft 800 LOC, hard 1000 LOC (`scripts/check-module-size.py` + `make check`).
- **Rg filter**: every `rg` command must carry `--type py` or `-g '*.py'` (14 GB fixture dir).
- **Config anti-drift**: new config blocks must appear in BOTH `config/` and `config.example/` overlays.
- **Commits**: Conventional Commits — `{type}(watch-seed): description` per sub-phase.
- **Tests**: regression test per bug (project rule); golden fixtures from REAL `.torrent` files for RP10a.
