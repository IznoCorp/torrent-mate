# What the interface asks of v1

**COMPUTED, NEVER WRITTEN.** `python3 scripts/compare-contracts.py --write --have v1`
builds this file by diffing `contract/openapi.json` — the contract the
interface REQUIRES — against `contract/openapi.generated.json`, which
`python scripts/export-openapi.py --v1` generates FROM the v1 application.
`--check --have v1` refuses a committed register that differs from the computed one, so
the two cannot separate. Edit the contract or v1, not this file.

**ITS ROW COUNT IS THE MEASURE OF THE BACKEND'S END**: v1 is done when sections 1, 2,
2b, 2c and 4 read « None. » (section 3 is a demand on the contract's fields, which v1
answers as declared). The v0 register, `docs/reference/frontend-backend-demands.md`,
compares the same contract against today's backend; this one does not replace it.

**BOTH SIDES ADDRESS EVERY OPERATION UNDER `/api/v1`**: the contract's `servers` URL, and
where the web application mounts v1. Operations are matched on the path below it.

**IT DESCRIBES OPERATIONS, AND A WEBSOCKET IS NOT ONE.** OpenAPI cannot declare
`/api/v1/events`; the stream's demands are written by hand in
`docs/reference/frontend-backend-demands-stream.md`.

**A SERVED OPERATION IS HELD TO MORE THAN THIS.** Names and statuses are what a register
can carry; `tests/http_v1/test_contract_conformance.py` holds every operation v1 serves to
the contract field by field — enums, required sets, request bodies, refusals and rights.

| | |
| --- | ---: |
| operations the interface requires | 103 |
| operations v1 serves | 18 |
| required and not served | 85 |
| served, different response shape | 0 |
| served, path parameter spelled differently | 0 |
| served, answered with a different status | 0 |
| fields carried pre-formatted | 22 |
| v1 serves and the interface does not declare | 0 |

---

## 1. Operations the interface requires and v1 does not serve

| operation | operationId | what it is for |
| --- | --- | --- |
| `DELETE /api/v1/acquisition/downloads/{infoHash}` | `removeDownload` | Remove one entry from the download client, its files deleted or kept |
| `DELETE /api/v1/acquisition/followed/{followedId}` | `deleteFollow` | Stop following |
| `DELETE /api/v1/library/items` | `deleteLibraryItems` | Delete media from the library, by provider identity |
| `DELETE /api/v1/staging/media/{mediaId}` | `deleteStagedMedia` | Delete a staged folder from the disk |
| `DELETE /api/v1/staging/media/{mediaId}/reclassify` | `restoreReclassifiedMedia` | Put a reclassified folder back in the staging area |
| `DELETE /api/v1/torrents/{infoHash}/cross-seed/exclusions` | `undoCrossSeedExclusion` | Lift an exclusion, of one pair or of a whole title |
| `GET /api/v1/acquisition/downloads` | `readDownloads` | Every entry the download client holds, one per tracker it is active on |
| `GET /api/v1/acquisition/followed` | `readFollows` | Everything being followed |
| `GET /api/v1/acquisition/followed/{followedId}/completeness` | `readFollowCompleteness` | What has aired against what the library holds, season by season, for one follow |
| `GET /api/v1/acquisition/journeys/{infoHash}` | `readJourney` | One medium's ladder, rung by rung |
| `GET /api/v1/acquisition/obligations` | `readObligations` | Every seeding obligation, open or ended |
| `GET /api/v1/acquisition/releases` | `readReleases` | The release candidates for one wanted item |
| `GET /api/v1/acquisition/search` | `searchProviders` | Search the providers for a title to follow |
| `GET /api/v1/acquisition/search/by-id` | `searchProviderById` | Find the one medium a source knows under an identifier |
| `GET /api/v1/acquisition/status` | `readAcquisitionStatus` | The grab cadence, and when the next search runs |
| `GET /api/v1/acquisition/suggestions` | `readSuggestions` | Titles worth following, and why |
| `GET /api/v1/acquisition/to-handle` | `readAcquisitionQueue` | What the acquisition side is holding, by bucket |
| `GET /api/v1/config/files` | `readConfigurationFiles` | The configuration files, and which have pending edits |
| `GET /api/v1/config/files/{name}` | `readConfigurationFile` | Read one configuration file's content |
| `GET /api/v1/config/schema` | `readSettings` | Every setting, by topic |
| `GET /api/v1/config/secrets` | `readSecrets` | Which secrets are defined — never their values |
| `GET /api/v1/config/status` | `readConfigurationStatus` | Whether a restart is owed |
| `GET /api/v1/decisions/` | `readDecisions` | The decisions awaiting arbitration, and those already settled |
| `GET /api/v1/library/categories` | `readLibraryCategories` | The engine's leaf categories and their counts |
| `GET /api/v1/library/incomplete` | `readLibraryIncomplete` | The series with holes, and how big each hole is |
| `GET /api/v1/library/items` | `readLibraryItems` | The library listing, one page of it |
| `GET /api/v1/library/membership` | `readLibraryMembership` | Whether the library holds one medium, asked by its provider identity |
| `GET /api/v1/library/recent` | `readLibraryRecent` | The most recently added titles |
| `GET /api/v1/maintenance/actions` | `readMaintenanceActions` | The maintenance actions, and how risky each is |
| `GET /api/v1/maintenance/destructive-log` | `readDeletionJournal` | What has been deleted, and when |
| `GET /api/v1/maintenance/disks` | `readDisks` | The disks, and how full each is |
| `GET /api/v1/maintenance/index-health` | `readIndexHealth` | The indexer's own figures |
| `GET /api/v1/maintenance/locks` | `readLocks` | What holds the pipeline, whether it is paused, whether the automatic trigger is paused, and what temporary entries a crash left behind |
| `GET /api/v1/maintenance/schedulers` | `readSchedulers` | The schedulers, their cadence and their last pass |
| `GET /api/v1/media/{provider}/{providerId}/cross-seed` | `readMediaCrossSeed` | The medium's cross-seed, tracker by tracker |
| `GET /api/v1/notifications/preferences` | `readNotificationPreferences` | The signed-in account's notification switches, one per type it may receive |
| `GET /api/v1/pipeline/history` | `readPipelineHistory` | The recent runs, a page at a time, and whether the list can be trusted |
| `GET /api/v1/pipeline/history/{runUid}` | `readRun` | One passage: what triggered it, how it ended, its steps with their counts and their reasons, and its raw output |
| `GET /api/v1/pipeline/status` | `readPipeline` | The pipeline, its nine steps, and its last run |
| `GET /api/v1/staging/destinations` | `readStagingDestinations` | Where the sort files what is not a medium |
| `GET /api/v1/staging/media` | `readStaging` | What is in the staging area, by bucket |
| `GET /api/v1/staging/media/{mediaId}/copies` | `readStagedMediaCopies` | Whether a staged folder is the only copy of its files — POSED in the maquette (RULINGS 22); the backend reads the torrent's presence in qBittorrent at the gesture |
| `GET /api/v1/system/dependencies` | `readDependencies` | The external dependencies, and whether each answers |
| `GET /api/v1/system/errors` | `readErrors` | How many errors, out of how many runs, and the latest |
| `GET /api/v1/system/services` | `readServices` | The services, and whether each answers |
| `GET /api/v1/trackers` | `readTrackers` | Every configured tracker, its ratio, volumes, trend, alert threshold and health |
| `PATCH /api/v1/acquisition/followed/{followedId}` | `updateFollow` | Pause or resume a follow |
| `POST /api/v1/acquisition/detect` | `runDetection` | Look now for everything that could be taken |
| `POST /api/v1/acquisition/followed` | `createFollow` | Follow a title |
| `POST /api/v1/acquisition/followed/{followedId}/grab` | `grabForFollow` | Claim now what the last search found for one follow |
| `POST /api/v1/acquisition/followed/{followedId}/restore` | `restoreFollow` | Put a removed follow back, as it was |
| `POST /api/v1/acquisition/followed/{followedId}/search` | `searchForFollow` | Search now for one follow |
| `POST /api/v1/acquisition/follows/{followedId}/seasons/{season}/grab` | `grabSeasonForFollow` | Take one season of a medium, following it first if it is not followed yet |
| `POST /api/v1/acquisition/journeys/{infoHash}/closure/seen` | `dismissClosure` | Mark one closed tunnel seen, for the caller — the seen mark stored per account (BK5); the engine closes the tunnel itself, its medium vanished (BK3) or a later choice in place (BK4) |
| `POST /api/v1/acquisition/journeys/{infoHash}/plex-match` | `resolvePlexMatch` | Confirm or correct the match Plex made for a medium — the Plex match's CORRECTION VERB, OPEN 9's fifth demand; the disagreement is POSED in the maquette (RULINGS 24), the backend compares Plex's real match with the identity held |
| `POST /api/v1/acquisition/journeys/{infoHash}/requeue` | `requeueJourney` | Put one journey back in the queue |
| `POST /api/v1/acquisition/journeys/{infoHash}/rescrape` | `rescrapeJourney` | Re-scrape one journey's tracked item |
| `POST /api/v1/acquisition/ranking/preview` | `previewRanking` | Score the preview's fixed sample set under a candidate ranking |
| `POST /api/v1/acquisition/requesters/reassign` | `reassignRequester` | Move one requester of an acquisition to another account |
| `POST /api/v1/config/restart-web` | `restartWeb` | Restart the web process so a change takes |
| `POST /api/v1/decisions/{decisionId}/dismiss` | `dismissDecision` | Leave the folder as it is |
| `POST /api/v1/decisions/{decisionId}/reopen` | `reopenDecision` | Re-open a settled decision for arbitration, with the candidates a provider search finds |
| `POST /api/v1/decisions/{decisionId}/resolve` | `resolveDecision` | Choose a candidate and re-scrape |
| `POST /api/v1/decisions/{decisionId}/search` | `searchForDecision` | Search the providers by hand for one decision |
| `POST /api/v1/maintenance/actions/{actionId}/run` | `runMaintenanceAction` | Run one maintenance action |
| `POST /api/v1/notifications/devices` | `registerPushDevice` | Register this device's push token for the signed-in account (K5) |
| `POST /api/v1/pipeline/kill` | `killPipeline` | Stop the run |
| `POST /api/v1/pipeline/pause` | `pausePipeline` | Pause the run |
| `POST /api/v1/pipeline/resume` | `resumePipeline` | Resume the run |
| `POST /api/v1/pipeline/run` | `runPipeline` | Start a run, or queue one visibly |
| `POST /api/v1/pipeline/watcher` | `setWatcher` | Turn the automatic trigger on or off, and say which it now is |
| `POST /api/v1/staging/media/{mediaId}/continue` | `continueStagedMedia` | Send a staged item back through the pipeline |
| `POST /api/v1/staging/media/{mediaId}/discard` | `discardStagedMedia` | Quarantine a staged folder |
| `POST /api/v1/staging/media/{mediaId}/enqueue` | `enqueueForResolution` | Send a staged medium to arbitration: a pending decision, with the candidates a provider search found |
| `POST /api/v1/staging/media/{mediaId}/reclassify` | `reclassifyStagedMedia` | File a folder that is not a medium where the sort files its kind |
| `POST /api/v1/torrents/{infoHash}/cross-seed/search` | `searchCrossSeed` | Search a cross-seed for one torrent, on one tracker or on every eligible one |
| `POST /api/v1/torrents/{infoHash}/cross-seed/{tracker}/cut` | `cutCrossSeed` | Cut one torrent's cross-seed on one tracker |
| `POST /api/v1/torrents/{infoHash}/cross-seed/{tracker}/upload` | `uploadCrossSeed` | Create a torrent from one origin's files and publish it on one tracker |
| `POST /api/v1/trackers/{tracker}/broken-obligations/{infoHash}/seen` | `markBrokenObligationSeen` | Mark one broken obligation of a tracker seen |
| `PUT /api/v1/acquisition/followed/{followedId}/pause` | `setAcquisitionPause` | Set the caller's pause on one acquisition |
| `PUT /api/v1/acquisition/followed/{followedId}/quality` | `setAcquisitionQuality` | Set the caller's quality profile on one acquisition |
| `PUT /api/v1/config/files/{name}` | `updateConfigurationFile` | Write one configuration file |
| `PUT /api/v1/config/secrets` | `updateSecrets` | Set secret values |
| `PUT /api/v1/notifications/preferences/{type}` | `updateNotificationPreference` | Switch one notification type on or off for the signed-in account |
| `PUT /api/v1/torrents/{infoHash}/cross-seed/exclusions` | `writeCrossSeedExclusion` | Exclude one pair, or a whole title, from the engine's future cross-seed passes |

## 2. Operations both declare, whose response carries different property names

None.

## 2b. Operations both declare, whose path parameter is spelled differently

None.

## 2c. Operations both declare, answered with a different status

None.

## 3. Fields the interface carries pre-formatted

The demand is the same for every one of them: supply the underlying fact and let the
interface format it.

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

## 4. Operations v1 serves and the interface does not declare

v1 is written from the contract, so a row here is a defect: the contract declares it, or
v1 drops it.

None.
