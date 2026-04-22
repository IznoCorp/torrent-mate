# Migration V14 → V15

This document describes the upgrade path from **V14** (hardcoded disk paths and French
category labels) to **V15** (config-driven architecture with abstract category IDs).

## Why V15?

V14 baked storage paths (`DISK1_DIR`…`DISK4_DIR`) and category names (`"films"`,
`"series"`, `"series animes"`, etc.) directly into the code and `.env` file.
V15 moves all user-specific values into `config.json5`, leaving the code
completely generic and portable.

## Quickstart

```bash
# Automated migration from an existing V14 setup
personalscraper init-config --from-current
```

This single command:

1. Reads `DISK1_DIR`–`DISK4_DIR`, `STAGING_DIR`, `TORRENT_COMPLETE_DIR` from `.env`
2. Generates `config.json5` with matching disk/category structure
3. Merges `library_preferences.json` into `config.json5` (`library` section)
4. Rewrites `library_index.json` categories from V14 FR labels to V15 IDs
5. Converts `.category` sidecar files to NFO `<category>` tags
6. Moves `.personalscraper/` to `.data/` (configured via `config.json5`)

## Manual Migration

If the automated command fails or your setup is non-standard:

### 1. Create `config.json5` from template

```bash
cp config.example.json5 config.json5
```

Edit `config.json5`:

- Set `paths.torrent_complete_dir`, `paths.staging_dir`, `paths.data_dir`
- Add each disk under `disks[]` with the correct `id`, `path`, and `categories`
- Set `folder_name` for each category to match your physical directory names

### 2. Map V14 folder names to V15 IDs

| V14 folder name        | V15 category ID        |
| ---------------------- | ---------------------- |
| `films`                | `movies`               |
| `films animations`     | `movies_animation`     |
| `films documentaires`  | `movies_documentary`   |
| `spectacles`           | `standup`              |
| `theatres`             | `theater`              |
| `series`               | `tv_shows`             |
| `series animations`    | `tv_shows_animation`   |
| `series documentaires` | `tv_shows_documentary` |
| `series animes`        | `anime`                |
| `emissions`            | `tv_programs`          |
| `livres audios`        | `audiobooks`           |

### 3. Validate the config

```bash
python -c "from pathlib import Path; from personalscraper.conf.loader import load_config; load_config(Path('config.json5')); print('OK')"
```

## Rollback

Every migration command creates `.v14.bak` backups:

- `library_index.json.v14.bak` — original library index
- `library_preferences.json.v14.bak` — original preferences
- `.personalscraper.v14.bak/` — original data directory

To rollback:

```bash
mv config.json5 config.json5.bak
cp library_index.json.v14.bak library_index.json
cp library_preferences.json.v14.bak library_preferences.json
mv .personalscraper.v14.bak .personalscraper
```

## Troubleshooting

### Unknown V14 label in library_index.json

If `migrate_library_json` warns about an unknown category label, add a custom
mapping in `config.json5` under `custom_categories` or correct the
`category_rules` to catch the label.

### Cross-filesystem data_dir move fails

If `.personalscraper/` and the new `data_dir` are on different filesystems,
`os.rename` will fail. Solution: `cp -r .personalscraper /new/path/data &&
rm -rf .personalscraper` then set `paths.data_dir` in `config.json5`.

### NFOs without `<category>` tag

Items in `library_index.json` marked as "unknown" after migration means the NFO
never had a `<category>` tag. Run `personalscraper library-rescrape` to refetch
and regenerate NFOs with correct IDs.

## Post-Migration Checklist

- [ ] Review `spectacles → standup` mapping — confirm your folder name
- [ ] Verify each disk path is correct in `config.json5`
- [ ] Run `personalscraper library-scan` and check output for unexpected items
- [ ] Run `personalscraper run --dry-run` to confirm the full pipeline works
- [ ] Remove `.env` path variables: `DISK1_DIR`–`DISK4_DIR`, `STAGING_DIR`,
      `TORRENT_COMPLETE_DIR` (keep secrets: `TMDB_API_KEY`, `TVDB_API_KEY`, etc.)
