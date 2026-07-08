# Config Overlay Layout (v2 Split Config)

## Directory structure

The v2 config is a directory of JSON5 files rather than a single monolith:

```
config/                       ← gitignored, machine-specific (created by init-config)
  config.json5                ← master: declares overlays list + config_version
  paths.json5                 ← paths.*
  disks.json5                 ← disks[]
  categories.json5            ← custom_categories, categories{}, category_rules[], anime_rule, genre_mapping
  patterns.json5              ← staging_dirs[]
  encoding.json5              ← library.*
  scraper.json5               ← scraper, ingest, sort, fuzzy_match
  trailers.json5              ← trailers.*
  indexer.json5               ← indexer.*
  thresholds.json5            ← thresholds.*
  metadata.json5              ← metadata.*
  providers.json5             ← providers.*
  torrent.json5               ← torrent.*
  tracker.json5               ← tracker.*
  ranking.json5               ← ranking.*
  notify.json5                ← notify.*
  watch_seed.json5             ← cross_seed.*, watch.*
  web.json5                    ← web.*
  local.json5                 ← optional, gitignored, last-wins machine overrides
```

## Example template

The tracked equivalent lives under `config.example/` at the repo root:

```
config.example/               ← tracked, canonical template for new installs
  config.json5                ← master (18 overlays + config_version)
  paths.json5
  disks.json5
  categories.json5
  patterns.json5
  encoding.json5
  scraper.json5
  trailers.json5
  indexer.json5
  thresholds.json5
  metadata.json5
  providers.json5
  torrent.json5
  tracker.json5
  ranking.json5
  notify.json5
  watch_seed.json5
  web.json5
```

The master `config.json5` lists exactly 18 overlays (one master + 18 overlay
files = 19 config files total).

The `config.example/` directory at repo root is the tracked template for new installs.
Run `personalscraper init-config` to copy it to `./config/`.

## Overlay merge rules

1. The `overlays` key is read from `config.json5`, then **popped** from the
   master dict (`conf/loader.py`). The remaining master dict (still carrying
   `config_version` and any other master-only keys) becomes the merge base.
2. Each file named in `overlays` is merged onto that base, in declaration
   order, via `merge_overlays()`.
3. Two non-local overlays **must not** share the same top-level key
   (`ConfigConflictError` is raised).
4. Optional `local.json5` is merged last with last-wins semantics (no conflict error).

## Key ownership

| Top-level key(s)                                                                   | File               |
| ---------------------------------------------------------------------------------- | ------------------ |
| `config_version`, `overlays`                                                       | `config.json5`     |
| `paths`                                                                            | `paths.json5`      |
| `disks`                                                                            | `disks.json5`      |
| `custom_categories`, `categories`, `category_rules`, `anime_rule`, `genre_mapping` | `categories.json5` |
| `staging_dirs`                                                                     | `patterns.json5`   |
| `library`                                                                          | `encoding.json5`   |
| `scraper`, `ingest`, `sort`, `fuzzy_match`                                         | `scraper.json5`    |
| `trailers`                                                                         | `trailers.json5`   |
| `indexer`                                                                          | `indexer.json5`    |
| `thresholds`                                                                       | `thresholds.json5` |
| `metadata`                                                                         | `metadata.json5`   |
| `providers`                                                                        | `providers.json5`  |
| `torrent`                                                                          | `torrent.json5`    |
| `tracker`                                                                          | `tracker.json5`    |
| `ranking`                                                                          | `ranking.json5`    |
| `notify`                                                                           | `notify.json5`     |
| `acquire`                                                                          | `acquire.json5`    |
| `cross_seed`, `watch`                                                              | `watch_seed.json5` |
| `web`                                                                              | `web.json5`        |

## Tracker economy schema (tracker-economy RP2)

`tracker.json5` providers may include an optional `economy` block:

    c411: {
      enabled: true,
      economy: {
        target_ratio: 2.0,        // required; must be >= min_ratio
        min_ratio: 1.0,           // default 1.0; deletion floor (Vague 5 O2)
        min_seed_time: "72h",     // humanized string → integer seconds at load
        hit_and_run_grace: "0h",  // default "0h"; grace before H&R counting
      },
    },

Duration fields accept `"<N><unit>"` (unit `s/m/h/d/w`) or bare integer seconds.
Invalid strings raise `ValueError` at boot.

### Optional-secret convention

Announce passkeys are **non-gating**: a missing `<TRACKER>_PASSKEY` never
deactivates a tracker. Resolved via `resolve_optional_secret()` in
`api/_activation.py` — never consulted by `resolve_active()`.
See `.env.example` for variable names (`LACALE_PASSKEY`, `C411_PASSKEY`).

## Programmatic writes (S4 config editor)

The web config editor (`/config` route, TorrentMate S4) rewrites overlay files
and `local.json5` atomically via `tempfile.mkstemp` + `os.replace` with a
generated header comment:

```
// Written by TorrentMate config editor <ISO-8601-utc> — hand-written comments are not preserved.
```

**Implications**:

- Hand-written inline comments in config files are lost on the first web edit.
  Operators who rely on inline comments should keep notes in `config.example/`
  (the tracked template) or version-control their `config/` directory.
- Git-tracked config files get dirty on every web edit (accepted as an audit
  trail per DESIGN.md §Appendix D4).
- Before each write, the current file is backed up to
  `config/.backups/{name}.{utc_microsecond}.json5`. The 10 most recent backups
  per file name are kept; older ones are pruned automatically.
- The master `config.json5` (overlays array + `config_version`) is **read-only**
  through the write endpoints — only overlay files and `local.json5` are
  writable via `PUT /api/config/files/{name}`.
