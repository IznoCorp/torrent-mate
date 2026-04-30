# Config Overlay Layout (v2 Split Config)

## Directory structure

The v2 config is a directory of JSON5 files rather than a single monolith:

```
.personalscraper/config/      ← gitignored, machine-specific
  config.json5                ← master: declares overlays list + config_version
  paths.json5                 ← paths.*
  disks.json5                 ← disks[]
  categories.json5            ← custom_categories, categories{}, category_rules[], anime_rule, genre_mapping
  patterns.json5              ← staging_dirs[]
  encoding.json5              ← library.*
  scraper.json5               ← scraper, ingest, fuzzy_match
  trailers.json5              ← trailers.*
  local.json5                 ← optional, gitignored, last-wins machine overrides
```

## Example template

The tracked equivalent lives under `config.example/` at the repo root:

```
config.example/               ← tracked, canonical template for new installs
  config.json5                ← master (same structure, placeholder values)
  paths.json5
  disks.json5
  categories.json5
  patterns.json5
  encoding.json5
  scraper.json5
  trailers.json5
```

The legacy `config.example.json5` at repo root is kept as a compatibility reference
and updated to point users to `config.example/` in its header comment.

## Overlay merge rules

1. Master `config.json5` is the base dict (minus the `overlays` key).
2. Each file in `overlays` is merged in order via `merge_overlays()`.
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
