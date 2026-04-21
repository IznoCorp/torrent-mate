# Phase 4 — Migration module + `init-config` command

## Objectif

Implémenter la migration V14 → V15 intégrale (`.env`, `library_*.json`, `.category`, `.personalscraper/` → `.data/`) et la commande `personalscraper init-config` interactive avec support `--from-current`, `--force`, `--yes`.

## Sous-phases

### 4.1 — `conf/migration.py` : V14_LABEL_TO_ID + squelette

- [ ] Créer `personalscraper/conf/migration.py` avec :
  - `V14_LABEL_TO_ID: dict[str, str]` (11 mappings, dont "spectacles" → "standup")
  - Signatures `generate_config_from_env`, `migrate_library_json`, `migrate_category_files`, `migrate_data_dir`
- [ ] Test : `V14_LABEL_TO_ID` couvre les 11 KNOWN_CATEGORIES V14 (introspection sur `genre_mapper.KNOWN_CATEGORIES`)

**Commit** : `v15.4.1: Add conf/migration.py scaffold with V14_LABEL_TO_ID`

### 4.2 — `generate_config_from_env` : V14 .env → config.json5 dict

- [ ] Implémenter `generate_config_from_env(env_values: dict[str, str]) -> dict` :
  - Parse `TORRENT_COMPLETE_DIR`, `STAGING_DIR`, `DISK1_DIR..DISK4_DIR`
  - Extract `DISK_CATEGORIES` depuis V14 `disk_scanner.py` (inline la map V14 dans migration.py pour indépendance)
  - Construire `disks` list avec V14 → V15 IDs mappés
  - Pre-remplir `genre_mapping` avec les IDs V14 `genre_mapper.py` → IDs V15
  - Construire `anime_rule` miroir V14 (applies_to="tv", requires_genre_id=16, requires_origin_country=["JP"], maps_to="anime")
  - `categories.*.folder_name` = label V14 original (préserve nommage dossiers sur disque)
- [ ] Test fixture : `v14_env_sample.env` avec DISK\*\_DIR + secrets → assert config result structure + validation Pydantic OK

**Commit** : `v15.4.2: Implement generate_config_from_env for V14 migration`

### 4.3 — `migrate_library_json` : rewrite labels → IDs

- [ ] Implémenter `migrate_library_json(file_path, backup_suffix=".v14.bak") -> None` :
  - Backup `.v14.bak` (refuse si existe déjà, éviter écraser backup manuel)
  - Parse JSON, pour chaque field connu containing label : rewrite via `V14_LABEL_TO_ID`
  - Label inconnu → log WARN, laisse tel quel (pas de crash)
  - Fields par fichier (à enumerer via introspection des V14 writers) :
    - `library_index.json` : items[].category (string label)
    - `library_analysis.json` : même structure
    - `library_rescrape.json`, `library_recommendations.json`, `library_validation.json` : idem
- [ ] Test fixtures : 5 fichiers V14 samples → assert rewritten vers IDs + backup créé

**Commit** : `v15.4.3: Implement migrate_library_json with V14 label rewrite`

### 4.4 — `migrate_category_files` : .category → NFO `<category>`

- [ ] Implémenter `migrate_category_files(staging_root: Path) -> int` :
  - Walk staging_root récursif, glob `**/.category`
  - Pour chaque `.category` :
    - Read content, strip, map via `V14_LABEL_TO_ID` (label inconnu → WARN, skip)
    - Find sibling NFO (movie.nfo ou tvshow.nfo)
    - Si NFO absent → WARN "no NFO sibling for {path}", laisse `.category`
    - Si NFO présent → parse XML, insert `<category source="personalscraper">{ID}</category>` (skip si element existe déjà avec même source)
    - Write NFO, delete `.category`
  - Return count migrated
  - Lock file check en début : si `data_dir/lock.json` existe → refuse (pipeline tourne)
- [ ] Test fixture : tarball `v14_category_files.tar.gz` avec scénarios : `.category` + NFO, `.category` sans NFO, label inconnu, lock présent

**Commit** : `v15.4.4: Implement migrate_category_files to NFO category element`

### 4.5 — `migrate_data_dir` : `.personalscraper/` → `.data/`

- [ ] Implémenter `migrate_data_dir(staging_dir: Path) -> Path` :
  - Source = `staging_dir / ".personalscraper"`, target = `staging_dir / ".data"`
  - Check same filesystem (via `os.stat().st_dev`) — si différent, abort avec message explicite
  - Check target n'existe pas (sinon abort)
  - `shutil.move(source, target)` atomique si même filesystem
  - Return target (chemin absolu à écrire dans config.data_dir)
- [ ] Tests : same-fs move, cross-fs detection, target existe (abort), lock file present (abort)

**Commit** : `v15.4.5: Implement migrate_data_dir with same-filesystem atomicity check`

### 4.6 — `commands/init_config.py` : squelette + interactive flow

- [ ] Créer `personalscraper/commands/__init__.py` (vide)
- [ ] Créer `personalscraper/commands/init_config.py` avec :
  - Signature `init_config(example, output, *, interactive, from_current, force) -> None`
  - Si `output.exists()` et pas `force` → error + exit 2
  - Si `output.exists()` et `force` → backup vers `output.with_suffix(".json5.v15.bak")`
  - Si `from_current` → appel `generate_config_from_env(...)` + appel toutes les migrations
  - Sinon (simple) : parse example via `example_parser.parse_example()` et boucle prompts
  - Prompts via `typer.prompt()` (accepte ENTER = default)
  - Write résultat JSON5 avec `json5.dumps(indent=2)`
- [ ] Tests avec `CliRunner(input="...")` pour simuler l'interaction

**Commit** : `v15.4.6: Add commands/init_config.py with interactive and from-current modes`

### 4.7 — `init-config --from-current --yes` sans `.env` : error

- [ ] Dans `init_config()` : si `from_current` et `not interactive` et `.env` manque DISK\*\_DIR → error avec message clair + exit 2
- [ ] Test : `--from-current --yes` sur fixture `.env` sans DISK_DIR → assert exit 2 + message

**Commit** : `v15.4.7: Error explicit when --from-current --yes lacks V14 .env`

### 4.8 — `init-config --from-current` : E2E

- [ ] Test E2E complet `tests/migration/test_init_config_e2e.py` :
  - Setup tmp staging avec `.env` V14 + `.personalscraper/` + `.category` files + NFOs
  - Run `init-config --from-current --yes` (avec inputs minimum)
  - Assert `config.json5` créé et `load_config()` passe
  - Assert `.personalscraper/` déplacé vers `.data/`
  - Assert `library_*.json` rewrittés avec backup `.v14.bak`
  - Assert `.category` files migrés vers NFOs (+ supprimés)
  - Assert semantic equivalence : config résultat matche la V14 source (paths, categories, disks)

**Commit** : `v15.4.8: E2E test of init-config --from-current full migration`

## Tests de cohérence P4→P5

- [ ] `tests/conf/test_migration.py` : tous passent
- [ ] `tests/commands/test_init_config.py` : tous passent (interactive via CliRunner, from-current via fixture)
- [ ] `tests/migration/test_init_config_e2e.py` : E2E passe
- [ ] Migration **idempotente** : re-run `--force` overwrite le backup précédent (test explicite)
- [ ] `conf/migration.py::V14_LABEL_TO_ID` couvre les 11 KNOWN_CATEGORIES V14
- [ ] mypy strict : 0 erreur sur `conf/migration.py`, `commands/init_config.py`
