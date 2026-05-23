# Provider-IDs — Deviations Tracking

Observateur : Claude, rôle passif. Aucune interférence avec l'implémentation.

**Feature complète — 15/15 phases gatées + post-review fixes appliqués.**

---

## Phase 1 — Capabilities Protocols

| #   | Sous-phase | Écart | Sévérité | Commit | Statut |
| --- | ---------- | ----- | -------- | ------ | ------ |
| —   | —          | Aucun écart. 7/7 sous-phases OK. | — | — | ✅ |

## Phase 2 — Fix DEV #2 IDs Propagation

| # | Sous-phase | Écart | Sévérité | Commit | Statut |
| -- | ---------- | ----- | -------- | ------ | ------ |
| 1 | 2.2 | Implémentation plus large que le plan : modifie `_tvdb_parsers.py`, `_tmdb_parsers.py` et `EpisodeInfo.external_ids` dans `_base.py`. Extraction de `_episode_payload()` helper. Approche plus propre. | Mineur | `afd06b2` | Accepté |
| — | 2.1, 2.3, 2.4 | Aucun écart. | — | — | ✅ |

## Phase 3 — IMDb/RT Facades

| # | Sous-phase | Écart | Sévérité | Commit | Statut |
| -- | ---------- | ----- | -------- | ------ | ------ |
| 1 | 3.2 | `class IMDbClient:` n'hérite pas explicitement de `IDValidator`, `RatingProvider`, `IDCrossRef`. Docstring dit "Composes" mais duck-type uniquement. `@runtime_checkable` compense. | Mineur | `00fd673` | ✅ Résolu (post-review) — héritage explicite ajouté + extension aux 11 clients api/* |
| 2 | 3.3 | Même écart : `class RottenTomatoesClient:` sans héritage explicite de `RatingProvider`. | Mineur | `7be760c` | ✅ Résolu (post-review) — héritage explicite ajouté |

## Phase 4 — Drift Validator Hardening

| # | Sous-phase | Écart | Sévérité | Commit | Statut |
| -- | ---------- | ----- | -------- | ------ | ------ |
| — | 4.2 | Pas de helper séparé `_read_canonical_provider`, logique intégrée dans `existing_validator.py`. | Mineur | `cfd3dd2` | ✅ |

## Phase 5 — NFO Generator

Aucun écart. Extraction `_xref.py` pour budget module-size.

## Phase 6 — Canonical ID Decision

Aucun écart.

## Phase 7 — DB Schema External IDs

Aucun écart résiduel. Migration 005 appliquée, `external_ids_json` + `ratings_json` en place.

## Phase 8 — Backfill Mode

Aucun écart.

## Phase 9 — Verify Checker Extensions

Aucun écart.

## Phase 10 — Consumers Refactor

Aucun écart. `OverrideRule.imdb_id` supprimé.

## Phase 11 — Tracker Capabilities

Aucun écart. `TrackerClient` monolithique droppé, LaCale/C411 composent capabilities.

## Phase 12 — Tracker Registry Priority-Aware

Aucun écart.

## Phase 13 — Torrent Capabilities

Aucun écart. `TorrentClient` monolithique droppé, QBit/Transmission composent capabilities.

## Phase 14 — Notify Capabilities

Aucun écart. `TelegramNotifier(Notifier)` + `HealthcheckClient(HealthChecker)` composition explicite.

## Phase 15 — Integration E2E

Aucun écart. E2E aggregate + acceptance report + reference doc.

---

## Synthèse

| Sévérité | Count |
| -------- | ----- |
| Critique | 0 |
| Majeur | 0 |
| Modéré | 0 |
| Mineur | 2 (2.2 scope élargi, 4.2 pas de helper séparé — 3.2 et 3.3 résolus en post-review) |

**Quality gates final** : `make lint` 0, `make test` 4475 passed, `make check` OK, `import personalscraper` OK.

Dernier audit : Phase 15 gate `d7f7c04` (2026-05-18) — Feature provider-ids complète. 🎯

## Post-review fixes (2026-05-18)

Cycle de review `/pr-review-toolkit:review-pr` a remonté plusieurs items non couverts par les 15 phases initiales :

| Item | Description | Résolution |
| ---- | ----------- | ---------- |
| C1 | 4 fichiers (`rotten_tomatoes`, `notify/healthchecks`, `notify/telegram`, `torrent/transmission`) déclaraient l'héritage Protocol sans importer le Protocol — `NameError` au module load. | ✅ Imports ajoutés. |
| C2 | TMDB / TVDB / Trakt / C411 / LaCale déclaraient des Protocols qu'ils n'implémentaient pas. | ✅ Listes d'héritage corrigées. TMDB/TVDB gagnent `get_episodes` (wrapper sur `get_tv_season`/`get_series_episodes`). TVDB gagne `get_tv` alias. Trakt gagne `get_movie` + `get_tv` aliases sur `get_details`. Signatures TMDB/TVDB `get_movie`/`get_tv` élargies à `str \| int` pour satisfaire les Protocols `(provider_id: str)` sans casser les callers existants. C411/LaCale perdent `FreeleechAware` + `TorrentDetailsProvider` (méthodes absentes). |
| C3 | `personalscraper indexer --backfill-ids` était un no-op silencieux sur les IDs (`new_ids={}` codé en dur). | ✅ Pluggé via `_fetch_cross_provider_ids` qui appelle `tmdb_client.get_tv` / `tvdb_client.get_movie` et extrait `MediaDetails.external_ids`. Avertissement clair si pas de client canonical configuré. Ordre IDs→ratings fixé pour qu'un IMDb ancré au pass IDs soit visible au pass ratings. |
| I1 | Drift validator avait un dead-code path : la branche "missing canonical uniqueid" ne se déclenchait jamais car `_read_canonical_provider` tombait sur le premier `<uniqueid>`. | ✅ Check strict `default="true"` ajouté en amont (DESIGN §3 Q6). Test fixtures legacy mises à jour pour porter l'attribut. |
| I2 | Pas de test pour la composition Protocol des clients metadata. | ✅ `tests/unit/test_metadata_capabilities_composition.py` ajouté (33 assertions bidirectionnelles isinstance + MRO). |
| I3 | Coverage backfill idempotence uniquement sur le cas "library déjà complète". | ✅ `test_e2e_backfill_partial_then_idempotent` ajouté : seed TVDB-only, pass1 ajoute TMDB+IMDb+rating, pass2 zéro update. |
| Silent failures | Logging gaps sur xref ratings, multi-source NFO dedup, Telegram chunk-on-mid-failure, NFO parse fails dans verify checker, backfill rating call. | ✅ Logs structurés ajoutés partout (`source`, `chunks_sent/total`, `error_type`, `unparseable` marker). |
| Misc | Stale docstrings (lacale/c411/qbit/transmission "Structural composition rather than explicit inheritance"). | ✅ Docstrings réalignées avec la nouvelle inheritance explicite. |
| Protocol mismatch | `Notifier.provider_name` / `HealthChecker.provider_name` étaient `str` (instance var) — incompatibles avec `ClassVar[str]` sur les implémentations concrètes. | ✅ Protocols mis à jour en `ClassVar[str]` pour matcher l'usage réel. |

**Quality gates post-review** : `make lint` 0 erreurs, `make test` 4475 passed (≈+36 vs gate phase 15), `make check` OK.
