# What the interface asks of the backend

**COMPUTED, NEVER WRITTEN.** `python3 scripts/compare-contracts.py --write` builds this
file by diffing `frontend/maquette/contract/openapi.json` — the contract the maquette's
interface REQUIRES — against `frontend/openapi.json`, which is generated FROM the running
backend. `--check` refuses a committed register that differs from the computed one, so the
two cannot separate. Edit the contract, not this file.

**NOBODY IS BUILDING THIS YET, and that is D7.** No backend work happens until the
interface is frozen; starting earlier means rebuilding against a specification that is
still moving. What this file is FOR is that the specification arrives as a diff rather
than a blank page.

| | |
| --- | ---: |
| operations the interface requires | 54 |
| operations the backend has | 65 |
| required and missing | 13 |
| declared by both, different response shape | 41 |
| declared by both, path parameter spelled differently | 11 |
| fields carried pre-formatted | 25 |
| the backend has and the interface does not use | 24 |

---

## 1. Operations the interface requires and the backend does not have

| operation | operationId | what it is for |
| --- | --- | --- |
| `DELETE /api/library/items` | `deleteLibraryItems` | Delete titles from the library |
| `GET /api/acquisition/journeys/{infoHash}` | `readJourney` | One torrent's journey, stage by stage |
| `GET /api/acquisition/releases` | `readReleases` | The release candidates for one wanted item |
| `GET /api/acquisition/suggestions` | `readSuggestions` | Titles worth following, and why |
| `GET /api/library/categories` | `readLibraryCategories` | The categories and their counts |
| `GET /api/library/incomplete` | `readLibraryIncomplete` | The series with holes, and how big each hole is |
| `GET /api/library/items` | `readLibraryItems` | The library listing, one page of it |
| `GET /api/library/recent` | `readLibraryRecent` | The most recently added titles |
| `GET /api/media/{provider}/{providerId}/seasons` | `readMediaSeasons` | The seasons of a show, and what the library holds of each |
| `GET /api/system/dependencies` | `readDependencies` | The external dependencies, and whether each answers |
| `GET /api/system/errors` | `readErrors` | How many errors, out of how many runs, and the latest |
| `GET /api/system/services` | `readServices` | The services, and whether each answers |
| `POST /api/acquisition/to-handle/{mediaId}/take` | `takeQueued` | Restart one item that was waiting to be acquired |

## 2. Operations both declare, whose response carries different property names

Names, never types. A type comparison across two documents written by different hands
reports a difference for every optional field and drowns the real findings.

| operation | the interface adds | the backend has and the interface does not use |
| --- | --- | --- |
| `DELETE /api/acquisition/followed/{followedId}` (`deleteFollow`) | `ok` | — |
| `GET /api/acquisition/followed` (`readFollows`) | `aired`, `fresh`, `searches`, `showStatus`, `since` | `acquiring_count`, `active`, `added_at`, `aired_count`, `announced_count`, `cadence`, `cadence_tier`, `id`, `imdb_id`, `items`, `last_search_at`, `last_search_found`, `last_search_outcome`, `media_ref`, `movie_facts`, `next_search_at`, `original_title`, `overview`, `owned_count`, `pending_count`, `poster_url`, `priming_running`, `quality_profile`, `season_count`, `series_status`, `tmdb_id`, `to_grab_count`, `tvdb_id`, `tvdb_unresolved`, `unverified_count`, `wanted_grabbed`, `wanted_pending`, `wanted_status` |
| `GET /api/acquisition/search` (`searchProviders`) | `followed`, `owned`, `shown` | `already_owned`, `limit`, `offset`, `poster_url`, `provider`, `provider_id`, `score` |
| `GET /api/acquisition/status` (`readAcquisitionStatus`) | `cadence`, `nextSearch` | `command`, `deferred`, `ended_at`, `last_successful_run_at`, `name`, `outcome`, `reason`, `recent_runs`, `result`, `run_uid`, `started_at`, `trigger`, `watcher_enabled` |
| `GET /api/acquisition/to-handle` (`readAcquisitionQueue`) | `blocked`, `chip`, `doneToday`, `inFlight`, `notFound`, `secondaryLine`, `strip`, `takeable`, `text`, `tone`, `withoutPoster` | `candidates_count`, `created_at`, `decision_id`, `degraded`, `episode`, `followed_id`, `info_hash`, `items`, `kind`, `orphan_count`, `season`, `stage`, `year` |
| `GET /api/auth/me` (`readAccount`) | `avatar`, `email`, `name` | — |
| `GET /api/config/files` (`readConfigurationFiles`) | `changed` | `files`, `mtime`, `owned_keys`, `sha256`, `shadowed_keys`, `size` |
| `GET /api/config/schema` (`readSettings`) | `displayedValue`, `file`, `fileNames`, `id`, `key`, `name`, `note`, `raw`, `secondaryLine`, `settings`, `title`, `type` | `json_schema`, `ownership`, `restart_impact` |
| `GET /api/config/secrets` (`readSecrets`) | `defined`, `label` | `description`, `is_set`, `secrets` |
| `GET /api/config/status` (`readConfigurationStatus`) | `readOnly`, `restartRequired` | `read_only`, `restart_configured`, `restart_required`, `role`, `stale_files` |
| `GET /api/decisions/` (`readDecisions`) | `candidates`, `choice`, `folder`, `kind`, `overview`, `pending`, `provider`, `reason`, `score`, `settled`, `state`, `title`, `via`, `when`, `withoutPoster`, `year` | `candidates_count`, `created_at`, `extracted_title`, `extracted_year`, `items`, `media_kind`, `page`, `page_size`, `pending_count`, `staging_path`, `status`, `total`, `trigger` |
| `GET /api/maintenance/actions` (`readMaintenanceActions`) | `dryRun`, `group`, `long` | `actions`, `category`, `category_counts`, `default`, `dry_run`, `enum_values`, `help`, `long_running`, `name`, `options`, `required`, `title`, `type` |
| `GET /api/maintenance/destructive-log` (`readDeletionJournal`) | `label`, `rows`, `secondaryLine`, `total`, `value` | `actor`, `detail`, `entries`, `op`, `path`, `run_uid`, `ts` |
| `GET /api/maintenance/disks` (`readDisks`) | `secondaryLine`, `tone`, `value` | `disks`, `free_gb`, `id`, `mounted`, `total_gb`, `used_pct` |
| `GET /api/maintenance/index-health` (`readIndexHealth`) | `label`, `secondaryLine`, `tone`, `value` | `canonical_null`, `degraded`, `error`, `files`, `invalid`, `items`, `last_scan_finished_at`, `last_scan_id`, `last_scan_mode`, `last_scan_started_at`, `last_scan_status`, `last_scan_stuck`, `missing`, `movies`, `nfo`, `outbox_oldest_age_s`, `outbox_pending`, `repair_queue_oldest_age_s`, `repair_queue_pending`, `shows`, `size_gb`, `soft_deleted`, `valid` |
| `GET /api/maintenance/schedulers` (`readSchedulers`) | `label`, `secondaryLine`, `tone`, `value` | `display_name`, `enabled`, `kind`, `last_outcome`, `last_run_at`, `name`, `schedule`, `schedulers` |
| `GET /api/media/{provider}/{providerId}` (`readMediaSheet`) | `airDate`, `cast`, `castPortraits`, `duration`, `episodes`, `hero`, `ids`, `key`, `language`, `name`, `number`, `poster`, `posterHighDefinition`, `rating`, `role`, `runtime`, `status`, `tmdbTelevisionId`, `trailer`, `trailerVideo` | `aired_count`, `degraded_reason`, `episode_count`, `owned_count`, `ownership`, `poster_url`, `provider`, `provider_id`, `season_number`, `series_status`, `trailer_url` |
| `GET /api/pipeline/history` (`readPipelineHistory`) | `cause`, `result`, `succeeded`, `when` | `command`, `degraded`, `dry_run`, `duration_s`, `ended_at`, `kind`, `outcome`, `run_uid`, `runs`, `started_at`, `total`, `trigger` |
| `GET /api/pipeline/status` (`readPipeline`) | `blockedCount`, `description`, `duration`, `facts`, `label`, `last`, `name`, `outcome`, `result`, `secondaryLine`, `steps`, `trigger`, `triggers`, `uid`, `when` | `paused`, `pid`, `run_uid`, `state`, `step`, `watcher_enabled` |
| `GET /api/staging/media` (`readStaging`) | `chip`, `moving`, `secondaryLine`, `settled`, `strip`, `stuck`, `text`, `tone`, `withoutPoster` | `absent`, `ambiguous`, `awaiting_action`, `blocked_reason`, `category`, `category_id`, `continuation_requested_at`, `counts`, `decision_id`, `decision_trigger`, `disk`, `dispatch_target`, `episode_count`, `folder`, `has_nfo`, `has_poster`, `has_trailer`, `id`, `items`, `key`, `label`, `match`, `matched`, `media_kind`, `mode`, `modified_at`, `overview`, `page`, `page_size`, `position_stage`, `position_state`, `poster_url`, `provider_ids`, `relative_path`, `scraped`, `season`, `seasons`, `size_bytes`, `stages`, `state`, `total`, `video_count`, `with_trailer`, `year` |
| `GET /api/version` (`readVersion`) | `commit` | `build_commit` |
| `PATCH /api/acquisition/followed/{followedId}` (`updateFollow`) | `aired`, `fresh`, `searches`, `showStatus`, `since` | `acquiring_count`, `active`, `added_at`, `aired_count`, `announced_count`, `cadence`, `cadence_tier`, `id`, `imdb_id`, `last_search_at`, `last_search_found`, `last_search_outcome`, `media_ref`, `movie_facts`, `next_search_at`, `original_title`, `overview`, `owned_count`, `pending_count`, `poster_url`, `priming_running`, `quality_profile`, `season_count`, `series_status`, `tmdb_id`, `to_grab_count`, `tvdb_id`, `tvdb_unresolved`, `unverified_count`, `wanted_grabbed`, `wanted_pending`, `wanted_status` |
| `POST /api/acquisition/detect` (`runDetection`) | `available`, `detected`, `grabbed` | — |
| `POST /api/acquisition/followed` (`createFollow`) | `aired`, `fresh`, `kind`, `owned`, `searches`, `showStatus`, `since`, `status`, `title`, `year` | — |
| `POST /api/acquisition/followed/{followedId}/grab` (`grabForFollow`) | `releaseName` | — |
| `POST /api/acquisition/followed/{followedId}/search` (`searchForFollow`) | `found` | — |
| `POST /api/auth/login` (`signIn`) | `avatar`, `email`, `name` | — |
| `POST /api/auth/logout` (`signOut`) | `ok` | — |
| `POST /api/config/restart-web` (`restartWeb`) | `ok` | — |
| `POST /api/decisions/{decisionId}/dismiss` (`dismissDecision`) | `state` | `candidates`, `candidates_count`, `created_at`, `extracted_title`, `extracted_year`, `id`, `media_kind`, `overview`, `poster_url`, `provider`, `provider_id`, `resolution_json`, `score`, `staging_path`, `status`, `title`, `trigger`, `year` |
| `POST /api/decisions/{decisionId}/resolve` (`resolveDecision`) | `state` | — |
| `POST /api/decisions/{decisionId}/search` (`searchForDecision`) | `id`, `withoutPoster` | `candidates`, `poster_url`, `provider_id` |
| `POST /api/maintenance/actions/{actionId}/run` (`runMaintenanceAction`) | `state`, `uid` | — |
| `POST /api/pipeline/kill` (`killPipeline`) | — | `paused`, `pid`, `run_uid`, `step`, `watcher_enabled` |
| `POST /api/pipeline/pause` (`pausePipeline`) | — | `paused`, `pid`, `run_uid`, `step`, `watcher_enabled` |
| `POST /api/pipeline/resume` (`resumePipeline`) | — | `paused`, `pid`, `run_uid`, `step`, `watcher_enabled` |
| `POST /api/pipeline/run` (`runPipeline`) | `state`, `uid` | — |
| `POST /api/staging/media/{mediaId}/continue` (`continueStagedMedia`) | `ok` | — |
| `POST /api/staging/media/{mediaId}/discard` (`discardStagedMedia`) | — | `detail`, `journaled`, `media_id`, `quarantine_path` |
| `PUT /api/config/files/{name}` (`updateConfigurationFile`) | `conflict`, `restartRequired` | `restart_required`, `warnings` |
| `PUT /api/config/secrets` (`updateSecrets`) | `restartRequired` | `restart_required`, `warnings` |

## 2b. Operations both declare, whose path parameter is spelled differently

The interface writes a parameter in camelCase, the backend in snake_case. It is a real
divergence and a small one — the demand is one spelling, and which one is the
operator's call rather than this file's.

| the interface requires | the backend has |
| --- | --- |
| `DELETE /api/acquisition/followed/{followedId}` | `DELETE /api/acquisition/followed/{followed_id}` |
| `GET /api/media/{provider}/{providerId}` | `GET /api/media/{provider}/{provider_id}` |
| `PATCH /api/acquisition/followed/{followedId}` | `PATCH /api/acquisition/followed/{followed_id}` |
| `POST /api/acquisition/followed/{followedId}/grab` | `POST /api/acquisition/followed/{followed_id}/grab` |
| `POST /api/acquisition/followed/{followedId}/search` | `POST /api/acquisition/followed/{followed_id}/search` |
| `POST /api/decisions/{decisionId}/dismiss` | `POST /api/decisions/{decision_id}/dismiss` |
| `POST /api/decisions/{decisionId}/resolve` | `POST /api/decisions/{decision_id}/resolve` |
| `POST /api/decisions/{decisionId}/search` | `POST /api/decisions/{decision_id}/search` |
| `POST /api/maintenance/actions/{actionId}/run` | `POST /api/maintenance/actions/{action_id}/run` |
| `POST /api/staging/media/{mediaId}/continue` | `POST /api/staging/media/{media_id}/continue` |
| `POST /api/staging/media/{mediaId}/discard` | `POST /api/staging/media/{media_id}/discard` |

## 3. Fields the interface carries pre-formatted

**The demand is the same for every one of them: supply the underlying fact and let the
interface format it.** They are carried verbatim today because the maquette's fixture
holds them that way, and because a mock returning exactly what the fixture returns is
what makes L09 provable at zero divergence (D-L08-5). Decomposing them in the contract
would be a better contract and would forfeit that proof for something nobody is building
yet.

| where | field |
| --- | --- |
| `CodeErrors` | `latest` |
| `CodeErrors` | `what` |
| `CodeErrors` | `where` |
| `Fact` | `secondaryLine` |
| `Fact` | `value` |
| `Follow` | `since` |
| `JournalRow` | `secondaryLine` |
| `JournalRow` | `value` |
| `JourneyStage` | `when` |
| `LibraryItem` | `secondaryLine` |
| `LibraryRow` | `secondaryLine` |
| `MediaSheet` | `genres` |
| `PendingDecision` | `when` |
| `PipelineExecution` | `cause` |
| `PipelineExecution` | `result` |
| `PipelineExecution` | `when` |
| `PipelineFact` | `result` |
| `PipelineFact` | `secondaryLine` |
| `PipelineRunSummary` | `duration` |
| `PipelineRunSummary` | `when` |
| `QueueCard` | `reason` |
| `QueueCard` | `secondaryLine` |
| `SearchResult` | `kind` |
| `SettledDecision` | `when` |
| `Suggestion` | `kind` |

## 4. Operations the backend has and the interface does not use

Recorded because it says what the switchover MAY retire. It is not a suggestion to
remove anything: an operation the maquette does not call may still be called by the
production app, by a script, or by the operator.

- `GET /api/acquisition/downloads`
- `GET /api/acquisition/followed/{followed_id}/completeness`
- `GET /api/acquisition/journeys`
- `GET /api/acquisition/lookup`
- `GET /api/acquisition/obligations`
- `GET /api/acquisition/overview`
- `GET /api/acquisition/stalled-grabs`
- `GET /api/acquisition/wanted`
- `GET /api/config/files/{name}`
- `GET /api/decisions/activity`
- `GET /api/decisions/{decision_id}`
- `GET /api/health`
- `GET /api/maintenance/locks`
- `GET /api/pipeline/history/{run_uid}`
- `GET /api/pipeline/stages`
- `GET /api/registry/status`
- `GET /api/staging/media/{media_id}/poster`
- `POST /api/acquisition/follows/{followed_id}/seasons/{season}/grab`
- `POST /api/acquisition/journeys/{info_hash}/requeue`
- `POST /api/acquisition/journeys/{info_hash}/rescrape`
- `POST /api/acquisition/ranking/preview`
- `POST /api/config/validate`
- `POST /api/pipeline/watcher`
- `POST /api/staging/media/{media_id}/enqueue`
