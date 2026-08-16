# Plan d'intervention - coherence configuration projet

Date: 2026-05-03

Objectif: supprimer les restes des anciennes configurations et realigner le code, les exemples, la documentation et les artefacts runtime autour de la configuration active. Cette intervention doit etre precedee d'une deuxieme passe de verification avant toute correction.

Contraintes demandees:

- Aucune reference active a l'ancienne configuration.
- Aucune gestion de migration ou de retrocompatibilite pour les anciennes configurations.
- Aucun code mort.
- Aucune documentation ni commentaire obsoletes.
- Aucun chemin ou dossier hardcode lorsqu'une valeur doit venir de la configuration.
- Avant les corrections: produire un resume de ce qui va etre modifie et attendre validation.

## Etat initial observe

Le depot etait propre au moment de l'ecriture de ce plan. Un audit precedent avait signale des modifications locales dans `personalscraper/dispatch/dispatcher.py` et `personalscraper/dispatch/run.py`; elles ne sont plus visibles dans `git status --short` lors de la creation du plan.

Les artefacts runtime locaux non suivis par git existent ou ont ete observes pendant l'audit:

- `.data/.legacy-bak/*`
- `.data/*.pre-migration-*.bak`
- `.data/library.db*`
- `trailers_cache.json`
- `youtube_quota.json`
- `__pycache__/`
- `.mypy_cache/`

Ces artefacts ne doivent pas etre traites comme du code source, mais ils doivent etre verifies dans `.gitignore` et eventuellement nettoyes localement apres validation explicite.

## Inventaire des problemes trouves

### 1. Ancien format de config encore supporte

Fichiers concernes:

- `personalscraper/conf/loader.py`
- `personalscraper/cli.py`
- `tests/conf/test_loader.py`
- `tests/indexer/test_cli.py`
- `tests/e2e/test_indexer_partial_migration.py`
- Documentation racine et reference qui mentionne `config.json5` monolithique ou la migration.

Constats:

- `resolve_config_path()` conserve un fallback vers `./config.json5`.
- `DEFAULT_LEGACY_CONFIG_PATH` et `DEFAULT_CONFIG_PATH` existent encore.
- `load_config()` accepte un fichier JSON5 unique, le valide et emet une `DeprecationWarning` au lieu de refuser.
- Le texte CLI `--config` mentionne encore un fichier legacy v1.
- Des tests couvrent encore `config migrate-to-v2`, les warnings v1 et la migration partielle.

Decision cible:

- Ne plus accepter le format v1 monolithique.
- Ne plus exposer de constante legacy.
- `--config` doit pointer vers un dossier de configuration split uniquement, sauf decision contraire explicite.
- Supprimer les tests de migration v1 ou les convertir en tests d'erreur claire.

### 2. Champs migres encore presents dans `Settings`

Fichier concerne:

- `personalscraper/config.py`

Constats:

- Le module declare que `Settings` ne contient que secrets et credentials.
- Les champs suivants y sont encore presents pour retrocompatibilite:
  - `scraper_language`
  - `scraper_fallback_language`
  - `scraper_prefer_local_title`
  - `min_free_space_staging_gb`
  - `min_free_space_disk_gb`
  - `library_preferences_file`
- Plusieurs tests instancient encore `Settings(...)` avec ces champs ou les mutent directement.

Decision cible:

- Retirer ces champs de `Settings`.
- Adapter les tests pour modifier `Config.scraper`, `Config.thresholds` ou `Config.library`.
- Verifier que le code production lit deja bien `Config` et non `Settings` pour ces valeurs.

### 3. Champs de schema reserves ou non consommes

Fichier principal:

- `personalscraper/conf/models.py`

Exemples observes:

- `DiskConfig.spotlight_enabled`
- `TrailersYoutubeApiConfig.cache_ttl_days`
- `TrailersYtdlpConfig.default_search`
- `TrailersPlacementConfig.movie_pattern`
- `TrailersPlacementConfig.tvshow_pattern`
- `TrailersSeasonsConfig.language_fallback`
- `TrailersSeasonsConfig.search_query_format`
- `TrailersConfig.bot_detected_max_consecutive_attempts`
- `IndexerScanConfig.nightly_mode`
- `IndexerScanConfig.racy_window_seconds`
- `IndexerScanConfig.sequential_read_hint`
- `IndexerFingerprintConfig.oshash`
- `IndexerFingerprintConfig.xxh3_partial_bytes`
- `IndexerFingerprintConfig.compute_xxh3_on_racy`
- `IndexerMediainfoConfig.library_path`
- `IndexerMediainfoConfig.extract_streams`
- `IndexerMediainfoConfig.min_size_mb`
- `IndexerMediainfoConfig.parse_speed`
- `IndexerMediainfoConfig.defer_to_enrich`
- `IndexerDriftConfig.merkle_per_disk`
- `IndexerDriftConfig.verify_disks_each_scan`
- `IndexerDriftConfig.sentinel_filename`
- `IndexerSpotlightConfig.probe_at_startup`
- `IndexerRepairConfig.queue_drain_on_scan_finish`
- `IndexerRepairConfig.max_repair_seconds_per_drain`
- `IndexerLogConfig.scan_event_retention_days`

Constats:

- Plusieurs docstrings disent explicitement "Reserved", "not consumed", "no runtime effect" ou "hardcoded".
- Certains champs sont presents dans `config.example/indexer.json5` et donnent l'impression d'etre configurables.
- Certains commentaires indiquent que le runtime utilise encore une constante hardcodee au lieu de la config.

Decision cible:

- Pour chaque champ: choisir entre suppression du schema ou cablage runtime reel.
- Vu la demande "pas de code mort", supprimer les champs non consommes sauf si le cablage est immediat et justifie.
- Mettre a jour `config.example/*`, tests de modele et documentation.

### 4. Commandes et shims legacy encore actifs

Fichiers concernes:

- `personalscraper/commands/library.py`
- `personalscraper/dispatch/media_index.py`
- `personalscraper/dispatch/disk_scanner.py`
- `personalscraper/trailers/placement.py`
- `personalscraper/pipeline.py` et tests si `step_overrides` legacy est encore conserve.

Constats:

- `library-scan` existe encore, marque deprecated, et redirige vers l'indexer.
- `MediaIndex` garde une API compatible avec l'ancien index JSON (`load`, `save`, `index_path` legacy).
- `MediaIndex` detecte encore `media_index.json` pour logger un warning.
- `rebuild()` retombe encore sur le nom du dossier comme `category_id` "for backward compatibility".
- `find_existing_trailer()` cherche encore l'ancien chemin TV show `{show}-trailer.ext`.
- `dispatch/disk_scanner.py` mentionne `choose_disk()` comme shim de compatibilite.

Decision cible:

- Supprimer `library-scan` si aucun appel externe actif n'est requis.
- Supprimer les no-op shims `load()` / `save()` si les appelants sont adaptes.
- Ne plus detecter ni mentionner `media_index.json`.
- Supprimer les fallbacks de placement trailer legacy.
- Remplacer les shims de choix disque par l'API config actuelle.

### 5. Documentation et commentaires obsoletes

Fichiers observes:

- `MANUAL.md`
- `CONFIGURATION.md`
- `README.md`
- `ROADMAP.md`
- `docs/reference/*`
- `docs/features/arch-cleanup/*`
- `docs/superpowers/*`
- Commentaires dans le code cites ci-dessus.

Constats:

- `MANUAL.md` contient une section "Migrating from <= 0.3.0".
- `MANUAL.md` contient "Commandes Claude Code archivees" et "Scripts legacy".
- `CONFIGURATION.md` documente d'anciennes variables d'environnement retirees.
- Plusieurs docs mentionnent encore `library_scan.json`, `media_index.json`, v1 config, deprecation/removal schedule ou migration.
- Les archives sous `docs/archive/**` contiennent volontairement de l'historique; il faudra decider si elles sont hors perimetre ou si la demande impose un nettoyage global.

Decision cible:

- Nettoyer les docs actives racine/reference.
- Decider explicitement du sort de `docs/archive/**`.
- Supprimer les commentaires de code qui decrivent des migrations, du legacy ou des champs reserves.

### 6. Chemins et dossiers hardcodes

Fichiers observes:

- `config.example/disks.json5`
- `config.example/paths.json5`
- `config.example/indexer.json5`
- `MANUAL.md`
- `INSTALLATION.md`
- `CLAUDE.md`
- `scripts/install-launchd.sh`
- `com.personalscraper.pipeline.plist.template`
- Tests e2e avec `/Volumes/...`, `/mnt/...`, `/tmp/...`
- `personalscraper/conf/models.py` pour le rejet de `/Volumes/`

Constats:

- Les exemples utilisent `/path/to/...`, `/Volumes/...`, `~`.
- Le modele indexer rejette `/Volumes/` explicitement, ce qui est une hypothese macOS hardcodee.
- Les tests utilisent des chemins synthetiques (`/mnt/DiskA`, `/fake/config.json5`, `/tmp/...`), probablement acceptables en fixture mais a verifier.
- Les scripts launchd utilisent volontairement `$HOME/Library/LaunchAgents`; cela peut etre un chemin systeme attendu, pas forcement un probleme.

Decision cible:

- Distinguer chemins systeme legitimes, fixtures de test et chemins applicatifs configurables.
- Remplacer les chemins applicatifs par des placeholders neutres ou des valeurs derivees de config.
- Verifier que les chemins de runtime viennent de `Config.paths`, `Config.disks` ou variables d'environnement de secrets.

### 7. Config example incoherente avec le modele

Fichiers concernes:

- `config.example/categories.json5`
- `config.example/indexer.json5`
- `config.example/trailers.json5`
- `personalscraper/conf/models.py`

Constats:

- `categories.json5` commente `applies_to: "movies"` alors que le modele accepte `movie`, `tv`, `both`. Le modele normalize encore `"movies"` pour compatibilite.
- `indexer.json5` expose beaucoup de champs reserves ou non consommes.
- Les commentaires des exemples de config presentent certains champs comme actifs alors que le modele dit qu'ils ne le sont pas.

Decision cible:

- Corriger `applies_to` vers `movie`.
- Supprimer la normalisation `"movies"` si plus aucune retrocompatibilite n'est souhaitee.
- Supprimer ou cabler les champs reserves dans les exemples.

## Plan de correction propose

### Phase 0 - Deuxieme passe de verification avant correction

Objectif: confirmer chaque surface avant modification.

Actions:

- Relancer `rg` sur `legacy|migration|migrate|compat|backward|deprecated|obsolete|Reserved|hardcoded|media_index.json|library_scan.json|config.json5.v15|DEFAULT_LEGACY_CONFIG_PATH`.
- Relancer la recherche de chemins absolus ou home: `/Users/`, `/Volumes/`, `/mnt/`, `/tmp/`, `~/`, `.legacy-bak`.
- Lire les tests touches avant suppression pour distinguer test historique et contrat actuel.
- Produire un resume court des corrections qui seront lancees.
- Attendre validation utilisateur avant modifications.

Livrable:

- Resume de lancement des corrections avec fichiers cibles et risques.

### Phase 1 - Supprimer le support config v1

Actions:

- Modifier `resolve_config_path()` pour resoudre uniquement le dossier split `./config` ou `PERSONALSCRAPER_CONFIG`.
- Refuser un chemin fichier pour `--config`, sauf si on choisit de supporter uniquement un fichier master dans un dossier.
- Supprimer `DEFAULT_LEGACY_CONFIG_PATH` et `DEFAULT_CONFIG_PATH`.
- Supprimer le bloc `DeprecationWarning` et le chargement monolithique dans `load_config()`.
- Supprimer ou adapter les tests `migrate-to-v2`, v1 loader et partial migration.
- Nettoyer les messages CLI et docs associees.

Verification:

- Tests `tests/conf/test_loader.py`.
- Tests CLI config pertinents.
- `personalscraper --help` si necessaire.

### Phase 2 - Retirer la config migree de `Settings`

Actions:

- Supprimer les champs non secrets de `Settings`.
- Adapter les tests pour utiliser `Config`.
- Verifier les helpers de tests qui construisent `Settings(min_free_space_...)`.
- Supprimer les assertions de `tests/test_config.py` sur les champs retires.

Verification:

- `tests/test_config.py`
- `tests/ingest/test_ingest.py`
- `tests/integration/*`
- `tests/scraper/*` concernes.

### Phase 3 - Eliminer les champs de schema morts

Actions:

- Pour chaque champ "Reserved", decider suppression ou cablage.
- Mettre a jour `Config` models, `config.example`, docs reference et tests modele.
- Supprimer les validateurs devenus inutiles (`TrailersPlacementConfig` si les patterns sont retires).
- Supprimer les commentaires qui justifient une future compatibilite.

Verification:

- `tests/conf/test_models.py`
- `tests/conf/test_example_config.py`
- Tests trailers/indexer selon champs touches.

### Phase 4 - Supprimer shims et commandes legacy

Actions:

- Supprimer `library-scan` ou le rendre indisponible selon decision.
- Supprimer les imports/tests qui attendent sa presence.
- Adapter `MediaIndex` pour prendre directement le chemin DB configure, sans `index_path` JSON legacy.
- Supprimer `load()` et `save()` si plus aucun appelant ne les utilise.
- Supprimer la detection `media_index.json`.
- Supprimer fallback trailer TV show legacy.
- Revoir `dispatch/disk_scanner.py` pour retirer le shim `choose_disk()` si non utilise.

Verification:

- `tests/test_cli.py`
- `tests/dispatch/test_media_index.py`
- `tests/integration/test_dispatch_*`
- `tests/trailers/test_placement.py`
- `tests/trailers/*`.

### Phase 5 - Nettoyer documentation active

Actions:

- Nettoyer `README.md`, `CONFIGURATION.md`, `MANUAL.md`, `INSTALLATION.md`.
- Nettoyer `docs/reference/*` lie a config, indexer, commands, pipeline.
- Supprimer les sections de migration et legacy actives.
- Decider explicitement si `docs/archive/**` reste preserve ou est nettoye.

Verification:

- `rg` final sur les termes interdits hors archives si archives conservees.
- Lecture rapide des guides racine.

### Phase 6 - Chemins hardcodes et exemples

Actions:

- Remplacer les chemins applicatifs hardcodes par des chemins derives de config ou placeholders neutres.
- Revoir la validation `/Volumes/` du `db_path`: soit la rendre configurable/portable, soit justifier comme contrainte systeme documentee.
- Nettoyer `config.example` pour ne montrer que des valeurs coherentes et portables.
- Garder les chemins systeme legitimes dans les scripts launchd si necessaire.

Verification:

- `rg` final sur `/Users/|/Volumes/|/mnt/|/tmp/|~/`.
- Tests de validation config.

### Phase 7 - Nettoyage artefacts locaux

Actions:

- Confirmer avec l'utilisateur avant suppression d'artefacts locaux.
- Nettoyer uniquement les caches/backups non suivis et non necessaires:
  - `__pycache__/`
  - `.mypy_cache/`
  - `.data/.legacy-bak/`
  - `.data/*.pre-migration-*.bak`
  - caches racine `trailers_cache.json`, `youtube_quota.json`
- Ne jamais supprimer `library.db` ou autres etats actifs sans validation explicite.

Verification:

- `git status --short`
- `git ls-files` pour confirmer qu'aucun fichier source n'a ete retire par erreur.

## Commandes d'audit a relancer avant correction

```bash
rg -n --hidden --glob '!.git/**' --glob '!**/__pycache__/**' --glob '!.mypy_cache/**' --glob '!.venv/**' --glob '!.venv310/**' "legacy|ancien|ancienne|migration|migrate|compat|backward|retro|deprecated|obsolete|Reserved|hardcod|media_index\\.json|library_scan\\.json|DEFAULT_LEGACY_CONFIG_PATH|config\\.json5\\.v15"
```

```bash
rg -n --hidden --glob '!.git/**' --glob '!**/__pycache__/**' --glob '!.mypy_cache/**' --glob '!.venv/**' --glob '!.venv310/**' "/Users/|/Volumes/|/mnt/|/tmp/|~/|\\.legacy-bak"
```

```bash
rg -n "settings\\.(scraper_language|scraper_fallback_language|scraper_prefer_local_title|min_free_space_staging_gb|min_free_space_disk_gb|library_preferences_file)|\\b(scraper_language|scraper_fallback_language|scraper_prefer_local_title|min_free_space_staging_gb|min_free_space_disk_gb|library_preferences_file)\\b" personalscraper tests
```

```bash
rg -n "Reserved|not currently consumed|no runtime effect|hardcoded|backward compatibility|compatibility shim|deprecated" personalscraper config.example tests docs README.md CONFIGURATION.md MANUAL.md
```

## Gate avant corrections

Avant toute correction, produire un resume avec:

- Les fichiers qui seront modifies.
- Les suppressions de schema/CLI/doc prevues.
- Les tests qui seront adaptes ou supprimes.
- Les risques de casse fonctionnelle.
- Les artefacts locaux qui seront ignores ou proposes au nettoyage.

Les corrections ne doivent commencer qu'apres validation explicite.
