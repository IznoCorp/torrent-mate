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
  scraper.json5               ← scraper, ingest, fuzzy_match
  trailers.json5              ← trailers.*
  indexer.json5               ← indexer.*
  thresholds.json5            ← thresholds.*
  metadata.json5              ← metadata.*
  providers.json5             ← providers.*
  torrent.json5               ← torrent.*
  tracker.json5               ← tracker.*
  ranking.json5               ← ranking.*
  notify.json5                ← notify.*
  local.json5                 ← optional, gitignored, last-wins machine overrides
```

## Example template

The tracked equivalent lives under `config.example/` at the repo root:

```
config.example/               ← tracked, canonical template for new installs
  config.json5                ← master (15 overlays + config_version)
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
```

The master `config.json5` lists exactly 15 overlays (one master + 15 overlay
files = 16 config files total).

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
| `scraper`, `ingest`, `fuzzy_match`                                                 | `scraper.json5`    |
| `trailers`                                                                         | `trailers.json5`   |
| `indexer`                                                                          | `indexer.json5`    |
| `thresholds`                                                                       | `thresholds.json5` |
| `metadata`                                                                         | `metadata.json5`   |
| `providers`                                                                        | `providers.json5`  |
| `torrent`                                                                          | `torrent.json5`    |
| `tracker`                                                                          | `tracker.json5`    |
| `ranking`                                                                          | `ranking.json5`    |
| `notify`                                                                           | `notify.json5`     |
