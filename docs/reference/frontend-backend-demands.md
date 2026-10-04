# What the interface asks of the backend

**COMPUTED, NEVER WRITTEN.** `python3 scripts/compare-contracts.py --write` builds this
file by diffing `contract/openapi.json` — the contract the maquette's
interface REQUIRES — against `frontend/openapi.json`, which is generated FROM the running
backend. `--check` refuses a committed register that differs from the computed one, so the
two cannot separate. Edit the contract, not this file.

**THE INTERFACE ADDRESSES EVERY OPERATION UNDER `/api/v1`** — its contract's `servers`
URL, its paths relative to it — where the backend serves them under `/api`. That
root is one demand, said here once: the operations below are matched on the path BELOW
each root, and written as each side addresses them.

**IT DESCRIBES OPERATIONS, AND A WEBSOCKET IS NOT ONE.** OpenAPI cannot declare
`/api/v1/events`, so nothing about the event stream can ever appear below — and nothing
reads as identical to no demands (B-153). The stream's demands are written BY HAND in
`docs/reference/frontend-backend-demands-stream.md`. This pointer lives in the
GENERATOR, so regenerating this file cannot drop it.

**NOBODY IS BUILDING THIS YET, and that is D7.** No backend work happens until the
interface is frozen; starting earlier means rebuilding against a specification that is
still moving. What this file is FOR is that the specification arrives as a diff rather
than a blank page.

| | |
| --- | ---: |
| operations the interface requires | 104 |
| operations the backend has | 65 |
| required and missing | 51 |
| declared by both, different response shape | 53 |
| declared by both, path parameter spelled differently | 17 |
| declared by both, answered with a different status | 11 |
| fields carried pre-formatted | 22 |
| the backend has and the interface does not use | 12 |

---

## 1. Operations the interface requires and the backend does not have

| operation | operationId | what it is for |
| --- | --- | --- |
| `DELETE /api/v1/acquisition/downloads/{infoHash}` | `removeDownload` | Remove one entry from the download client, its files deleted or kept |
| `DELETE /api/v1/library/items` | `deleteLibraryItems` | Delete media from the library, by provider identity |
| `DELETE /api/v1/roles/{roleId}` | `deleteRole` | Delete a role nobody holds |
| `DELETE /api/v1/staging/media/{mediaId}` | `deleteStagedMedia` | Delete a staged folder from the disk |
| `DELETE /api/v1/staging/media/{mediaId}/reclassify` | `restoreReclassifiedMedia` | Put a reclassified folder back in the staging area |
| `DELETE /api/v1/torrents/{infoHash}/cross-seed/exclusions` | `undoCrossSeedExclusion` | Lift an exclusion, of one pair or of a whole title |
| `GET /api/v1/accounts` | `readAccounts` | Every account and every role |
| `GET /api/v1/acquisition/journeys/{infoHash}` | `readJourney` | One medium's ladder, rung by rung |
| `GET /api/v1/acquisition/releases` | `readReleases` | The release candidates for one wanted item |
| `GET /api/v1/acquisition/search/by-id` | `searchProviderById` | Find the one medium a source knows under an identifier |
| `GET /api/v1/acquisition/suggestions` | `readSuggestions` | Titles worth following, and why |
| `GET /api/v1/library/categories` | `readLibraryCategories` | The engine's leaf categories and their counts |
| `GET /api/v1/library/incomplete` | `readLibraryIncomplete` | The series with holes, and how big each hole is |
| `GET /api/v1/library/items` | `readLibraryItems` | The library listing, one page of it |
| `GET /api/v1/library/membership` | `readLibraryMembership` | Whether the library holds one medium, asked by its provider identity |
| `GET /api/v1/library/recent` | `readLibraryRecent` | The most recently added titles |
| `GET /api/v1/media/{provider}/{providerId}/cross-seed` | `readMediaCrossSeed` | The medium's cross-seed, tracker by tracker |
| `GET /api/v1/media/{provider}/{providerId}/poster` | `readMediaPoster` | The poster file a medium's library folder holds |
| `GET /api/v1/media/{provider}/{providerId}/seasons` | `readMediaSeasons` | The seasons of a show, and what the library holds of each |
| `GET /api/v1/notifications/preferences` | `readNotificationPreferences` | The signed-in account's notification switches, one per type it may receive |
| `GET /api/v1/staging/destinations` | `readStagingDestinations` | Where the sort files what is not a medium |
| `GET /api/v1/staging/media/{mediaId}/copies` | `readStagedMediaCopies` | Whether a staged folder is the only copy of its files — POSED in the maquette (RULINGS 22); the backend reads the torrent's presence in qBittorrent at the gesture |
| `GET /api/v1/system/dependencies` | `readDependencies` | The external dependencies, and whether each answers |
| `GET /api/v1/system/errors` | `readErrors` | How many errors, out of how many runs, and the latest |
| `GET /api/v1/system/services` | `readServices` | The services, and whether each answers |
| `GET /api/v1/trackers` | `readTrackers` | Every configured tracker, its ratio, volumes, trend, alert threshold and health |
| `PATCH /api/v1/accounts/{accountId}` | `updateAccount` | Assign an account its one role |
| `PATCH /api/v1/roles/{roleId}` | `updateRole` | Rename a role or set its rights |
| `POST /api/v1/accounts` | `createAccount` | Create an account |
| `POST /api/v1/accounts/{accountId}/password` | `resetAccountPassword` | Reset a local account's password to a provisional one |
| `POST /api/v1/acquisition/followed/{followedId}/restore` | `restoreFollow` | Put a removed follow back, as it was |
| `POST /api/v1/acquisition/journeys/{infoHash}/closure/seen` | `dismissClosure` | Mark one closed tunnel seen, for the caller — the seen mark stored per account (BK5); the engine closes the tunnel itself, its medium vanished (BK3) or a later choice in place (BK4) |
| `POST /api/v1/acquisition/journeys/{infoHash}/plex-match` | `resolvePlexMatch` | Confirm or correct the match Plex made for a medium — the Plex match's CORRECTION VERB, OPEN 9's fifth demand; the disagreement is POSED in the maquette (RULINGS 24), the backend compares Plex's real match with the identity held |
| `POST /api/v1/acquisition/requesters/reassign` | `reassignRequester` | Move one requester of an acquisition to another account |
| `POST /api/v1/auth/plex` | `signInWithPlex` | Open a session through Plex |
| `POST /api/v1/auth/plex/start` | `startPlexSignIn` | Start a Plex sign-in |
| `POST /api/v1/decisions/{decisionId}/reopen` | `reopenDecision` | Re-open a settled decision for arbitration, with the candidates a provider search finds |
| `POST /api/v1/media/{provider}/{providerId}/rescrape` | `rescrapeMedia` | Ask the providers for one medium's metadata again |
| `POST /api/v1/notifications/devices` | `registerPushDevice` | Register this device's push token for the signed-in account (K5) |
| `POST /api/v1/roles` | `createRole` | Create an ordinary role |
| `POST /api/v1/staging/media/{mediaId}/reclassify` | `reclassifyStagedMedia` | File a folder that is not a medium where the sort files its kind |
| `POST /api/v1/torrents/{infoHash}/cross-seed/search` | `searchCrossSeed` | Search a cross-seed for one torrent, on one tracker or on every eligible one |
| `POST /api/v1/torrents/{infoHash}/cross-seed/{tracker}/cut` | `cutCrossSeed` | Cut one torrent's cross-seed on one tracker |
| `POST /api/v1/torrents/{infoHash}/cross-seed/{tracker}/upload` | `uploadCrossSeed` | Create a torrent from one origin's files and publish it on one tracker |
| `POST /api/v1/trackers/{tracker}/broken-obligations/{infoHash}/seen` | `markBrokenObligationSeen` | Mark one broken obligation of a tracker seen |
| `PUT /api/v1/accounts/{accountId}/access` | `setAccountAccess` | Allow or cut an account's sign-in |
| `PUT /api/v1/acquisition/followed/{followedId}/pause` | `setAcquisitionPause` | Set the caller's pause on one acquisition |
| `PUT /api/v1/acquisition/followed/{followedId}/quality` | `setAcquisitionQuality` | Set the caller's quality profile on one acquisition |
| `PUT /api/v1/auth/password` | `changeOwnPassword` | Change the signed-in account's password |
| `PUT /api/v1/notifications/preferences/{type}` | `updateNotificationPreference` | Switch one notification type on or off for the signed-in account |
| `PUT /api/v1/torrents/{infoHash}/cross-seed/exclusions` | `writeCrossSeedExclusion` | Exclude one pair, or a whole title, from the engine's future cross-seed passes |

## 2. Operations both declare, whose response carries different property names

Names, never types. A type comparison across two documents written by different hands
reports a difference for every optional field and drowns the real findings.

| operation | the interface adds | the backend has and the interface does not use |
| --- | --- | --- |
| `DELETE /api/v1/acquisition/followed/{followedId}` (`deleteFollow`) | `ok` | — |
| `GET /api/v1/acquisition/downloads` (`readDownloads`) | `addedAt`, `at`, `candidate`, `clientAvailable`, `crossSeed`, `crossSeedQuota`, `deadline`, `delaySeconds`, `downloadRate`, `downloadedBytes`, `entryHash`, `errorReason`, `etaSeconds`, `excluded`, `folder`, `ids`, `infoHash`, `pairs`, `perDay`, `poster`, `provenance`, `ratio`, `reason`, `searching`, `sizeBytes`, `stopCause`, `stoppedAt`, `swarmLeechers`, `swarmSeeds`, `titleExcluded`, `tracker`, `trackerReason`, `uploadRate`, `uploadedBytes`, `uploading`, `used`, `via`, `waitReason` | `client_available`, `error_reason`, `eta_seconds`, `imdb_id`, `info_hash`, `media_ref`, `size_bytes`, `tmdb_id`, `tvdb_id` |
| `GET /api/v1/acquisition/followed` (`readFollows`) | `addedAt`, `aired`, `fresh`, `ids`, `name`, `nextAirDate`, `ownPaused`, `ownQuality`, `paused`, `poster`, `quality`, `requesters`, `searches`, `showStatus`, `since` | `acquiring_count`, `active`, `added_at`, `aired_count`, `announced_count`, `cadence`, `cadence_tier`, `imdb_id`, `items`, `last_search_at`, `last_search_found`, `last_search_outcome`, `media_ref`, `movie_facts`, `next_search_at`, `original_title`, `overview`, `owned_count`, `pending_count`, `poster_url`, `priming_running`, `quality_profile`, `season_count`, `series_status`, `tmdb_id`, `to_grab_count`, `tvdb_id`, `tvdb_unresolved`, `unverified_count`, `wanted_grabbed`, `wanted_pending`, `wanted_status` |
| `GET /api/v1/acquisition/followed/{followedId}/completeness` (`readFollowCompleteness`) | `airDate`, `catalogRefreshedAt`, `followedId`, `lastSearchOutcome`, `providerCatalogEmpty` | `air_date`, `catalog_refreshed_at`, `followed_id`, `last_search_outcome`, `provider_catalog_empty` |
| `GET /api/v1/acquisition/obligations` (`readObligations`) | `accumulatedSeedTimeSeconds`, `addedAt`, `breachedAt`, `crossSeedOf`, `dispatchedPath`, `hitAndRunCount`, `infoHash`, `media`, `minimumRatio`, `minimumSeedTimeSeconds`, `observedRatio`, `releasedAt`, `releasedBy`, `requiredRatio`, `satisfiedAt`, `satisfiedBy`, `sourceTracker` | `accumulated_seed_time_s`, `added_at`, `breached_at`, `dispatched_path`, `hnr_count`, `info_hash`, `min_ratio`, `min_seed_time_s`, `observed_ratio`, `released_at`, `satisfied_at`, `source_tracker` |
| `GET /api/v1/acquisition/search` (`searchProviders`) | `followed`, `ids`, `owned`, `poster`, `shown` | `already_owned`, `limit`, `offset`, `poster_url`, `provider`, `provider_id`, `score` |
| `GET /api/v1/acquisition/status` (`readAcquisitionStatus`) | `cadence`, `nextSearch` | `command`, `deferred`, `ended_at`, `last_successful_run_at`, `name`, `outcome`, `reason`, `recent_runs`, `result`, `run_uid`, `started_at`, `trigger`, `watcher_enabled` |
| `GET /api/v1/acquisition/to-handle` (`readAcquisitionQueue`) | `absorbedBy`, `arrivals`, `at`, `blocked`, `blockedSince`, `blocks`, `chip`, `closure`, `droppedByHand`, `failedStep`, `id`, `ids`, `inFlight`, `keptNewer`, `ladder`, `minimumRatio`, `name`, `plexMatch`, `poster`, `provider`, `release`, `requester`, `requesters`, `resumedAt`, `resumes`, `rung`, `secondaryLine`, `since`, `size`, `state`, `steps`, `strip`, `takeable`, `text`, `tone`, `tracker`, `trigger`, `via`, `when`, `winner`, `withoutPoster` | `candidates_count`, `created_at`, `decision_id`, `degraded`, `followed_id`, `info_hash`, `items`, `orphan_count`, `stage`, `year` |
| `GET /api/v1/auth/me` (`readAccount`) | `avatar`, `defaultFor`, `email`, `forbiddenWrites`, `id`, `kind`, `name`, `rights`, `role`, `signInKind` | — |
| `GET /api/v1/config/files` (`readConfigurationFiles`) | `changed` | `files`, `mtime`, `owned_keys`, `sha256`, `shadowed_keys`, `size` |
| `GET /api/v1/config/files/{name}` (`readConfigurationFile`) | `digest`, `shadowedKeys` | `sha256`, `shadowed_keys` |
| `GET /api/v1/config/schema` (`readSettings`) | `displayedValue`, `file`, `fileNames`, `id`, `key`, `name`, `note`, `precision`, `raw`, `secondaryLine`, `settings`, `title`, `type` | `json_schema`, `ownership`, `restart_impact` |
| `GET /api/v1/config/secrets` (`readSecrets`) | `defined`, `label` | `description`, `is_set`, `secrets` |
| `GET /api/v1/config/status` (`readConfigurationStatus`) | `restartRequired` | `read_only`, `restart_configured`, `restart_required`, `role`, `stale_files` |
| `GET /api/v1/decisions/` (`readDecisions`) | `candidates`, `choice`, `folder`, `kept`, `kind`, `overview`, `pending`, `poster`, `provider`, `reason`, `score`, `settled`, `settledBy`, `state`, `title`, `via`, `when`, `withoutPoster`, `year` | `candidates_count`, `created_at`, `extracted_title`, `extracted_year`, `items`, `media_kind`, `page`, `page_size`, `pending_count`, `staging_path`, `status`, `total`, `trigger` |
| `GET /api/v1/maintenance/actions` (`readMaintenanceActions`) | `dryRun`, `group`, `long` | `actions`, `category`, `category_counts`, `default`, `dry_run`, `enum_values`, `help`, `long_running`, `name`, `options`, `required`, `title`, `type` |
| `GET /api/v1/maintenance/destructive-log` (`readDeletionJournal`) | `label`, `rows`, `secondaryLine`, `total`, `value` | `actor`, `detail`, `entries`, `op`, `path`, `run_uid`, `ts` |
| `GET /api/v1/maintenance/disks` (`readDisks`) | `secondaryLine`, `since`, `state`, `tone`, `value` | `disks`, `free_gb`, `id`, `mounted`, `total_gb`, `used_pct` |
| `GET /api/v1/maintenance/index-health` (`readIndexHealth`) | `label`, `secondaryLine`, `since`, `state`, `tone`, `value` | `canonical_null`, `degraded`, `error`, `files`, `invalid`, `items`, `last_scan_finished_at`, `last_scan_id`, `last_scan_mode`, `last_scan_started_at`, `last_scan_status`, `last_scan_stuck`, `missing`, `movies`, `nfo`, `outbox_oldest_age_s`, `outbox_pending`, `repair_queue_oldest_age_s`, `repair_queue_pending`, `shows`, `size_gb`, `soft_deleted`, `valid` |
| `GET /api/v1/maintenance/locks` (`readLocks`) | `ageS`, `pauseAgeS`, `pipelineLock`, `watcherPaused`, `watcherPausedAgeS` | `age_s`, `pause_age_s`, `pid_alive`, `pipeline_lock`, `watcher_paused`, `watcher_paused_age_s` |
| `GET /api/v1/maintenance/schedulers` (`readSchedulers`) | `label`, `secondaryLine`, `since`, `state`, `tone`, `value` | `display_name`, `enabled`, `kind`, `last_outcome`, `last_run_at`, `name`, `schedule`, `schedulers` |
| `GET /api/v1/media/{provider}/{providerId}` (`readMediaSheet`) | `airDate`, `cast`, `castPortraits`, `duration`, `episodes`, `hero`, `ids`, `key`, `language`, `metadataRefreshedAt`, `name`, `number`, `poster`, `posterHighDefinition`, `rating`, `role`, `runtime`, `status`, `tmdbTelevisionId`, `trailer`, `trailerVideo` | `aired_count`, `degraded_reason`, `episode_count`, `owned_count`, `ownership`, `poster_url`, `provider`, `provider_id`, `season_number`, `series_status`, `trailer_url` |
| `GET /api/v1/pipeline/history` (`readPipelineHistory`) | `available`, `cause`, `counts`, `detected`, `dryRun`, `durationS`, `endedAt`, `errorCount`, `grabbed`, `name`, `result`, `runUid`, `skipCount`, `startedAt`, `status`, `steps`, `succeeded`, `successCount`, `unmatchedCount`, `when` | `dry_run`, `duration_s`, `ended_at`, `run_uid`, `started_at` |
| `GET /api/v1/pipeline/history/{runUid}` (`readRun`) | `available`, `detected`, `dryRun`, `durationS`, `elapsedS`, `endedAt`, `errorCount`, `grabbed`, `optionsJson`, `outputTail`, `runUid`, `skipCount`, `startedAt`, `successCount`, `unmatchedCount` | `dry_run`, `duration_s`, `elapsed_s`, `ended_at`, `error_count`, `options_json`, `output_tail`, `run_uid`, `skip_count`, `started_at`, `success_count`, `unmatched_count` |
| `GET /api/v1/pipeline/status` (`readPipeline`) | `blockedCount`, `description`, `duration`, `facts`, `label`, `last`, `name`, `outcome`, `result`, `secondaryLine`, `steps`, `trigger`, `triggers`, `uid`, `watcherDown`, `watcherEnabled`, `when` | `paused`, `pid`, `run_uid`, `step`, `watcher_enabled` |
| `GET /api/v1/staging/media` (`readStaging`) | `absorbedBy`, `at`, `blockedSince`, `blocks`, `chip`, `closure`, `droppedByHand`, `episode`, `failedStep`, `ids`, `keptNewer`, `kind`, `ladder`, `minimumRatio`, `moving`, `name`, `plexMatch`, `poster`, `provider`, `release`, `requester`, `requesters`, `resumedAt`, `resumes`, `rung`, `secondaryLine`, `settled`, `since`, `size`, `steps`, `strip`, `stuck`, `text`, `tone`, `tracker`, `trigger`, `via`, `when`, `winner`, `withoutPoster` | `absent`, `ambiguous`, `awaiting_action`, `blocked_reason`, `category`, `category_id`, `continuation_requested_at`, `counts`, `decision_id`, `decision_trigger`, `disk`, `dispatch_target`, `episode_count`, `folder`, `has_nfo`, `has_poster`, `has_trailer`, `items`, `key`, `label`, `match`, `matched`, `media_kind`, `mode`, `modified_at`, `overview`, `page`, `page_size`, `position_stage`, `position_state`, `poster_url`, `provider_ids`, `relative_path`, `scraped`, `seasons`, `size_bytes`, `stages`, `total`, `video_count`, `with_trailer`, `year` |
| `GET /api/v1/version` (`readVersion`) | `commit` | `build_commit` |
| `PATCH /api/v1/acquisition/followed/{followedId}` (`updateFollow`) | `addedAt`, `aired`, `fresh`, `ids`, `name`, `nextAirDate`, `ownPaused`, `ownQuality`, `paused`, `poster`, `quality`, `requesters`, `searches`, `showStatus`, `since` | `acquiring_count`, `active`, `added_at`, `aired_count`, `announced_count`, `cadence`, `cadence_tier`, `imdb_id`, `last_search_at`, `last_search_found`, `last_search_outcome`, `media_ref`, `movie_facts`, `next_search_at`, `original_title`, `overview`, `owned_count`, `pending_count`, `poster_url`, `priming_running`, `quality_profile`, `season_count`, `series_status`, `tmdb_id`, `to_grab_count`, `tvdb_id`, `tvdb_unresolved`, `unverified_count`, `wanted_grabbed`, `wanted_pending`, `wanted_status` |
| `POST /api/v1/acquisition/detect` (`runDetection`) | `runUid` | `run_uid` |
| `POST /api/v1/acquisition/followed` (`createFollow`) | `addedAt`, `aired`, `fresh`, `ids`, `name`, `nextAirDate`, `ownPaused`, `ownQuality`, `paused`, `poster`, `quality`, `requesters`, `searches`, `showStatus`, `since` | `acquiring_count`, `active`, `added_at`, `aired_count`, `announced_count`, `cadence`, `cadence_tier`, `imdb_id`, `last_search_at`, `last_search_found`, `last_search_outcome`, `media_ref`, `movie_facts`, `next_search_at`, `original_title`, `overview`, `owned_count`, `pending_count`, `poster_url`, `priming_running`, `quality_profile`, `season_count`, `series_status`, `tmdb_id`, `to_grab_count`, `tvdb_id`, `tvdb_unresolved`, `unverified_count`, `wanted_grabbed`, `wanted_pending`, `wanted_status` |
| `POST /api/v1/acquisition/followed/{followedId}/grab` (`grabForFollow`) | `runUid` | `run_uid` |
| `POST /api/v1/acquisition/followed/{followedId}/search` (`searchForFollow`) | `found` | `run_uid` |
| `POST /api/v1/acquisition/follows/{followedId}/seasons/{season}/grab` (`grabSeasonForFollow`) | `absorbedCount`, `queued`, `runUid` | `absorbed_count`, `run_started`, `run_uid`, `season_wanted_id` |
| `POST /api/v1/acquisition/journeys/{infoHash}/requeue` (`requeueJourney`) | `queued`, `runUid` | `run_uid` |
| `POST /api/v1/acquisition/journeys/{infoHash}/rescrape` (`rescrapeJourney`) | `queued`, `runUid` | `run_uid` |
| `POST /api/v1/acquisition/ranking/preview` (`previewRanking`) | `freeleech`, `knownTrackers`, `sizeBytes`, `trackerRatioState` | `is_freeleech`, `known_trackers` |
| `POST /api/v1/auth/login` (`signIn`) | `avatar`, `defaultFor`, `email`, `forbiddenWrites`, `id`, `kind`, `name`, `rights`, `role`, `signInKind` | — |
| `POST /api/v1/auth/logout` (`signOut`) | `ok` | — |
| `POST /api/v1/config/restart-web` (`restartWeb`) | `ok` | `status` |
| `POST /api/v1/decisions/{decisionId}/dismiss` (`dismissDecision`) | `state` | `candidates`, `candidates_count`, `created_at`, `extracted_title`, `extracted_year`, `id`, `media_kind`, `overview`, `poster_url`, `provider`, `provider_id`, `resolution_json`, `score`, `staging_path`, `status`, `title`, `trigger`, `year` |
| `POST /api/v1/decisions/{decisionId}/resolve` (`resolveDecision`) | `state` | `run_uid` |
| `POST /api/v1/decisions/{decisionId}/search` (`searchForDecision`) | `id`, `poster`, `withoutPoster` | `candidates`, `poster_url`, `provider_id` |
| `POST /api/v1/maintenance/actions/{actionId}/run` (`runMaintenanceAction`) | `state`, `uid` | `queued`, `run_uid` |
| `POST /api/v1/pipeline/kill` (`killPipeline`) | — | `paused`, `pid`, `run_uid`, `step`, `watcher_enabled` |
| `POST /api/v1/pipeline/pause` (`pausePipeline`) | — | `paused`, `pid`, `run_uid`, `step`, `watcher_enabled` |
| `POST /api/v1/pipeline/resume` (`resumePipeline`) | — | `paused`, `pid`, `run_uid`, `step`, `watcher_enabled` |
| `POST /api/v1/pipeline/run` (`runPipeline`) | `state`, `uid` | `queued`, `run_uid` |
| `POST /api/v1/pipeline/watcher` (`setWatcher`) | `watcherEnabled` | `watcher_enabled` |
| `POST /api/v1/staging/media/{mediaId}/continue` (`continueStagedMedia`) | — | `deferred`, `detail`, `media_id`, `run_uid` |
| `POST /api/v1/staging/media/{mediaId}/discard` (`discardStagedMedia`) | — | `detail`, `media_id` |
| `POST /api/v1/staging/media/{mediaId}/enqueue` (`enqueueForResolution`) | `candidatesCount`, `candidatesSeeded`, `decisionId`, `mediaKind` | `candidates_count`, `candidates_seeded`, `decision_id`, `media_kind` |
| `PUT /api/v1/config/files/{name}` (`updateConfigurationFile`) | `conflict`, `restartRequired` | `restart_required`, `warnings` |
| `PUT /api/v1/config/secrets` (`updateSecrets`) | `restartRequired` | `restart_required`, `warnings` |

## 2b. Operations both declare, whose path parameter is spelled differently

The interface writes a parameter in camelCase, the backend in snake_case. It is a real
divergence and a small one — the demand is one spelling, and which one is the
operator's call rather than this file's.

| the interface requires | the backend has |
| --- | --- |
| `DELETE /api/v1/acquisition/followed/{followedId}` | `DELETE /api/acquisition/followed/{followed_id}` |
| `GET /api/v1/acquisition/followed/{followedId}/completeness` | `GET /api/acquisition/followed/{followed_id}/completeness` |
| `GET /api/v1/media/{provider}/{providerId}` | `GET /api/media/{provider}/{provider_id}` |
| `GET /api/v1/pipeline/history/{runUid}` | `GET /api/pipeline/history/{run_uid}` |
| `PATCH /api/v1/acquisition/followed/{followedId}` | `PATCH /api/acquisition/followed/{followed_id}` |
| `POST /api/v1/acquisition/followed/{followedId}/grab` | `POST /api/acquisition/followed/{followed_id}/grab` |
| `POST /api/v1/acquisition/followed/{followedId}/search` | `POST /api/acquisition/followed/{followed_id}/search` |
| `POST /api/v1/acquisition/follows/{followedId}/seasons/{season}/grab` | `POST /api/acquisition/follows/{followed_id}/seasons/{season}/grab` |
| `POST /api/v1/acquisition/journeys/{infoHash}/requeue` | `POST /api/acquisition/journeys/{info_hash}/requeue` |
| `POST /api/v1/acquisition/journeys/{infoHash}/rescrape` | `POST /api/acquisition/journeys/{info_hash}/rescrape` |
| `POST /api/v1/decisions/{decisionId}/dismiss` | `POST /api/decisions/{decision_id}/dismiss` |
| `POST /api/v1/decisions/{decisionId}/resolve` | `POST /api/decisions/{decision_id}/resolve` |
| `POST /api/v1/decisions/{decisionId}/search` | `POST /api/decisions/{decision_id}/search` |
| `POST /api/v1/maintenance/actions/{actionId}/run` | `POST /api/maintenance/actions/{action_id}/run` |
| `POST /api/v1/staging/media/{mediaId}/continue` | `POST /api/staging/media/{media_id}/continue` |
| `POST /api/v1/staging/media/{mediaId}/discard` | `POST /api/staging/media/{media_id}/discard` |
| `POST /api/v1/staging/media/{mediaId}/enqueue` | `POST /api/staging/media/{media_id}/enqueue` |

## 2c. Operations both declare, answered with a different status

**A STATUS IS A DEMAND, and it was invisible here until 2026-09-06.** The comparison
above reads property NAMES; two documents can agree on every name and still disagree
on what the answer means. `POST /api/acquisition/journeys/{infoHash}/requeue` is the
case this table was built for: the backend answers **409** when a requeue for the item
is already in flight, and NE-DOIT-PAS-3 with §20 forbid the interface showing that — an
ask at the bound is QUEUED, visibly, never refused. So the interface declares a queued
202 and the difference is recorded rather than reconciled.

**Most rows here predate the lot that built the table.** Twelve operations already
disagreed, and they are the backend's own business — a 202 where the interface expects
a 200 is not a defect in either document, it is a decision nobody had written down.

| operation | operationId | the interface requires | the backend answers |
| --- | --- | --- | --- |
| `DELETE /api/v1/acquisition/followed/{followedId}` | `deleteFollow` | `200` | `204` |
| `POST /api/v1/acquisition/followed` | `createFollow` | `200` | `201` |
| `POST /api/v1/acquisition/followed/{followedId}/search` | `searchForFollow` | `200` | `202` |
| `POST /api/v1/acquisition/follows/{followedId}/seasons/{season}/grab` | `grabSeasonForFollow` | `200`, `201` | `201` |
| `POST /api/v1/auth/login` | `signIn` | `200` | `204` |
| `POST /api/v1/auth/logout` | `signOut` | `200` | `204` |
| `POST /api/v1/config/restart-web` | `restartWeb` | `200` | `202` |
| `POST /api/v1/decisions/{decisionId}/resolve` | `resolveDecision` | `200` | `202` |
| `POST /api/v1/maintenance/actions/{actionId}/run` | `runMaintenanceAction` | `200` | `202` |
| `POST /api/v1/pipeline/run` | `runPipeline` | `200` | `202` |
| `POST /api/v1/staging/media/{mediaId}/continue` | `continueStagedMedia` | `200` | `202` |

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

- `GET /api/acquisition/journeys`
- `GET /api/acquisition/lookup`
- `GET /api/acquisition/overview`
- `GET /api/acquisition/stalled-grabs`
- `GET /api/acquisition/wanted`
- `GET /api/decisions/activity`
- `GET /api/decisions/{decision_id}`
- `GET /api/health`
- `GET /api/pipeline/stages`
- `GET /api/registry/status`
- `GET /api/staging/media/{media_id}/poster`
- `POST /api/config/validate`
