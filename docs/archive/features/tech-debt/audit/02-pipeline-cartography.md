# Item 2 — Étude du pipeline et de son fonctionnement

**Périmètre** : flux opérationnel complet — pipeline strict + library-index + trailers + enforce.
**Date** : 2026-05-21
**Méthode** : lecture comparée du code (`personalscraper/pipeline.py`, `commands/pipeline.py`, et les `run.py` de chaque étape) avec `docs/reference/pipeline-internals.md` + `architecture.md` + `event-bus.md`, et avec le matrix actuel de la skill `pipeline-monitor`.

---

## 1. Vue d'ensemble — ce que fait réellement `personalscraper run`

### 1.1 Orchestration

Le code (`personalscraper/pipeline.py::Pipeline.run`) exécute **7 étapes orchestrées** en séquence stricte :

```
INGEST → SORT → [GATE: 097-TEMP empty] → PROCESS → ENFORCE → VERIFY → TRAILERS → DISPATCH
```

`PROCESS` est une étape composite qui produit **3 StepReports** indépendants :

```
PROCESS = clean → scrape → cleanup
```

Au final, un `PipelineReport` contient donc **9 StepReports nommés** :

| Ordre | Step name  | Origine               |
| ----- | ---------- | --------------------- |
| 1     | `ingest`   | étape directe         |
| 2     | `sort`     | étape directe         |
| 3     | `clean`    | sous-étape de PROCESS |
| 4     | `scrape`   | sous-étape de PROCESS |
| 5     | `cleanup`  | sous-étape de PROCESS |
| 6     | `enforce`  | étape directe         |
| 7     | `verify`   | étape directe         |
| 8     | `trailers` | étape directe         |
| 9     | `dispatch` | étape directe         |

### 1.2 Modes de criticité

- **CRITIQUE** (abort pipeline si fatal crash) : `ingest`, `sort`
- **TRAILERS** : bloquant par défaut (`TrailerStepFailed` raise abort dispatch). Configurable via `--continue-on-trailer-error` ou `config.trailers.pipeline.continue_on_error`.
- **DISPATCH** : skip silencieux si `verified` est vide (emit quand même `StepStarted`/`StepCompleted` pour symétrie bus).
- **Autres** : isolation par étape — un crash ne stoppe pas la suite.

### 1.3 Lifecycle subscribers + AppContext

Tout est construit dans `pipeline.run()` AVANT la première étape :

- **AppContext** (`_build_app_context`) — porte le shared `event_bus`
- **HealthcheckClient** — `ping_start` au début, `ping_success`/`ping_fail` dans le finally
- **RichConsoleSubscriber** + **TelegramSubscriber** (si configurés, sauf `--headless`)
- **DebugLogSubscriber** (si `--verbose`)
- **Pipeline** (`personalscraper.pipeline.Pipeline`)

Le `pipeline.lock` est pris au CLI level (`commands/pipeline.py::run`) avant tout, libéré dans le finally.

---

## 2. Fiches par étape

Chaque fiche : commande CLI · module(s) clé(s) · I/O · invariants · events.

### 2.1 — `ingest` (Phase 1, critique)

- **Commande** : `personalscraper ingest [--dry-run]` ou via `run`
- **Module** : `personalscraper/ingest/ingest.py`
- **Inputs** : qBittorrent (via `QBitClient` ou `build_active_torrent_client`), tracker `paths.data_dir/ingested_torrents.json`, `paths.staging_dir/097-TEMP/`
- **Outputs** : fichiers copiés en 097-TEMP, tracker mis à jour
- **Invariants** :
  - Idempotence : hash déjà tracké → skipped
  - Lockout file `~/.cache/personalscraper/qbit_auth_lockout` protège contre IP-ban qBit
  - `_cleanup_orphan_temps` au start si pas dry-run
- **Events émis** : `ItemProgressed(step="ingest", ...)` (start, copied, failed, etc.) — **10 sites** d'emit dans `ingest.py`
- **Erreurs** :
  - Auth lockout / 403 → `qbit_ip_banned` + log warn + step error
  - Network unreachable → `ApiError(http_status=0)`
  - `error_count > 0` AND 097-TEMP vide → STOP_PROTOCOL au niveau de la skill

### 2.2 — `sort` (Phase 2, critique)

- **Commande** : `personalscraper sort [--dry-run]`
- **Module** : `personalscraper/sorter/` + `personalscraper/sorter/run.py`
- **Inputs** : `097-TEMP/` (ou `find_ingest_dir`), config catégories, naming patterns
- **Outputs** : items déplacés en `001-MOVIES/`, `002-TVSHOWS/`, etc. ; 097-TEMP vidé
- **Invariants** :
  - `sort_fast_skip` si 097-TEMP vide → no-op (DESIGN_CONFORM matrix)
  - Ne crée PAS les `Saison NN/` (c'est `episode_manager.create_season_dirs` au scrape qui le fait)
- **Events** : `ItemProgressed(step="sort", item=name, status=...)` — 5 sites
- **Gate post-sort** : `_check_temp_empty_gate()` log warning si 097-TEMP non-vide après le run réel (non bloquant — items traités au prochain run)

### 2.3 — `process` (Phase 3, composite : clean + scrape + cleanup)

- **Commande** : `personalscraper process [--dry-run]` ou via `run`
- **Module** : `personalscraper/process/run.py` (clean + cleanup), `personalscraper/scraper/run.py` (scrape)
- **Inputs** : catégories triées (001-MOVIES, 002-TVSHOWS), TMDB/TVDB clients, NFOGenerator
- **Outputs** : NFOs Kodi-compliant, artwork, Saison NN/, renaming
- **Invariants** (par sous-étape) :
  - `clean` : `clean_fast_skip` si pas de pollution détectée. Dedup toujours run (léger).
  - `scrape` : `scrape_fast_skip` si tous NFOs valides. Provider lock (TVDB primaire), unmatched-no-rename, drift validator strict (post-provider-ids + post-tech-debt fixes).
  - `cleanup` : suppression dossiers vides / fichiers parasites.
- **Events** : `ItemProgressed(step="clean"|"scrape"|"cleanup", ...)` — process.run émet pour clean+cleanup ; scrape.run émet pour scrape.
- **Erreurs** :
  - `tmdb_id_validation_auth_failure` → OPERATIONAL (rotation clé)
  - `nfo_corrupt_rescrape` → drift detected, re-scrape
  - `episode_unmatched_no_rename` → DESIGN_CONFORM (matrix)

### 2.4 — `enforce` (Phase 4) ⚠️ ABSENT DU MATRIX ACTUEL

- **Commande** : `personalscraper enforce [--dry-run]`
- **Module** : `personalscraper/enforce/run.py`
- **Inputs** : staging (1xx-\* catégories)
- **Outputs** : filenames sanitizés, structure validée, coherence checked
- **Sub-modules** : `file_sanitizer.py`, `structure_validator.py`, `coherence_checker.py`
- **Invariants** : pure validation/sanitization — n'écrit pas hors fichier qu'il corrige
- **Erreurs** : `ItemProgressed(step="enforce", ...)` — pas observé dans le grep events (à vérifier)

### 2.5 — `verify` (Phase 5)

- **Commande** : `personalscraper verify [--dry-run] [--movies-only] [--tvshows-only]`
- **Module** : `personalscraper/verify/run.py` + `personalscraper/verify/checker.py`
- **Inputs** : staging items scrapés
- **Outputs** : (StepReport, dispatchable_list) — la `dispatchable_list` est consommée par `dispatch`
- **Invariants** :
  - 12 checks pour movies, 15 pour TV shows
  - TV `nfo_ids` : TVDB OR TMDB requis (IMDb non requis)
  - Movie `nfo_ids` : TMDB AND IMDb requis (un manquant → WARNING ; les deux → ERROR bloquant)
  - `root_video_files` (TV only) : video file à racine du show alors que tvshow.nfo existe → ERROR bloquant (safety net Unmatched Episode Policy)
  - Items "blocked" PAS dispatchés
- **Events** : `ItemProgressed(step="verify", ...)` (start, valid, blocked) — 3 sites
- **Read-only** : n'écrit jamais

### 2.6 — `trailers` (Phase 6) ⚠️ ABSENT DU MATRIX ACTUEL

- **Commande** : `personalscraper trailers scan|download|verify|purge` (sous-app)
- **Module** : `personalscraper/trailers/cli.py` (4 commandes) + `personalscraper/trailers/step.py` (pipeline integration)
- **Inputs** : library scan + verify result + TMDB / YouTube
- **Outputs** : trailers placés à côté des médias (Plex-conformant : flat pour movies, sub `Trailers/` pour TV)
- **Invariants** :
  - Run après verify, avant dispatch (placement avant move atomique)
  - Bloquant par défaut (configurable)
  - `TrailerStepFailed` raise abort dispatch
- **Events** : `TrailerDownloaded` (event-bus v1 catalog)
- **Erreurs** :
  - YouTube quota → fail-soft per-item
  - Trailer source missing → log warn

### 2.7 — `dispatch` (Phase 7)

- **Commande** : `personalscraper dispatch [--dry-run]`
- **Module** : `personalscraper/dispatch/` (run, \_transfer, media_index, conf/resolver)
- **Inputs** : staging items verified (dispatchable_list)
- **Outputs** : items déplacés vers disks de stockage (replaced/merged/moved)
- **Invariants** :
  - **Move Rules** : movies → `replace`, TV shows → `merge`, new items → disk avec plus d'espace libre (`pick_disk_for`)
  - **rsync flags** : `-a --no-perms --no-owner --no-group` (NTFS via macFUSE)
  - **Staging→commit pattern** : `_tmp_dispatch_{name}/` puis atomic `os.rename`. Crash → tmp dir nettoyé au run suivant.
  - **Merge backup** : `_merge()` utilise `--backup --backup-dir=.merge_backup/` pour rollback per-file.
  - **NFC Unicode normalization** + case-insensitive matching (NTFS) : disque casing wins
  - Standalone : auto-run verify d'abord
- **Events** : `ItemDispatched(item, disk, action, ...)`, `ItemProgressed(step="dispatch", ...)` — 6 sites
- **Erreurs** :
  - `rsync failed` + `Invalid argument` → NTFS illegal char (STOP_PROTOCOL matrix)
  - `No space left on device` → DISK FULL (STOP_PROTOCOL)
  - `_tmp_dispatch_*` orphan → DESIGN_DEVIATION (critique)

---

## 3. Flux connexes

### 3.1 — `library-index` (indexer scan, hors pipeline strict)

- **Commande** : `personalscraper library-index [--mode quick|incremental|enrich|full|verify] [--disk DISK] [--dry-run] [--wait-for-lock S] [--confirm-bulk-change] [--rebuild]`
- **Module** : `personalscraper/indexer/scanner/__init__.py::scan` + `personalscraper/library/scanner.py::scan_library`
- **Modes (ScanMode enum)** : `quick` (Merkle short-circuit), `incremental` (dir-mtime delta), `enrich` (mediainfo/NFO/artwork re-enrich), `full` (walk every file), `verify` (re-stat + escalate mismatches)
- **Hors enum mais existant** : `backfill_ids` (provider-ids) — appelle `run_backfill_ids` directement, pas via le scanner
- **BDD** : `.data/library.db` (SQLite + WAL) — tables `media_item`, `media_file`, `season`, `episode`, `media_release`, `media_stream`, `disk`, `path`, `repair_queue`, `outbox`, `scan_run`, etc.
- **Invariants** :
  - Disk breaker per-disk (`indexer/breaker.py`)
  - Merkle root per-disk pour fast-skip
  - Crash recovery : checkpoint + sigterm handler + budget guard
  - `scan_run` row inserted at start (status=running), updated to ok/failed/aborted at end
  - **C5 bug audit récent** : index re-creation race quand 3+ disk workers fork — `idx_stream_kind_codec already exists`
- **Events** : `LibraryScanCompleted`, `ItemProgressed` per-file

### 3.2 — Connexes maintenance / audit (hors pipeline)

| Commande              | But                                  | Module                                             |
| --------------------- | ------------------------------------ | -------------------------------------------------- |
| `library-status`      | dernier scan + repair queue + outbox | `commands/library/query.py`                        |
| `library-search`      | flex-attr query language             | `commands/library/query.py` + `indexer/query.py`   |
| `library-show ID`     | détails d'un item                    | idem                                               |
| `library-report`      | stats globales + suggestions         | `commands/library/analyze.py`                      |
| `library-validate`    | validation NFO/artwork/naming        | `commands/library/maintenance.py`                  |
| `library-verify`      | re-stat fichiers indexés             | idem                                               |
| `library-repair`      | drain de la repair queue             | idem                                               |
| `library-clean`       | suppression `.actors/`, junk         | idem                                               |
| `library-reconcile`   | détection drift index↔FS             | `commands/library/audit.py`                        |
| `library-ghost-audit` | NTFS ghost dirents                   | idem                                               |
| `library-relink`      | relink `media_file` orphan           | idem                                               |
| `library-analyze`     | ffprobe deep scan                    | `commands/library/analyze.py`                      |
| `library-recommend`   | re-download recommendations          | idem (⚠️ utilise legacy flat IDs per audit récent) |
| `library-rescrape`    | re-scrape ciblé via TMDB/TVDB        | idem (⚠️ porte le DEV #2 vector encore vivant)     |

### 3.3 — `info`, `torrents-list`, `init-config`

- `info` : version + config paths + disk status (`commands/info.py`)
- `torrents-list` : inventaire qBit completed (`commands/pipeline.py`, ajouté en tech-debt P1)
- `init-config` : génération `config/` depuis `config.example/` (`commands/config.py`)

---

## 4. Invariants transversaux

### 4.1 — Locking

- **`paths.data_dir/pipeline.lock`** : pris au CLI level (`acquire_lock` / `release_lock`) AVANT toute commande de pipeline. Une seule instance pipeline à la fois.
- **Indexer writer lock** : géré via WAL PRAGMAs + flock (`indexer/db.py`). `--wait-for-lock S` configurable.

### 4.2 — Dry-run

- Toutes les commandes pipeline ET maintenance acceptent `--dry-run`
- Convention : log `*_would_*` au lieu de l'action réelle
- Idempotent par construction

### 4.3 — EventBus

- **Sole emit substrate** depuis event-bus v0.14.0 — pas de canal callback parallèle
- **AppContext boundary** : EventBus construit AU CLI, jamais imports internes
- **13 events v1** catalogués dans `personalscraper.events` (eagerly imported)
- **ContextVar** `current_correlation_id` pour bind les events sub-step
- **Subscribers** : RichConsole, Telegram, DebugLog, plus les internes (CircuitBreaker emit, TrailerStateSubscriber, etc.)

### 4.4 — Fast-skip / idempotence

- `scrape_fast_skip` quand tous NFOs valides
- `clean_fast_skip` quand pas de pollution
- `sort_fast_skip` quand 097-TEMP vide
- `cleanup_fast_skip` quand pas de junk
- Re-run produit no-op si rien à faire

### 4.5 — Crash recovery

- `_recover_from_previous_run()` au début de `pipeline.run()` (sauf dry-run)
- Indexer : checkpoint + sigterm handler + budget guard
- Dispatch : `_tmp_dispatch_*` orphans cleaned au run suivant

### 4.6 — Healthcheck dead-man's switch

- `ping_start` au début de run
- `ping_success` sur completion clean uniquement
- `ping_fail` sur tout autre exit (TrailerStepFailed, exception, typer.Exit)
- Fail-soft : healthchecks non joignable n'abort pas le pipeline

### 4.7 — `pipeline_outcome` semantic

- Variable `pipeline_outcome` set à "success" UNIQUEMENT sur clean completion
- Toute autre sortie laisse `None` → finally fire `ping_fail`

---

## 5. Écarts code-vs-docs (alimente l'item 4 — MAJ skill)

### 5.1 — Matrix skill pipeline-monitor : 5 étapes au lieu de 9 (StepReports)

Le matrix actuel à `.claude/skills/pipeline-monitor/references/design-conformity-matrix.md` ne couvre que :

- INGEST, SORT, PROCESS (agrégé), VERIFY, DISPATCH

**Manquent** :

- **ENFORCE** (phase 4 du pipeline) — étape complète, jamais évoquée dans le matrix
- **TRAILERS** (phase 6) — étape complète, jamais évoquée
- **Décomposition de PROCESS** en `clean` / `scrape` / `cleanup` (3 StepReports séparés au final)

### 5.2 — Docstring `personalscraper run` obsolète

```python
"""Run full pipeline (ingest -> sort -> process -> verify -> dispatch)."""
```

Mention ni `enforce`, ni `trailers`. À mettre à jour pour matcher la réalité.

### 5.3 — Architecture.md cohérent mais skill-monitor pas synchro

`architecture.md` §Workflow Pipeline expose les 9 étapes correctement. Mais ce document n'est pas la source que la skill consulte — la skill a son propre matrix.

### 5.4 — `library-index` modes : 5 ScanMode + 1 hors-enum (backfill_ids)

- L'enum `ScanMode` (`indexer/scanner/_types.py`) liste 5 modes.
- Le SQL CHECK constraint sur `scan_run.mode` accepte aussi `'repair'` (forward-compat, non implémenté).
- `backfill_ids` (provider-ids) est appelable mais hors `ScanMode` ET hors CLI (audit récent — C2).

### 5.5 — Backfill auto post-process non implémenté

DESIGN provider-ids §2-7 promettait un auto-trigger backfill après `process` quand gap détecté. Aucune trace dans `pipeline.py` ni dans `process/run.py`.

### 5.6 — Pas d'integration test "scrape → library-scan"

Conséquence audit pipeline-monitor : tous les bugs (DEV #2, library scanner ignore tvdb_id, season columns 0, etc.) ont >90% line coverage mais aucun test E2E n'aurait pu les attraper.

### 5.7 — Matrix nomenclature "TMDB Auto-Recovery" / "Provider Lock" / "Unmatched Episode Policy"

Le matrix mentionne ces contrats en `process` section. Code post-tech-debt-P2 a restauré ces contrats (avaient été perdus en `192bad3`). Matrix doit confirmer qu'ils sont actifs et matcher les events `provider_lock_engaged` / `episode_unmatched_no_rename` réellement émis.

### 5.8 — Étape `enforce` jamais cartographiée

Aucune section du matrix actuel ne couvre `enforce`. Sub-modules :

- `file_sanitizer.py` — sanitization filenames
- `structure_validator.py` — validation structure dirs
- `coherence_checker.py` — checks transverses

Les outputs normaux et déviations doivent être documentés.

### 5.9 — Trailers jamais cartographié dans le matrix

- Sub-app `trailers` avec 4 commandes
- Logic `step.py` invoqué au sein de `pipeline.run()`
- Patterns design-conform / déviation à formaliser (quota YouTube, missing source, etc.)

---

## 6. Liste des invariants vérifiables (alimentent item 4)

Idées de **checks transverses** que la skill pourrait ajouter :

1. **Pipeline lock present iff command running** — un `pipeline.lock` qui survit après tout run est un orphan.
2. **097-TEMP empty après sort réel non-fast-skip** — sinon items perdus.
3. **Aucun `_tmp_dispatch_*` après dispatch réussi** — sinon rsync interrompu.
4. **Aucun `_tmp_ingest_*` après ingest réussi** — idem côté ingest.
5. **Stale `scan_run` running > 6h** — déjà fixé en tech-debt P10.
6. **Aucun `media_item.dispatch_path` qui n'existe pas sur disque** — drift FS↔BDD (déjà couvert par `library-reconcile`).
7. **Aucun item staging valide qui n'est PAS dans dispatchable_list après verify** — bug verify.

---

## 7. Output

Cette carto est la **source de vérité** pour les items 3 (brainstorm MAJ skill), 4 (MAJ skill), 5 (run pipeline-monitor). Le matrix actuel doit être étendu pour couvrir les 9 StepReports + enforce + trailers + flux connexes.

---

## 8. Compléments (angles initialement loupés)

Section ajoutée après revue utilisateur. Couvre les 14 angles qui n'étaient pas dans la première passe.

### 8.1 — Décomposition réelle de `PROCESS` (clarification dedup)

Le matrix dit `clean = reclean + dedup`. C'est confirmé : `personalscraper/process/run.py:122` exécute :

```
clean: si polluted folders → reclean + dedup ; sinon → dedup seul (lightweight)
scrape: orchestrator scraper → TMDB/TVDB
cleanup: suppression dossiers vides
```

**3 StepReports** au final pour PROCESS (`clean`, `scrape`, `cleanup`). Le "reclean" et "dedup" sont DES SOUS-OPÉRATIONS de `clean`, pas des StepReports séparés. Le matrix actuel est correct sur ce point ; ma première passe avait sur-décomposé.

`_revert_unmatched_recleans()` : helper qui annule les renames de reclean dont le scrape n'a pas matché (évite faux-positifs après reclean).

### 8.2 — `_recover_from_previous_run` — 3 actions de récupération

Au tout début de `pipeline.run()` (avant INGEST, sauf dry-run) :

1. **Clean `_tmp_dispatch_*`** sur TOUS les storage disks — orphans de dispatch interrompu
2. **Expire qBit auth lockout** si `>1h` — fichier `~/.cache/personalscraper/qbit_auth_lockout`
3. **Clean `.ingest_tmp_*`** dans staging — orphans de ingest interrompu

Le matrix devrait noter cette phase de récupération (n'est pas un StepReport mais une phase de pré-run).

### 8.3 — Outbox indexer

- **Tables** : `index_outbox` (events queue) + `repair_queue` (work queue).
- **Outbox drain** (`indexer/outbox/_drain.py`) : drainer asynchrone qui propage les `media_item` writes vers les disques (write-through pattern). Appelé via `drain()` et `drain_if_present()`.
- **Write-through** : `scraper.NFOGenerator` + `ArtworkDownloader` écrivent dans outbox via `outbox/_publish.py`, puis le drainer propage.
- **Lifecycle outbox event** : pending → done.

### 8.4 — Repair queue lifecycle

- **Schema** : `status IN ('pending', 'running', 'done', 'failed')`
- **Enqueue** : `indexer/repair.py::enqueue_repair` et `indexer/drift.py::enqueue_repair` (dédupliqués via `idx_repair_pending_dedup` partial UNIQUE index)
- **Drain** : `indexer/repair.py::drain` consomme la queue avec budget (CLI `library-repair`)
- **Source d'entrées** : `drift.reconcile_file` (file mismatch detected), `reconcile.detect_*` (drift FS↔BDD)

### 8.5 — API orchestration au sein du pipeline

Les API clients (TMDB / TVDB) sont **construits dans le scraper orchestrator** (`scraper/orchestrator.py:80-98`) au moment où le scrape step démarre :

```python
tmdb_policy = TMDBClient.policy(settings.tmdb_api_key, circuit=cb_policy)
self._tmdb = TMDBClient(transport=HttpTransport(tmdb_policy, event_bus=event_bus), ...)
self._tvdb = TVDBClient(api_key=settings.tvdb_api_key, circuit=cb_policy, event_bus=event_bus)
```

- Chaque client a son **CircuitPolicy** (seuils du `thresholds_config`).
- L'**HttpTransport** est partagé entre clients (mais avec policies dédiées).
- L'**event_bus** est plumbé dans les transports — circuit breaker emit `CircuitBreakerOpened/Closed/HalfOpened`.
- **OMDb / Trakt** : construits au point d'usage (IMDb façade, RT façade) — pas un client central comme TMDB/TVDB.

### 8.6 — Scheduling launchd

Fichiers à `docs/reference/launchd/` :

- **`personalscraper-index-quick.plist`** : nightly 03:30 — `library-index --mode quick` (Merkle short-circuit, sub-minute si rien changé)
- **`personalscraper-index-enrich.plist`** : enrich mode (mediainfo + NFO + artwork ré-enrichi)
- **`personalscraper-index-rotate.plist`** : log rotation
- **`index-rotate.sh`** : script de rotation

**Le pipeline `personalscraper run` n'est PAS automatisé via launchd** dans le repo — c'est l'opérateur qui le lance. Seul l'indexer est automatisé.

### 8.7 — Flex attributes (`item_attribute` table)

3 clés dispatch importantes (`indexer/repos/item_repo.py`) :

- `_ATTR_DISPATCH_DISK = "dispatch_disk"` (config-level disk id, ex: `"disk_2"`)
- `_ATTR_DISPATCH_PATH = "dispatch_path"` (chemin absolu sur disque)
- `_ATTR_DISPATCH_NORM_TITLE = "dispatch_normalized_title"` (NFC + lowercase + stripped pour lookup)

**Set par** :

- `dispatch/media_index.py` lors de l'insertion d'un nouvel item (au moment du dispatch)
- `library/scanner.py::_upsert_item` lors d'un scan complet

**Lu par** : `trailers/` (cross-disk lookup), `library-search` (filtres `disk:`), `dispatch` (re-dispatch ciblé).

### 8.8 — `library-index` flags spéciaux

- **`--rebuild`** : quarantine la DB corrompue (`library.db.corrupt-{timestamp}`), recrée fresh + lance scan complet stage A.
- **`--confirm-bulk-change`** : bypass le **bulk-restore freeze guard**. Le scan quick refuse de continuer si le Merkle delta dépasse un seuil — sécurité contre un restore complet de disque (qui ferait apparaître tout comme "nouveau"). Le flag force la prise en compte.
- **`--wait-for-lock S`** : attendre S secondes que le writer lock se libère (sinon échec immédiat si lock pris).

### 8.9 — Fingerprint + Merkle

- **`fingerprint.py`** :
  - `fingerprint_tier1(stat)` : `(size, mtime_ns, inode)` — fast path d'identification
  - `is_racy(file_mtime_ns, scan_started_at_ns, window_ns)` : détection mtime "racy" (mtime trop proche du scan start → re-stat plus tard)
  - `oshash(path)` : fingerprint binaire (16-char hex)
  - `xxh3_partial(path, partial_bytes=1MB)` : fingerprint partiel (anti-collision)
- **`merkle.py`** :
  - `FileFingerprint` (dataclass)
  - `DiskMountStatus` enum (mounted/unmounted/mismatched)
  - `verify_disk_mounted` (side-effect-free check)
  - Exceptions : `BootstrapError`, `DiskUnmountedError`, `DiskMismatchError`, `DiskBulkChangeDetected`
- **Sentinel UUID** : chaque disque a un fichier sentinel avec UUID — vérifié avant scan pour éviter de scanner un autre disque monté sur le même mount point.

### 8.10 — Drift et reconcile

- **`drift.py`** : niveau fichier
  - `clamp_mtime_ns` : règle racy-mtime
  - `enqueue_repair` : pousse dans repair_queue
  - `reconcile_file` : compare stat actuel vs DB row
  - `detect_rename` : reconnaît file rename (oshash inchangé, path changé)
  - `mark_missed_files` : marque les fichiers absents du scan en cours
  - `apply_soft_deletes` : N-strikes soft-delete (un fichier manquant N scans → soft-deleted)

- **`reconcile.py`** : niveau item
  - `detect_merkle_drift` : Merkle root divergent
  - `detect_dispatch_path_missing` : dispatch_path pointe vers chemin absent
  - `detect_enrich_stale` : items dont l'enrich est obsolète
  - `detect_release_orphans` : releases sans item associé
  - `detect_season_count_drift` : season.episode_count divergent du compte réel
  - `detect_items_without_files` : items sans aucun media_file lié
  - `reconcile()` : orchestrateur global → produit un `ReconcileReport`

### 8.11 — Subscribers internes au pipeline

Externes (déjà mentionnés) : `RichConsoleSubscriber`, `TelegramSubscriber`, `DebugLogSubscriber`.

**Internes** (auto-subscribed lors de construction) :

- `CircuitBreaker` lui-même émet `CircuitBreakerOpened/Closed/HalfOpened` quand il transitionne — pas un subscriber, c'est un émetteur.
- Pas de TrailerStateSubscriber explicite — le trailer state est tracké dans `trailers/state.py` (sub-module avec sa propre lifecycle exception `TrailerStepFailed`).

**Note importante** : un emit qui n'a pas de subscriber compilé est SILENCIEUSEMENT DROPPED. C'est le contrat du bus typed (no error si pas de listener).

### 8.12 — Convention logging (réf `docs/reference/logging.md`)

3 canaux :

- **Structured log** (`structlog` via `get_logger("<module>")`) : tout ce qui est observable — errors, progress, decisions. `log.info("event_name", key=value)` — clé = snake_case stable (treated as public API, rename = breaking).
- **CLI UI** (`state["console"].print(...)`) : output user-facing — headers, tables, summaries.
- **Interactive prompt** (`typer.prompt/confirm/echo`) : input TTY.

**Event naming** : `<module_prefix>_<event>` (ex: `ingest_*`, `dispatch_*`, `tmdb_*`). Past-tense préféré (`_moved_ok`, `_login_failed`). Stability garantie via `tests/test_event_names.py` (rename → breaking, doit être déclaré).

### 8.13 — `media_release` + `release_linker.py`

- **Table `media_release`** : représente une "release" d'un média (quality + edition + primary_lang). Une release peut être attachée à un `item_id` (movie/show level) OU à un `episode_id` (per-episode release). UNIQUE(item_id, episode_id, quality, edition, primary_lang).
- **`release_linker.py`** :
  - `find_item_for_path(conn, abs_dir)` — résout dir → (item_id, kind, year)
  - `get_or_create_season/episode` — upsert idempotent
  - `get_or_create_default_release` — release "default" (NULL quality/edition/lang) pour fallback
  - `link_file_to_release(conn, file_id, abs_path)` — attribue un file_id à une release
  - `recompute_season_episode_counts` — recalcule `season.episode_count` (utile après drift)

**Rôle dans le pipeline** : appelé pendant le scan indexer pour relier les `media_file` aux `media_item` via les `media_release`.

### 8.14 — Config overlay

**Layout v2 (split config)** dans `config/` :

```
config/                    ← gitignored, machine-specific
  config.json5             ← master: déclare overlays + config_version
  paths.json5              ← paths.*
  disks.json5              ← disks[]
  categories.json5         ← custom_categories, categories{}, category_rules[]
  patterns.json5           ← staging_dirs[]
  encoding.json5           ← library.*
  scraper.json5            ← scraper, ingest, fuzzy_match
  trailers.json5           ← trailers.*
  indexer.json5            ← indexer.*
  thresholds.json5         ← thresholds.*
  local.json5              ← overrides last-wins (gitignored)
```

**Tracked equivalent** : `config.example/` même structure, valeurs placeholder.

**Merge order** : le master `config.json5` déclare la liste des overlays, lus dans l'ordre, dernier l'emporte. `local.json5` est appliqué en dernier.

**Validation** : Pydantic strict mode (`extra='forbid'`) — d'où le bug pipeline-monitor récent où `episode_scraping_policy` (dropped en `192bad3`) bloquait le boot.

**Métadonnées API** : `metadata.json5` → `MetadataConfig` + ses sub-models (`MetadataProviderConfig`, `MetadataPriorities`, `MetadataDefaults`, `MetadataEpisodeScrapingPolicy`).

---

## 9. Bilan complémentaire — implications pour la skill

Les 14 angles ajoutent à la to-do du matrix (item 4) :

| Angle | Impact pour la skill                                                                        |
| ----- | ------------------------------------------------------------------------------------------- |
| 8.1   | Confirme matrix PROCESS = 3 StepReports (clean composite, scrape, cleanup)                  |
| 8.2   | Ajouter phase "pré-run recovery" au matrix (`_tmp_*` orphans, qBit lockout, ingest tmp)     |
| 8.3   | Outbox drain + `library-repair` — checks transverses possibles                              |
| 8.4   | Repair queue lifecycle — state machine documentable                                         |
| 8.5   | API circuit breakers émis sur le bus — matrix peut subscribe et logger                      |
| 8.6   | launchd index-quick — orchestre l'indexer hors pipeline, à mentionner dans la skill         |
| 8.7   | Flex attributes `dispatch_*` — invariants verifiables (path existe, normalized_title match) |
| 8.8   | `--rebuild` / `--confirm-bulk-change` — flags spéciaux à ne pas activer accidentellement    |
| 8.9   | Sentinel UUID drift = `DiskMismatchError` — STOP_PROTOCOL candidate                         |
| 8.10  | `library-reconcile` produit `ReconcileReport` → checks supplémentaires                      |
| 8.11  | Bus emit sans subscriber = silently dropped — matrix doit lister subscribers attendus       |
| 8.12  | Event naming = public API — la skill peut grep les events attendus                          |
| 8.13  | Release linker — joint files↔items, drift potentiel à monitorer                             |
| 8.14  | Config Pydantic strict — toute extra-input = boot failure → STOP_PROTOCOL                   |
