# Config Dead-Fields Matrix

Audit strict des champs de configuration marques `Reserved`, non consommes, ou
documentes comme sans effet. La decision est prise sur le chemin complet du
modele, pas sur le nom court du champ.

## Regle De Decision

- `KEEP`: lu par le runtime ou valide un invariant utile consomme ailleurs.
- `REMOVE`: aucune lecture runtime, uniquement schema/exemple/tests/docs.
- `WIRE LATER`: comportement souhaitable mais hors correction de coherence; le
  champ reste supprime tant qu'il n'est pas effectivement lu.

## Library Preferences

| Champ | Usages trouves | Decision | Raison |
| --- | --- | --- | --- |
| `LibraryConfig.audio.profile_priority` | `library/recommender.py` | KEEP | Classement audio reel. |
| `LibraryConfig.audio.min_channels` | schema/exemples/tests seulement | REMOVE | Aucun scoring ni validation runtime ne le lit. |
| `LibraryConfig.audio.preferred_codec` | schema/exemples seulement | REMOVE | Les hits `preferred_codec` runtime concernent `VideoPrefs.preferred_codec`, pas `AudioPrefs`. |
| `LibraryConfig.subtitles.required_languages` | `library/recommender.py` | KEEP | Raisons de recommandation si langue requise absente. |
| `LibraryConfig.subtitles.preferred_languages` | schema/tests seulement | REMOVE | Sert seulement a un validateur local, jamais a un comportement runtime. |
| `LibraryConfig.subtitles.warn_if_missing` | schema/exemples/tests seulement | REMOVE | Aucun warning runtime conditionne par ce champ. |

## Trailers

| Champ | Usages trouves | Decision | Raison |
| --- | --- | --- | --- |
| `TrailersConfig.enabled` | step/orchestrateur/tests | KEEP | Active/desactive la feature. |
| `TrailersConfig.languages` | `trailers/orchestrator.py` | KEEP | Langues TMDB. |
| `TrailersConfig.search_query_format` | `trailers/orchestrator.py` | KEEP | Template YouTube fallback. |
| `TrailersConfig.state_file` | state/orchestrateur/CLI | KEEP | Chemin d'etat resolu par config. |
| `TrailersConfig.retry_after_days` | `trailers/orchestrator.py` | KEEP | Politique de retry. |
| `TrailersConfig.bot_detected_max_consecutive_attempts` | schema/docs/tests seulement | REMOVE | L'etat `BOT_DETECTED` est toujours retryable; le champ ne limite rien. |
| `TrailersConfig.placement.*` | schema/tests seulement | REMOVE | Les chemins sont calcules par `trailers/placement.py`, aucun read de config. |
| `TrailersYoutubeApiConfig.daily_quota_units` | `trailers/orchestrator.py` | KEEP | Quota manager. |
| `TrailersYoutubeApiConfig.search_list_cost_units` | `trailers/orchestrator.py` | KEEP | Cout par recherche. |
| `TrailersYoutubeApiConfig.cache_ttl_days` | schema/docs/tests seulement | REMOVE | `trailers_cache.py` utilise une constante interne. |
| `TrailersYtdlpConfig.format` | `trailers/orchestrator.py` | KEEP | Passe au downloader. |
| `TrailersYtdlpConfig.socket_timeout_sec` | `trailers/orchestrator.py` | KEEP | Passe au downloader. |
| `TrailersYtdlpConfig.retries` | `trailers/orchestrator.py` | KEEP | Passe au downloader. |
| `TrailersYtdlpConfig.default_search` | schema/docs/tests seulement | REMOVE | `youtube_search.py` fixe `ytsearch1` localement. |
| `TrailersSeasonsConfig.enabled` | CLI/orchestrateur/placement/tests | KEEP | Active les trailers de saison. |
| `TrailersSeasonsConfig.language_fallback` | tests seulement | REMOVE | Aucun chemin prod ne le lit. |
| `TrailersSeasonsConfig.search_query_format` | tests seulement | REMOVE | Le query format prod est `TrailersConfig.search_query_format`. |
| `TrailersLibraryCheckConfig.*` | `trailers/orchestrator.py` | KEEP | Controle l'idempotence via indexer. |

## Indexer

| Champ | Usages trouves | Decision | Raison |
| --- | --- | --- | --- |
| `IndexerConfig.db_path` | commandes/indexer/dispatch/library | KEEP | Chemin DB actif. |
| `IndexerScanConfig.budget_seconds` | `indexer/commands/scan.py` | KEEP | Budget CLI par defaut. |
| `IndexerScanConfig.checkpoint_every_n_files` | `indexer/commands/scan.py` | KEEP | Parametre scan. |
| `IndexerScanConfig.max_workers_total` | `indexer/commands/scan.py` | KEEP | Parametre scan. |
| `IndexerScanConfig.n_strikes_for_softdelete` | `indexer/commands/scan.py` | KEEP | Politique soft-delete. |
| `IndexerScanConfig.read_rate_mb_per_sec` | `indexer/commands/scan.py` | KEEP | Throttle IO. |
| `IndexerScanConfig.drop_indexes_during_full_scan` | `indexer/commands/scan.py` | KEEP | Optimisation full scan. |
| `IndexerScanConfig.paranoia_window_seconds` | `indexer/commands/scan.py`, `commands/query.py` | KEEP | Branche paranoia quick-mode. |
| `IndexerScanConfig.nightly_mode` | schema/docs/tests seulement | REMOVE | Le mode est choisi par CLI `--mode`; aucun scheduler ne lit le champ. |
| `IndexerScanConfig.racy_window_seconds` | schema/tests seulement | REMOVE | `drift.reconcile_file` prend un argument runtime, pas ce champ config. |
| `IndexerScanConfig.sequential_read_hint` | schema/exemples/tests seulement | REMOVE | Pas de lecture config. |
| `IndexerFingerprintConfig.*` | schema/exemples/tests seulement | REMOVE | OSHash/xxh3 sont pilotes par le code indexer, pas par config. |
| `IndexerMediainfoConfig.*` | schema/exemples/tests seulement | REMOVE | `MediaInfoWrapper` est instancie par le mode enrich avec ses arguments runtime. |
| `IndexerDriftConfig.merkle_delta_freeze_threshold` | `indexer/commands/scan.py`, `commands/query.py` | KEEP | Guard de scan actif. |
| `IndexerDriftConfig.merkle_per_disk` | schema/exemples/tests seulement | REMOVE | Aucun code ne le lit. |
| `IndexerDriftConfig.verify_disks_each_scan` | schema/exemples/tests seulement | REMOVE | Les checks montages ne sont pas conditionnes par ce champ. |
| `IndexerDriftConfig.sentinel_filename` | schema/exemples/tests seulement | REMOVE | Le nom sentinel est une constante runtime, pas un chemin config. |
| `IndexerSpotlightConfig.use_when_available` | `indexer/commands/scan.py` | KEEP | Passe a `scan(..., spotlight_enabled=...)`. |
| `IndexerSpotlightConfig.probe_at_startup` | schema/exemples/tests seulement | REMOVE | Le probe n'est pas conditionne par config. |
| `IndexerRepairConfig.*` | schema/exemples/tests seulement | REMOVE | `library-repair --budget` porte le budget; pas de drain auto conditionne par config. |
| `IndexerLogConfig.deleted_item_retention_days` | `indexer/commands/repair.py` | KEEP | Purge tombstones. |
| `IndexerLogConfig.scan_event_retention_days` | schema/exemples/tests seulement | REMOVE | Aucun prune worker ne lit ce champ. |

## Cas A Ne Pas Confondre

| Nom | Decision | Detail |
| --- | --- | --- |
| `preferred_codec` | KEEP pour `VideoPrefs`, REMOVE pour `AudioPrefs` | Les usages runtime sont video uniquement. |
| `spotlight_enabled` | KEEP comme argument `scan(...)`, REMOVE comme `DiskConfig.spotlight_enabled` | Le scanner recoit le global `indexer.spotlight.use_when_available`. |
| `extract_streams`, `min_size_mb`, `parse_speed` | KEEP comme API `MediaInfoWrapper`, REMOVE comme config indexer | Les tests directs de `MediaInfoWrapper` restent valides. |

