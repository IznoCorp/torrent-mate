# The backend brief

**Status: the operator's rulings of 2026-10-01 and 2026-10-02 are written in (§ 5, DECIDED); the lots of § 6 follow
them.** The plan is a new application layer and a new HTTP v1 on the kept engine (§ 5 Q11); where a ruling of
2026-10-02 replaces one of 2026-10-01, the earlier one is marked SUPERSEDED with its date, never deleted.
`backend-demands-architecture.md` says the backend's work
« will carry another letter, in a backend brief written once the maquette is finished » (operator, 2026-08-30). Every
drawn lot is merged (`main` `27b304157`, 0.98.125) and the freeze is reached at L24's close (`IMPLEMENTATION.md`).
This is that brief. It schedules the backend mission's lots — letter **K** (the maquette's lots carry L) — and
records the questions only the operator answers, with his rulings (§ 5).

**Its inputs**, never repeated here in full: the constitution (`product-intent.md`, §§ cited per row); the
operator's principles (`operator-method.md` § 1) and his « Environnements et back-end » decisions (§ 3); the
architecture decisions (`backend-demands-architecture.md`, cited « arch § n »); the computed register
(`frontend-backend-demands.md`, cited « reg § n », in sync with the contract at `27b304157`:
`compare-contracts.py --check` green); the stream register (`frontend-backend-demands-stream.md`, cited « stream
§ n »); the maquette's contract (`frontend/maquette/contract/openapi.json`, 93 operations); the lots' DESIGNs for
their lettered demands (L16-bis T1–T3, L17 A–K, L18 C–P, L23 Q–S, L24 A–D, season recovery SR1–SR6);
`IMPLEMENTATION.md` § « Carried to the backend mission ».

**His rules this brief is held to** (`operator-method.md` § 1):

- « Le back-end : on reprend ce qui existe (adapter, réarchitecturer, transformer), refaire seulement s'il le
  faut » (09-12) — every row of § 2 says which of the four it is.
- « On n'est pas obligé de reprendre toutes les données telles quelles. On n'est pas encore en production » ;
  « on pourrait […] réimaginer des bases de données » ; « ce serait bien d'avoir une vraie staging » (09-27) — § 3,
  § 4.
- « A, pas de gestion de rétro-compatibilité ! » (09-29) — no alias, no migration script kept for a shape that dies;
  the v0 surface is FROZEN and deleted in one block at the switchover (§ 5 Q1 as amended by Q11 — `/api/v1` is the
  new backend's permanent prefix, not a temporary one).
- The backend follows the interface (§ 15): a divergence is settled on the contract's side unless the contract is
  shown wrong, and a backend limitation is recorded, never a reason for the interface to draw less.
- The acquired backend decisions were held as « realigned, never razed »; on 2026-10-02 he reopened them
  (« je veux qu'on pèse tout, et qu'on remette en question les decisions ») and ruled the shape D (§ 5 Q11). Each
  keeps its PRINCIPLE; two lose their letter:
  - `web/staging/stages.py` as the single stage taxonomy — one taxonomy still, but it is the contract's LADDER (eight
    rungs from the wish to Plex); `compute_position` and the « one position » rule move into the tunnel service, the
    eight staging stages become the sub-steps of « rangé » and « enrichi », their French reasons become codes (X4);
  - the resolve queue (#287 — true parallel resolves were REFUSED on proof of construction: every step mutates the
    item) — the proof stands and is the same rule as one tunnel per release (Q6); the mechanism is replaced: a
    resolve becomes a tunnel's resume in the supervisor's queue (Q5), never a second queue beside it (NE-DOIT-PAS-7);
  - kept as they are: the canonical resolution write (#260, a scraper kernel the tunnel calls), the completeness
    read-model and `acquire/reconcile.py`, the deletion authority on seed obligations.

**Two anti-decisions fall.** `docs/production/architecture.md` § « Anti-decisions » lists « No multi-user / no
RBAC »: § 17 (dictated 2026-08-26, completed 08-30 and 09-27) overrules it. Its « No microservices » entry also
says « one process per command »: that half falls to the supervisor of § 5 Q5, which runs the tunnels as its workers,
the CLI becoming one of its clients (no service split follows — the rest of the entry stands). The brief treats both
as void.

---

## 1. What the interface needs

The union of the two registers, the architecture file and the lots' lettered demands, deduplicated, by domain.
« **new** » = the contract declares it and the backend does not serve it (reg § 1, 40 operations); « **reshape** » =
both declare it and the answer differs (reg § 2, 53 operations); « **engine** » = no operation, a behaviour of the
engine. The cross-cutting divergences come first because every domain carries them.

### 1.0 Cross-cutting — every operation

| Demand | What | Source |
| --- | --- | --- |
| **X1 — the failure shape** | every refusal answers `Problem {status, title, detail}`; today FastAPI's `{detail}` makes the maquette's `isRequestFailure` take the outage branch and QUEUE an action the server refused (401, 403, 409, 422). The binding's first gesture | arch § 6, B-267, NE-DOIT-PAS-1/5 |
| **X2 — names** | the contract's property names (camelCase) on 53 reshaped answers; one spelling of the 17 path parameters (reg § 2b, « the operator's call » — § 5 intro) | reg § 2, § 2b |
| **X3 — statuses** | the 11 status divergences (202/201/204 where the contract says 200); `requeueJourney`'s 409 becomes a visible queue — the only refusal left is idempotence | reg § 2c, § 6, DOIT-4, NE-DOIT-PAS-3 |
| **X4 — facts, not sentences** | the 25 pre-formatted fields (`when`, `secondaryLine`, `duration`, `reason`, `kind`…) become the underlying fact (epoch, counts, codes); the interface owns every word through `fr.json`. Système's facts are STATE CODES (conformity Q2 = A); a run's narrative is codes + parameters, never French on the wire | reg § 3, arch § 15, stream § 7, DOIT-1, NE-DOIT-PAS-4 |
| **X5 — year and kind on every card** | `QueueCard`, `LibraryItem`, `LibraryRow`, `IncompleteShow` carry `year` and `kind` as first-class fields (ruling 55, reading B); `PendingDecision.kind` is the enum `movie \| show` | arch § 10, § 13 |
| **X6 — a right on every route** | every operation authorised by ONE path reading the account's role's rights and the instance's forbidden writes; every read under `/api/system`, `/api/maintenance`, `/api/trackers`, `/api/config` declares `403` for a non-holder (L18 F30); `require_not_staging` absorbed | arch § 2, § 17.3, NE-DOIT-PAS-7, L18 N |

### 1.1 Acquisition — follows, cards, « À traiter », the tunnel

| Operation / behaviour | Kind | What it must do | § | Demand ids |
| --- | --- | --- | --- | --- |
| `readFollows`, `createFollow`, `updateFollow` | reshape | a follow carries `requesters[]`, the caller's `ownQuality` / `ownPaused` and the effective `quality` / `paused` (the highest quality wins among requesters whose role holds the right; paused only when every holder asked), `showStatus`, `aired`, `searches`, `fresh` | §5, §17 | arch § 2, § 3; L18 K, P |
| `deleteFollow` | reshape | removes the CALLER as requester; the follow ends with its last requester; `200 {ok}` | §17 | arch § 2 |
| `restoreFollow` | new | puts a removed follow back as it was (the undo of a removal) | DOIT-7 | reg § 1 |
| `setAcquisitionQuality`, `setAcquisitionPause` | new | the caller's per-acquisition override, honoured on the whole acquisition path (search, rank, grab, re-switch) | §9, §17 | arch § 3; L18 K, P |
| `reassignRequester` | new | moves ONE requester off a follow or a card onto another account (`acquisition.reassign`) | §17 | L18 I; ruling 9 |
| `readAcquisitionQueue` (`to-handle`) | reshape | the cards of « En cours » and « À traiter »: one card per ACQUISITION (film, episode, season — ruling 1), its rung on the eight-rung ladder (Rd 5 Q4), `requesters`, `trigger` (`manual \| automatic`, SR5), `season` / `episode` / `absorbedBy` (SR1), `release` (SR4), `plexMatch`, `failedStep`, `droppedByHand`, `minimumRatio` + `tracker` of a ratio deferral | §14, §20, ruling 1–7, 19 | SR1, SR4, SR5; arch § 4 (F14) |
| `readJourney` | new | the ladder rung by rung, keyed by the ACQUISITION (wanted row), not the title; « enrichi » unfolded into metadata / posters / trailer (L24 OPEN 5 = B); a step not known reads « unknown », never « not done » | §14.3, Rd Q14 = A | SR4; L24 |
| `requeueJourney`, `rescrapeJourney` | reshape | `{queued, runUid}`; an ask at the bound is queued, visibly | §6 | reg § 2c |
| `resolvePlexMatch` | new | confirm or correct the match Plex made (« Confirmer » / « Corriger » on the card, Rd 5 Q9); the engine compares Plex's real match with the identity held | §4 | reg § 1 (OPEN 9 fifth demand) |
| `grabSeasonForFollow` | reshape | addressed by the MEDIUM, followed or not (a medium nobody follows has no follow rowid today). For an unfollowed owned show it creates a ONE-OFF acquisition (`via: request`) carrying « Suivre » — never a follow: Rd 10 Q2 (09-27) supersedes arch § 7's implied follow (09-11) and its `newlyFollowed`, which the contract no longer declares. Answers `queued`, `reused` (a live recovery of that season already ran), `absorbedCount` (counted on AIRED, not owned episodes — B-380, ruled 09-11: « Manquant : les épisodes diffusés et non possédés ! ») | DOIT-3, §17 | arch § 7 (as amended by Rd 10 Q2) |
| season recovery | engine | while a season wanted is open, the per-episode enqueue and grab paths skip that season's episodes (SR3); an episode's own card is ABSORBED (conformity Q6 = A); an episode already `grabbed` at the ask is neither cancelled nor filtered: at filing the LAST CHOSEN release wins (§ 5 Q9); the season-pack guards (#489 `filter_to_season`, #542 fallback) compose with the exclusion | §20 | SR1–SR3, SR6 |
| `readReleases` | new | the release candidates of one wanted item, each row with its parsed `season` / `episode` (the picker never parses a name) | §9 | SR6 |
| `previewRanking` | reshape | `trackerRatioState`: a release from a low-ratio tracker loses points | §18 | arch § 4 |
| `readSuggestions` | new | titles worth following, and why (Découvrir); « passer » is local (Rd 09-30 Q4 = A), « rejeter » is written | §5 | reg § 1 |
| `searchProviders`, `readFollowCompleteness`, `readAcquisitionStatus`, `runDetection`, `grabForFollow`, `searchForFollow` | reshape | names (X2), `followed` / `owned` on a search result, `cadence` / `nextSearch`; `grabForFollow` declares `403` | §5, DOIT-6 | L18 L; L24 B |
| `readStaging`, `continueStagedMedia`, `discardStagedMedia`, `enqueueForResolution` | reshape | the staged medium as a card (same card fields as the queue) | §3, §4 | L24 A |
| `deleteStagedMedia`, `reclassifyStagedMedia`, `restoreReclassifiedMedia`, `readStagingDestinations`, `readStagedMediaCopies` | new | « Mis de côté »'s real deletion, confirmed (ruling 16); file a non-medium where the sort files its kind, and its undo; whether a staged folder is the only copy (the torrent's presence in qBittorrent at the gesture) | §7, NE-DOIT-PAS-6 | reg § 1 |
| a resolve's inverse | engine | « remettre en attente »: a settled folder goes back in the queue, so the undo window need not hold the send | DOIT-7 | arch § 9 |
| `readDecisions`, `resolveDecision`, `dismissDecision`, `searchForDecision` | reshape | a settled decision carries `id`, `candidatesCount`, `settledBy: operator \| engine` — an identification the engine made ALONE is written as a decision row | §3, ruling L24 OPEN 1 = C | L24 D |
| `reopenDecision` | new | « Corriger »: a settled decision back to arbitration with the candidates a provider search finds, a shelved medium's included | DOIT-7 | L24 |
| the tunnel | engine | one execution per ARRIVAL, followed to its Plex match; N in parallel under `pipeline.tunnels.max_parallel`, the rest queued visibly; a block ENDS the execution and persists its state, step, reason and what resumes it; a resume verb; one trigger authority; a block of an EXTERNAL cause resumes on its own when the engine sees it lifted; every blocked tunnel is an « À traiter » card with its cause, what lifts it and where | §20, §4, §6, NE-DOIT-PAS-7 | arch § 1, § 12 — § 5 Q5–Q9 |

### 1.2 Library — the listing and the sheet

| Operation / behaviour | Kind | What it must do | § | Demand ids |
| --- | --- | --- | --- | --- |
| `readLibraryItems`, `readLibraryCategories`, `readLibraryRecent`, `readLibraryIncomplete` | new | the listing (one page; each row its facts — `year`, `kind` — never a pre-formatted line), the ENGINE'S LEAF categories and their counts (the interface groups them into lenses and names them, K2-G5 = A), the recent, the series with holes and each hole's size — « manquant » = aired and not owned; the category filters on all three tabs | §11, DOIT-11 | reg § 1; X5 |
| `readLibraryMembership` | new | whether the library holds one medium, asked by its PROVIDER ID (TVDB first for a show — § 5 Q15), never a title nor a fuzzy match; carries the medium's kind; `rows` counts the rows holding the id, two or more a duplicate. The contract carries it | §11, §13 | arch § 11; B-581; § 5 Q15 |
| `readMediaSheet` | reshape | the sheet's facts (synopsis — absent from `library.db` today —, cast with portraits, trailer, hero, runtime, rating, `metadataRefreshedAt`), a FILM variant with no seasons block | §11 | reg § 2; IMPLEMENTATION carry |
| `readMediaSeasons` | new | the seasons of a show and what the library holds of each, aired vs announced said apart | §5, §9 | reg § 1; B-380 |
| `rescrapeMedia` | new | ask the providers for one medium's metadata again | DOIT-3 | reg § 1 |
| `deleteLibraryItems` | new | delete media named by their provider ids (`{media: [{provider, providerId}]}`), confirmed; refused, nothing deleted: 404 `media.not_found`, 409 `media.ambiguous` while an id names two rows or folders (O-5 = B), 409 `library.locked` while the pipeline holds its lock; written to the append-only destructive journal, refused on preprod (`library.delete` in its forbidden writes); the Plex deletion route with it | §7, NE-DOIT-PAS-6 | reg § 1; ruling 23; IMPLEMENTATION carry |
| `readMediaCrossSeed` | new | the sheet's per-tracker cross-seed block, gated by `trackers.view` | §19 | L18 C |

### 1.3 Trackers — ratio, obligations, cross-seed, upload

| Operation / behaviour | Kind | What it must do | § | Demand ids |
| --- | --- | --- | --- | --- |
| `readTrackers` | new | every configured tracker as a subject: the ratio the TRACKER recognises, Download / Upload volumes, trend, its alert threshold, its HEALTH (a refused credential and since when), its `disabled {by: failure, reason, since}`, its cross-seed summary `{enabled, engineEnabled, active, failed, lastInjectedAt}`, its « accepte les uploads » switch | §18, §19, DOIT-13 | arch § 4; L16-bis T2; L17 A; Rd 9 Q1 |
| `readDownloads` | reshape | every qBittorrent entry: dates, swarm, BOTH rates and volumes, poster, folder, provenance (grab, direct add, cross-seed, upload — the third origin mark), the deferral's KIND (ratio / space / missing content) with the tracker and ITS `min_ratio`; on the origin entry, one `CrossSeedPair` per other eligible tracker (six states, reason, `stoppedAt`, `stopCause`, `via: search \| upload`, exclusion flags) | §8, §18, §19 | L16-bis T3; L17 B; L23 S; arch § 4 (F14) |
| `readObligations` | reshape | names, plus `crossSeedOf {infoHash, title, media}` | §18, §19 | L17 D |
| `removeDownload` | new | « Retirer de qBittorrent »: an entry and every entry sharing its files, files deleted by default and decheckable, answering which trackers held a running obligation; the obligation closes « libérée », never « en infraction »; an outside removal is reconciled and SAID | §18, NE-DOIT-PAS-5 | arch § 4; Rd 9 Q7 |
| `markBrokenObligationSeen` | new | a broken obligation of a departed torrent, folded on its tracker's entry and effaceable | §18 | Rd 10 Q4 |
| `searchCrossSeed` | new | one torrent, one tracker or every eligible one; « en file » under throttle; bounded by the daily quota and delay ONLY | §19, NE-DOIT-PAS-8 | L17 E |
| `cutCrossSeed` | new | removes the pair's entry WITHOUT its files, closes its obligation « libérée », marks the pair « stoppé », and remembers the cut | §19 | arch § 5; Rd 9 Q5, Q8 |
| `writeCrossSeedExclusion`, `undoCrossSeedExclusion` | new | a pair or a whole title excluded from every future pass; undo without confirmation | §19 | L17 K; Rd 9 Q11 = C |
| `uploadCrossSeed` | new | creates a `.torrent` from an ACTIVE, complete, seeding torrent's files and publishes it on one tracker that accepts uploads; the backend applies the tracker's rules and answers a refusal with its reason; failures `creation_failed` / `publish_failed` count at the badge | §19 point 5 | L23 Q, R, S; Rd 11 Q1–Q5 |
| the per-tracker switches | config | `tracker.providers.<name>.cross_seed`, `.accepts_uploads` and `.economy.alert_threshold` (default 1.2) through the EXISTING `updateConfigurationFile` — one write, two doors; `stopRunningCrossSeeds` on the switch's cut | §18, §19 | L17 G; arch § 4 |
| the cross-seed engine | engine | attempts EVERY eligible switched-on tracker (not the first verified injection); keeps a state for the pairs no event fires for; active by default AT THE SWITCHOVER, never before | §19 | L17 B (fact 16), H |
| three more trackers | engine | `v3x.club`, `draupnirr.xyz`, `digitalcore.club` as providers (search, grab, ratio, cross-seed), each with the `c411` block | §18 | L16-bis T1 |
| a failing tracker switches itself off | engine | persistent 401/403 or open circuit ⇒ `enabled: false` with its reason; a re-activation refused (422) while it persists; an event | §8 | L16-bis T2 |
| the ratio alert by push | platform | FCM (Firebase project, web push on the installed PWA, Android and iOS); the threshold defaults to 1.2, per tracker; Telegram is not the channel | §18 | arch § 4 — § 5 Q10 |

### 1.4 Accounts and rights

| Operation / behaviour | Kind | What it must do | § | Demand ids |
| --- | --- | --- | --- | --- |
| `readAccount` (`/api/auth/me`), `signIn` | reshape | the role (name for display, kind `admin \| ordinary`, `defaultFor` — O-K1-4: no Default role), the closed set of rights (the contract's `Right` enum), the account's `signInKind`, the entry page, the instance's `forbiddenWrites` | §17, DOIT-12 | L18 D; arch § 2 |
| `signInWithPlex`, `startPlexSignIn` | new | Plex SSO by PIN (`202 {pending}` while unclaimed); the server's owner is created on Admin, every other first sign-in on its Plex kind's starting role (`Role.defaultFor`, O-K1-4); an e-mail matching a local account LINKS it and drops its role to that starting role; a Plex identity without access to the server refused `auth.refused`. The `auth.password` right is RETIRED: the password door is the account's `signInKind` (`owner \| plex \| local`) — the operator, 2026-10-03, « A » | §17 | L18 E; G-4 |
| `signOut` | reshape | `200 {ok}` | — | reg § 2c |
| `readAccounts`, `createAccount`, `updateAccount`, `resetAccountPassword`, `setAccountAccess`, `changeOwnPassword` | new | the roster and the roles; a local account's mandatory e-mail and its PROVISIONAL password, set by the Admin at creation and on a reset (local accounts only — never the owner's CLI-held fallback, never a Plex-linked account), changed by the account in Profil; one role per account (the operator, 2026-10-03, « A »); an account's sign-in allowed or cut by an Admin (`AccountSummary.signInAllowed`) — a cut ends every session of the account, its later sign-ins refused `auth.access_disabled` once its credentials are proven; never the owner, never the Admin's own; the Admin check before `account.unknown` (the operator: Q4 = A, Q5 = A, OPEN-3 B) | §17 | L18 F, G, H; G-5 |
| `createRole`, `updateRole`, `deleteRole` | new | ordinary roles: name, rights; refuses the last-Admin demotion and any escalation (a non-Admin manager grants only a SUBSET of its own role's rights) server-side; a role is created under the name TYPED — a blank one refused `role.name_required`, one another role carries `role.name_taken` (today's `createRole` stores a blank name as none) — and deleted only when no account holds it (`role.in_use`) and no newcomer starts on it (`role.default`, ruling A), never Admin's (the operator, 2026-10-04) | §17 | L18 H; Rd 9 Q14 |
| the authorisation | engine | ONE path: rights from the role, Admin bypassing; membership in `requesters` for « ses propres acquisitions »; refused with `403 Problem` when forced, on VIEWS too | §17, NE-DOIT-PAS-7 | arch § 2; X6 |
| a role that opens no page | engine | the entry page is a dedicated route, never a refusal at sign-in | ruling 22 | arch § 2 |
| existing acquisitions | data | attributed to the Plex server's owner account (Izno); a direct qBittorrent add the same, reassignable | ruling 9 | arch § 2 |

### 1.5 Système, Maintenance, Réglages

| Operation / behaviour | Kind | What it must do | § | Demand ids |
| --- | --- | --- | --- | --- |
| `readServices`, `readDependencies`, `readErrors` | new | the services and dependencies with a state CODE each (« joignable »…); errors out of runs, and the latest | §8, conformity Q2 | reg § 1; arch § 15 |
| `readPipeline` | reshape | the global levers (§20.3): the parallelism bound, pause / resume, the downloads' automatic processing (`watcherEnabled`, and `watcherDown` — a technical fault told from a person's stop, Rd 09-30 Q3), the last run's facts | §1, §20 | reg § 2; IMPLEMENTATION carry |
| `pipeline.tunnels.max_parallel` | config | the new key, `service` topic | §20.1 | arch § 12 |
| `readPipelineHistory`, `readRun` | reshape | a failed run's steps up to and including the failing one, named; the summary's counts including BLOCKED (no N+1) | DOIT-6 | arch § 12 |
| `readLocks` | reshape | a MAINTENANCE run's hold drawn, not the pipeline's alone | §6 | arch § 12 |
| `readSchedulers`, `readDisks`, `readIndexHealth`, `readDeletionJournal`, `readMaintenanceActions` | reshape | facts with state codes (a disk nearly full and an index anomaly count at the menu's Système badge — L24 OPEN 2 = A) | §8 | reg § 2, § 3 |
| `runMaintenanceAction`, `runPipeline`, `killPipeline`, `pausePipeline`, `resumePipeline`, `setWatcher` | reshape | `{state, uid}` — `queued` is a state, never a refusal | §6 | reg § 2c |
| `readSettings`, `readConfigurationFiles`, `readConfigurationFile`, `updateConfigurationFile`, `readSecrets`, `updateSecrets`, `readConfigurationStatus`, `restartWeb` | reshape | the settings as topics of rows (`id`, `key`, `type`, `displayedValue`…), `digest`, `restartRequired`, `conflict` | DOIT-3 | reg § 2 |
| `readVersion` | reshape | `commit` | — | reg § 2 |

### 1.6 Live events — `/api/v1/events` (v0: `/ws/events`)

| Demand | What | Source |
| --- | --- | --- |
| **E1** | an event names its medium's identity — `ItemDispatched` carries the provider identity | stream § 1 |
| **E2** | the ownership reads served from what the dispatcher writes, or `LibraryScanCompleted` guaranteed after a dispatch | stream § 5 |
| **E3** | a service's up/down TRANSITION (never per probe) | stream § 4 |
| **E4** | per-tunnel progress carrying the medium's identity; a tunnel's block and resume; the global levers' state | arch § 1 |
| **E5** | `CrossSeedInjected` / `CrossSeedRejected` with `tracker` (not `source_tracker`) and the reason; a new `CrossSeedSearched` | L17 I |
| **E6** | a removed torrent (by the gesture or by hand), so its row leaves live | arch § 4 |
| **E7** | a tracker switched off by failure | L16-bis T2 |
| **E8** | an account's rights changed | L18 M |
| **E9** | every run and tunnel event a stable code + typed parameters, no French; `run_log`'s `line` stays raw | stream § 7 |
| **E10** | the download rates (T3's stream half) — a value pushed to the component, never a list refetched | stream § 2; L16-bis T3 |

### 1.7 What the switchover may retire

The 12 operations the backend has and the interface does not use (reg § 4) — `journeys` (the list), `lookup`,
`overview`, `stalled-grabs`, `wanted`, `decisions/activity` (L24 OPEN 3 = A: read per card), `decisions/{id}`,
`health`, `pipeline/stages`, `registry/status`, `staging/…/poster`, `config/validate` — die with `frontend/src` unless
a script or a cron still calls them (checked per operation at K-lot time; `GET /api/health` is the deploy
post-check and stays).

---

## 2. What exists and is reused

Paths are under `personalscraper/`. The verdict is his four words: **adapt** (same module, new fields or routes),
**re-architect** (same responsibility, new structure), **transform** (the module's work moves into a new shape),
**rebuild** (nothing to take — only where nothing exists).

**Where each row lands under D** (§ 5 Q11). Three layers, and every row below belongs to one:

- **The kept engine** — `api/`, `sorter/`, `process/`, `scraper/`, `verify/`, `dispatch/`, `trailers/`, `indexer/`,
  `acquire/`: extended (a column, a setter, `released_at`, the ratio), never rewritten. Each step already has its
  one-medium kernel — `sorter.sort_item`, `scrape_movie` / `scrape_movie_forced` / `scrape_tvshow`, `check_movie` /
  `check_tvshow`, `dispatch_movie` / `dispatch_tvshow`, the trailers' `_process_item` — and the tunnel calls them
  directly; only the `run_*` entry points sweep the whole staging.
- **The application layer** — a new package (`personalscraper/app/`) owning `app.db`: the use-case services
  (accounts and rights, requesters, the tunnel and its supervisor, journeys, the « À traiter » cards, the cross-seed
  pairs) and the part of `web/` that is engine filed in the wrong place — the read-models, runners, queues, the
  maintenance registry, the torrent session — moved out of `web/` and freed of `fastapi`. The CLI and the web are two
  IN-PROCESS clients of it; no action goes through a CLI subprocess and its text arguments any more
  (`web/_runner_engine.py` `run_spawn_stream` :618 dies with v0).
- **The HTTP v1** — a new package whose models are written from the maquette's contract; a route calls one service.
  `web/routes`, `web/models`, `web/auth`, `web/ws` are v0: FROZEN (a production fix only), deleted in one block at
  the switchover. A row below naming a v0 route says what its v1 twin must do, never a change to the v0 route.

### 2.0 Cross-cutting

| Exists | Verdict | What changes |
| --- | --- | --- |
| ~101 `raise HTTPException(detail=…)` across `web/`, English and French strings mixed, no exception handler | transform | one handler answering `Problem`; a detail is a CODE with parameters, never a sentence (X1, X4) |
| `web/models/*` Pydantic models, `make openapi` → `frontend/openapi.json` | rebuild (v1), v0 frozen | the v1 models are WRITTEN from the maquette's contract, in its spelling, in the v1 package — no alias generator over the v0 models, which stay as they are and die at the switchover; the v1's generated contract compared to the maquette's by `scripts/compare-contracts.py` — the register reaching ZERO rows against v1 is the mission's measure |
| `web/app.py:214-268` (`guarded_api`), `web/deps.py` | transform | the v1 has ONE perimeter dependency of the same shape (never a per-route session check); its subject is « an account », and each route names its right (X6); v0's `guarded_api` is frozen with v0 |

### 2.1 Acquisition and the tunnel

| Exists | Verdict | What changes |
| --- | --- | --- |
| `acquire/` lobe — `store.py` (`_FollowSubStore` :150), `_wanted_store.py`, `detect.py`, `_grab_pass.py`, `_search_pass.py`, `_season_fallback.py`, `orchestrator.py`, `service.py`, `cadence.py`, `airing.py`, `reconcile.py` | adapt | `followed_series` has NO requester column anywhere: a requesters table with per-requester quality and pause; `wanted` gains `trigger` (SR5, only `staging_provenance.resolution_trigger` and `pipeline_run.trigger` exist today); `_detect_episode` (:526) and the grab pass skip a season under recovery (SR3 — `_detect_seasons` :616-780 already absorbs the open episode wanteds) |
| `followed_series.quality_profile_json`, `acquire/desired.py:79` (`QualityProfile`), applied at `acquire/_pass_gates.py:235-253` | adapt | the override EXISTS and is honoured on the grab path; it becomes per requester, resolved « highest wins », and writable (`UpdateFollowRequest` accepts only `active` and `cadence` today) |
| `staging_provenance` (acquire.db, `info_hash` primary key, migrations 010/015/017/018/021), `acquire/_provenance_store.py`, `GET /journeys` | re-architect | the journey is keyed by the ACQUISITION (wanted row) with the release it followed and its own rung times (SR4); it becomes the tunnel's persisted state (step, block reason code, what resumes it) |
| `web/acquisition/to_handle.py:100` `build_to_handle`, `web/staging/read_model.py`, `web/staging/stages.py` (the single stage taxonomy and `compute_position`) | transform | moved to the application layer; one card read-model for « En cours », « À traiter » and the staged media (§ 13: one derivation per question). The single taxonomy is the contract's eight-rung ladder: `compute_position` and the « one position » rule move into the tunnel service, the eight staging stages become the sub-steps of « rangé » and « enrichi », the French reasons (`REASON_*` :72-75) become codes |
| `web/routes/decisions.py`, `web/decisions/{runner,reserve}.py`, `scrape_decision` (library.db, migration 013), the resolve queue (#287) | transform | `settledBy`, an engine-made identification written as a row, `reopenDecision`, the resolve's inverse; #287's proof (every step mutates the item) stands, its mechanism goes: a resolve is a tunnel's resume in the supervisor's queue (§ 5 Q5), never a second queue |
| `api/plex.py`, `subscribers/plex.py` (refresh after `ItemDispatched`), `maintenance/plex_guard.py:194` `run_plex_guard` | transform | the guard's match-coherence check becomes the tunnel's last rung (§ 4, § 20) and `resolvePlexMatch`'s comparison; no web route exists today |
| `web/acquisition/service.py:319` `run_media_search`, `:571` `run_media_lookup` | adapt | `followed` / `owned` on a result |
| — suggestions | rebuild | nothing exists; built over the provider clients `api/` already has (TMDB, Trakt) |
| `web/routes/acquisition_triggers.py` (`_guard_no_running_grab` :148 → 409), `web/acquisition/runner.py` | transform | a busy grab is queued in the supervisor, never refused (§ 6); the runner's subprocess becomes an in-process call |
| `api/tracker/_ranking.py`, `conf/models/_ranking.py`, `web/routes/acquisition_ranking.py:198` | adapt | a tracker's ratio state enters the score (§ 18) |
| `pipeline.py`, `pipeline_history.py` (`PipelineRunWriter`), `web/_runner_engine.py` (`RunnerSpec` :498, `run_spawn_stream` :618), `web/pipeline_trigger.py`, `web/pipeline_queue.py`, `web/run_queue.py`, `lock.py` (`acquire_pipeline_lock` :197), `acquire/watcher.py`, `commands/watch.py` | re-architect | the supervisor first runs TODAY's `run` unchanged (K4a, § 5 Q14), then the batch run becomes N tunnels under its authority (§ 5 Q5); the STEPS — `ingest`, `sort`, `process`, `scraper`, `trailers`, `verify`, `dispatch` — are reused as they are, their one-medium kernels called directly; web and CLI enqueue in-process, `run_spawn_stream` dies with v0 |
| `ingest/` `ingested_torrents.json` tracker | transform | ingestion state becomes the tunnel's first rung, per arrival |

### 2.2 Library

| Exists | Verdict | What changes |
| --- | --- | --- |
| indexer — `indexer/db.py`, `indexer/migrations/001_init.sql` (`media_item`, `season`, `episode`, `media_release`, `media_file`…), `indexer/repos/*`, `indexer/query.py` (`execute` :590, `find_all_items` :659) | adapt | the listing, categories, recent and incomplete become routes over the query layer (today only maintenance CLI actions — `library-search`, `library-show`, `library-status` — reach them); the synopsis, absent today, joins the read-model |
| `indexer/ownership.py:280` `IndexerOwnershipChecker` (`owns`, `owned_pairs`), `core/ownership.py`, `indexer/repos/item_repo.py` `get_by_title_kind_year` | adapt | `readLibraryMembership` by provider id, with the kind (§ 5 Q15); the title-keyed lookups stay as a search fallback only |
| `web/routes/media.py:268` (live provider data + `_build_ownership_block` :165), `web/acquisition/completeness.py`, `truth.py` (ACQUIRED) | adapt | the sheet's missing facts, the film variant, `readMediaSeasons` on the same completeness truth table (aired ≠ catalogue) |
| `maintenance/rescraper.py:830` `rescrape_library` | adapt | per medium |
| `maintenance/disk_cleaner.py:481`, `indexer/destructive_journal.py` (`record_destruction` :43), `acquire/delete_authority.py` (ACQUIRED) | adapt | `deleteLibraryItems` composed of the three, plus the Plex deletion; no delete route today |

### 2.3 Trackers, ratio, cross-seed, upload

| Exists | Verdict | What changes |
| --- | --- | --- |
| `api/tracker/*` (c411, tr4ker), `config.example/tracker.json5` (`enabled`, `cross_seed`, `economy` — `TrackerEconomyConfig`) | adapt | three more providers (T1); `accepts_uploads`, `economy.alert_threshold`; a failure-driven `disabled` state (T2) fed by `core/circuit.py` and `TrackerAuthFailed` |
| `seed_obligation`, `ratio_state` (acquire `001_init.sql`), `acquire/store.py:545` `_SeedSubStore`, `:769` `_RatioSubStore`, `GET /obligations` | adapt | two holes first: `ratio_state` is NEVER written (`_RatioSubStore.upsert` has no caller) and no tracker client reads an account's ratio or volumes — K5 starts there; an obligation is never closed: `satisfied_at` (`mark_satisfied` has no caller) and `released_at` are read, never written. Then `crossSeedOf`; « libérée » on every gesture that ends one; the displayed ratio checked to be the TRACKER's own figure (NE-DOIT-PAS-1) |
| `web/acquisition/downloads.py:139` `list_active_downloads` | adapt | T3's fields, provenance, the deferral kind; the per-pair cross-seed list |
| `ingest/deferral.py:44` `classify_deferrals` (read by `commands/watch.py:332`, `web/acquisition/service.py:160`) | adapt | exposed on the downloads read: kind, tracker, that tracker's `min_ratio` |
| `acquire/cross_seed.py:49` `CrossSeedService` (`check` :109, `sweep` :529), `cross_seed_history`, `cross_seed_quota` (migration 002) | re-architect | it returns at the FIRST verified injection (:455, « first match wins »): it attempts every eligible tracker; a per-(torrent, tracker) state table with `stoppedAt` / `stopCause`; an exclusions table; a hand search under quota |
| `api/torrent/_base.py` (bencode, info-hash) | rebuild on it | torrent CREATION and per-tracker PUBLISH do not exist; built on the bencode code and on each tracker client |

### 2.4 Accounts and rights

| Exists | Verdict | What changes |
| --- | --- | --- |
| `web/auth/routes.py` (login :83, logout :165, me :182), `web/auth/tokens.py`, `passwords.py` (scrypt), `ratelimit.py` | transform | the session's subject becomes an account id; the password path open to the `owner` and `local` sign-in kinds only (`auth.password` retired, the operator 2026-10-03); the single `config.web.username` (`conf/models/web.py:30`) retired |
| `web/deps.py` `require_session` :137, `require_not_staging` :106 (about 15 uses), `tests/unit/web/routes/test_staging_write_policy.py` | transform | one `authorise(right)` reading the role and the instance's forbidden writes; `require_not_staging` absorbed (NE-DOIT-PAS-7); the policy table becomes the rights table's test |
| — accounts, roles, rights, Plex SSO | rebuild | no users table exists; `api/plex.py` speaks to the SERVER, the Plex account sign-in (PIN / OAuth) is new |

### 2.5 Système, Maintenance, Réglages

| Exists | Verdict | What changes |
| --- | --- | --- |
| `web/routes/maintenance.py` (`disks` :121, `locks` :384, `destructive-log` :468, `index-health` :499, `schedulers` :782, `actions` :904/:810), `web/maintenance/{registry,runner,service}.py`, `web/schedulers/registry.py:37` | adapt | facts as codes; `locks` reflects a maintenance run's hold |
| `web/routes/pipeline.py` (`run` :196, `pause` :232, `resume` :252, `kill` :268, `watcher` :325, `status` :356, `history` :498/:574), `pipeline_run` (library.db, 011/012/016) | adapt | the failing step named, blocked counts on the summary, the levers of § 20 (bound, pause, the automatic processing, `watcherDown`) |
| `core/circuit.py` (`CircuitBreakerOpened/Closed/HalfOpened`), the `health-check` cron | adapt | `readDependencies` / `readServices` / `readErrors` over them; a service's up/down transition event (E3) |
| `web/routes/config.py` (`schema`, `files`, `secrets`, `status`, `restart-web`), `conf/sync.py`, `conf/config_git.py` | adapt | the settings answered as topics of rows; the new keys of § 1 |

### 2.6 Live events

| Exists | Verdict | What changes |
| --- | --- | --- |
| `core/event_bus.py`, `subscribers/redis_stream.py:70` `RedisEventPublisher` (subscribes to the base `Event`: every bus event reaches the stream), `app/relay.py`, `web/ws/routes.py:28` | adapt | payloads carry identity and codes (E1, E9); new events E3–E8 land with the lot that owns their subject |

---

## 3. The data

### 3.1 What exists

| Store | Holds today | Owner |
| --- | --- | --- |
| `library.db` (indexer, migrations 001–016) | the index (`media_item`, `season`, `episode`, `media_release`, `media_file`, `scan_run`, `index_outbox`, `repair_queue`…), AND three tables that are not the index: `pipeline_run`, `scrape_decision`, `destructive_op` | `library-index`; the web for the three others |
| `acquire.db` (migrations 001–024) | `followed_series`, `wanted`, `seed_obligation`, `ratio_state`, `cross_seed_history`, `cross_seed_quota`, `watch_state`, `aired_episode`, `staging_provenance`, `download_marks` | the `acquire/` lobe |
| files in `data_dir` | `pipeline.lock`, `pipeline.pause`, `watcher.paused`, `ingested_torrents.json`, `trailers_state.json` | the pipeline |
| Redis | the event stream `personalscraper:events` (replay cursor) | the publisher |
| `~/.torrentmate/config` (19 `.json5` overlays) and `.env` | configuration and secrets | the config editor |

### 3.2 What changes

- **New data.** Accounts, roles and their rights, sessions; a follow's requesters with each one's quality and pause;
  the tunnel's state per acquisition (step, block reason code, what resumes it, rung times, the release it
  followed); `wanted.trigger`; a decision's `settled_by`; the per-(torrent, tracker) cross-seed state and the
  exclusion list; a tracker's failure-driven `disabled` state; a release's choice date (the added/grab date that
  decides the filing, § 5 Q9); push subscriptions (FCM, § 5 Q10); a kept Plex token, encrypted (§ 5 Q16).
- **Every store per environment.** The three stores by owner (§ 5 Q2) — `library` the index only, `acquire`, and
  `app`, owned by the application layer — exist once PER ENVIRONMENT: preprod shares no database with prod (§ 5
  Q13) and is free of schema. The suffix rule of Q2 (`-dev`, `-staging`, none for prod, from one environment
  setting) names them, and now covers the index too: preprod indexes its own disks, nothing of prod's.
- **Codes, not words.** Every stored reason — `last_grab_reason`, `last_search_outcome`, `blocked_reason`, a
  cross-seed refusal, a tunnel's block, a Système fact — is a member of a closed code set the contract declares; no
  French and no English sentence is stored or sent (X4, conformity Q2 = A, stream § 7).
- **The index becomes disposable.** The filesystem is the truth for files and the NFOs for identities
  (`architecture.md` « BDD vs FS truth rule »): `library.db` can be rebuilt by a full scan, which is what makes a
  reprise « pas à l'identique » cheap for the library. It stops holding what is not the index (§ 5 Q2); each
  environment scans and writes its own (§ 5 Q13).
- **Identity by provider id** (§ 5 Q15). The engine identifies a medium by its provider id everywhere — TVDB first
  for a show, per the existing separation of ids —; a title is only a search fallback. Two rows sharing one id are
  DUPLICATES to report, never merged in silence. The keys of `acquire` and of the indexer are reviewed in K2–K3. The
  most frequent fix family of the last 90 days is identity held by the title (#638, #489, #508, #435, #338, #460);
  `BUGS.md` B-476, B-477 and B-573 are still open on it — this closes the family at its source.
- **Per-acquisition journeys** replace the per-title, per-info-hash provenance (SR4, Rd Q14 = A).
- **The reprise** (§ 5 Q3, its route ruled by § 5 Q12): the tool calls the application layer's services IN-PROCESS,
  with the same validations as the API — no import route outside the contract, nothing copied table to table. It
  keeps the intent of « automatisée par l'API » (operator, 09-27 orientation); the letter is replaced. Existing
  follows are attributed to the Plex server's owner account (Izno, ruling 9).
- **No back-compatibility.** Migrations restart from a new baseline per store; the old migration chains are
  archived with `frontend/src` at the switchover. Until then, an engine migration that production runs is ADDITIVE
  (a column, a table), arrives with its regression test seen red, and runs on preprod before prod.

---

## 4. Environments

**Today** (`docs/production/web-ui.md` § ENV-SEP; retired by the rulings below): dev `~/dev/PersonalScraper` (no
daemons); prod `~/deploy/torrentmate` (`main`, :8710, the watcher and every cron); staging `~/staging/torrentmate`
(`staging`, :8711, web only, read-only by `require_not_staging`). All three SHARE `library.db`, `.data/`, the config
(`tracker.json5` says so: « shared with prod/staging via PERSONALSCRAPER_CONFIG ») and the disks — which is why
staging may write nothing. tm-design (:8712) serves the maquette alone, on mocks.

**Ruled before** (`operator-method.md` § 3 « Environnements et back-end »):

- Ruling 23 (Rd 9 Q17): the future **preprod** has ITS OWN data sets; its forbidden writes are the library DELETION
  alone (« Sur la preprod, tout fonctionne sauf la suppression dans la médiathèque », § 17). Its other term — it
  files into the PROD library — is SUPERSEDED on 2026-10-02 (§ 5 Q13): preprod files into its own. The environment
  is named `staging` (ruled 2026-10-01); `staging_dir` stays the name of the pipeline's space.
- 09-27 orientation: « une vraie staging séparée du back-end de prod ».
- The forbidden writes are a per-instance list served by `readAccount` (L18 N): production empty, preprod
  `library.delete`, a read-only instance every write right.

**Decided** (§ 5 Q1, Q13):

- **`staging` IS the preprod** (« l'env staging est bien la préprod ! »). It runs the whole engine and shares NOTHING
  with prod but, possibly, the torrent client:
  - its own databases, all three (§ 3.2), with full freedom of schema;
  - its own configuration — never prod's overlay files — and its own `data_dir` (its own `pipeline.lock`,
    `ingested_torrents.json`, everything the pipeline keeps there) and its own staging space;
  - its own « disques de préprod »: dedicated mount points on the NTFS disks, so the same filesystem and its traps
    (NFC/NFD, macFUSE) are exercised; outside prod's media roots, which prod's indexer walks recursively;
  - outside Plex's production libraries — a dedicated Plex preprod library is the operator's affair;
  - FCM on a dedicated preprod channel; one `app.db` per environment, so a preprod Plex sign-in gives prod no token
    (§ 5 Q16);
  - its forbidden writes are the library deletion alone; cross-seed and upload are off by its overlay; the read-only
    :8711 instance is retired and its port and host are taken by preprod, with its own PM2 apps (web, supervisor,
    its crons, offset from prod's).
- **The torrent client: B, else A** (« Ok, B sinon A »).
  - **B — a second qBittorrent, dedicated to preprod.** Prod's client sees nothing of preprod and prod changes
    nothing. B holds only if EVERY active tracker accepts two clients on one account and one IP: C411 and tr4ker today
    (`enabled: true` in `~/.torrentmate/config/tracker.json5`), and v3x, draupnirr and digitalcore once T1 lands.
    **This is an open verification, and K0 closes it FIRST**, before anything of preprod is built: per tracker, its
    rule on two clients behind one account and one IP, answered with its source.
  - **A — otherwise: one shared qBittorrent.** Preprod downloads in its OWN category with its own save path, and its
    torrents are ALSO tagged `seed-pure`, so today's prod ingest skips them (`ingest/ingest.py:449`; the watcher's
    trigger, the sort guard and the cross-seed sweep skip the same tag). Preprod's own code then owes what the shared
    client does not separate: an info-hash already in the client is refused (a second add of one hash is answered as
    a success and its tag is never set, `api/torrent/qbittorrent.py:358-363`); its own authentication-lockout path
    (one file under the home directory today, read by every checkout, `qbittorrent.py:50`); no global speed caps
    written. A residue A keeps: prod's watcher counts every downloading torrent before it runs
    (`commands/watch.py:293-296`), preprod's included.
- **The 02:00 purge.** A daily cron at 02:00 purges preprod's downloads, ONLY once their seed obligations are met:
  the tracker accounts are prod's own, and a purge before would be a hit-and-run on them (C411: 72 h or ratio 1.0,
  no grace — `tracker.json5`). So the purge reads a WRITTEN obligation state — today neither `satisfied_at` nor
  `released_at` is ever written (§ 2.3) — and refuses a torrent whose obligation it does not know (the deletion
  authority is fail-open today: « no-obligation […] → ALLOW », `acquire/delete_authority.py:8-9`); it removes
  through the torrent client's API, never `rm`, and writes the destructive journal.
- **The mount-point guard.** Every preprod write and purge is confined to preprod's own folders by a guard on the
  MOUNT POINT (rights may be added on them). The engine's own disk check does not hold it today:
  `dispatch/disk_scanner.py:58` takes `config.path.exists()` for « mounted », so an empty mount point left on the
  internal disk after the Monday reboot counts as a disk, and a dispatch lands in silence on the system SSD. K0
  replaces it by a real mount check.
- **What stays shared** whatever the client: the tracker accounts and their passkeys (hence the purge's rule), the
  machine's disks and memory. Noted by the operator for later: an analysis of the disk I/O load, prod and preprod
  alike.
- **The git flow**: `feature → develop → main`; `develop` auto-deployed on tm-design, `main` = everything validated,
  `staging` deployed voluntarily by him when a complete user story is ready for test users, `prod` (a branch carrying
  release tags, auto-deployed) deployed voluntarily after functional validation on staging; promotions are
  fast-forwards, a `hotfix/` branch from `prod` is merged back into `develop`. The autodeploy poller, which tracks
  `main` for prod today, is changed accordingly.
- It is where the maquette is bound to the real backend during the mission (§ 6), on real media, before production
  sees a lot.

---

## 5. DECIDED

Sixteen questions, ruled by the operator in two decision rounds: Q1–Q10 on 2026-10-01 (`operator-method.md` § 3,
« Environnements et back-end »), Q11–Q16 on 2026-10-02, after he reopened the backend's shape (« On refait tout ? On
repart de l'existant ? Un juste milieu ? » — « je veux qu'on pèse tout, et qu'on remette en question les
decisions »). They are rulings: not reopened here, and no option survives that he did not choose. Where a ruling of
2026-10-02 replaces part of an earlier one, the earlier text stays, marked SUPERSEDED with the date.
The spelling of the contract (reg § 2b, « the operator's call ») was NOT asked: § 15 already answers it — the backend
serves the contract's camelCase — and it is not functional; he overrules it by saying so.

**Q1 — How the new backend reaches production. HIS WORD.** Today's `/api` is **v0**; the new backend is served under
**`/api/v1`**, and future versions follow without breaking. A v0 route is DEPRECATED as soon as its v1 works: it
answers a `Deprecation` header and is entered in a register, which is the cleanup list once v1 is fully deployed and
validated. *Amended 2026-10-02 by Q11*: v0 is FROZEN, never adapted (a production fix only); the `Deprecation`
header marks a v0 route once its v1 twin exists, and v0 is deleted in ONE block at the switchover (`web/routes`,
`web/models`, `frontend/src`) — the register is that block's list. The git flow is adapted to it:

- `feature → develop → main`. `develop` is deployed automatically on tm-design (tm-design = `develop` plus the lot in
  flight, merged on the fly); `main` holds everything validated — validated features are promoted to it.
- `staging` is deployed VOLUNTARILY by him, only when a complete user story is ready for test users (« on déploie en
  staging que quand la user story est prête au complet »).
- `prod` is deployed VOLUNTARILY after functional validation on staging; it is a branch carrying release tags,
  auto-deployed.
- Defaults kept, as he did not object: promotions are fast-forwards; a `hotfix/` branch cut from `prod` is merged back
  into `develop`.
- `staging` IS the preprod of ruling 23 (« l'env staging est bien la préprod ! »), with its own data (§ 4, § 5 Q13).

*Consequence*: today's CD — the autodeploy poller tracks `main` and deploys prod — changes to this flow: a tooling
change to schedule in K0.

**Q2 — The stores, re-imagined. A, with his word.** Three stores by owner: `library.db` the index ONLY (rebuildable
from the disks); `acquire.db` acquisition and trackers (follows, requesters, wanted, obligations, ratio, cross-seed
pairs and exclusions); a new `app.db` for accounts and roles, tunnels and journeys, run history, decisions, the
destructive journal. Three tables move out of `library.db`; `app.db` is one more file in the lock order (a leaf).

- **One file per environment**, by suffix: `acquire-dev.db`, `acquire-staging.db`, `acquire.db`, `app-dev.db`,
  `app-staging.db`, `app.db` — prod keeps today's names, and the suffix comes from one environment setting (« Des
  fichiers bien séparé plus facile à gérer et à maintenir »).
- **The index is the exception, B′**: ONE `library.db`, written by prod alone and read-only for dev and staging (« B'
  tu as raison, la staging range en prod »), so the disks are scanned once. **SUPERSEDED 2026-10-02 by Q13**:
  preprod files into its own disks and keeps its own index; every store, the index included, is per environment.

**Q3 — What the reprise carries. A.** The operator's intent and debts: the follows (attributed to Izno) with their
quality profiles, the open and `abandoned` wanted rows with their tried releases (so a bad release is never grabbed
again), the seed obligations and ratio states, the cross-seed history (seeding the pair states), the destructive
journal. The index is REBUILT by a full scan; run history, settled decisions and past journeys start empty. *Cost*:
past runs and the journeys of media already in the library are gone. *Its route*: ruled 2026-10-02 by Q12 — the
application layer's services, in-process.

**Q4 — What the preprod runs. A. SUPERSEDED 2026-10-02 by Q13** (its two letters « one qBittorrent, one category per
environment » and « preprod files into prod's library »; § 4 carries the preprod as now ruled). The whole engine on
its own data (§ 4): its own follows grabbing for real in its own qBittorrent category, its own pipeline filing into
prod's library, deletion refused, cross-seed and upload OFF by its overlay; the read-only :8711 instance is retired and its port and host taken by preprod. *Cost*: real grabs on the
operator's tracker accounts from a second instance (bounded by its own few follows); a qBittorrent category per
environment.

**Q5 — One trigger authority for N tunnels. A.** One SUPERVISOR process (the watcher daemon becomes it) holds the
authority: it runs up to `max_parallel` tunnels as workers, queues the rest visibly, and serialises only what must be
serial (a dispatch onto one disk, the index write) by inner locks; the web and the CLI ENQUEUE, never spawn;
`pipeline.lock` is replaced by the supervisor's lease. *Cost*: the largest change of the mission; a CLI run goes
through the supervisor. *Order, ruled 2026-10-02 by Q14*: the supervisor comes ALONE and early (K4a), before the
acquisition model and the tunnels.

**Q6 — A series' tunnel granularity. A.** One tunnel per RELEASE (one torrent: an episode's, or a season pack). *Cost*:
a season pack's episodes advance together, one blocked episode blocks the pack's filing.

**Q7 — What blocks, and what resumes. HIS WORD after discussion** (« oui c'est ça »). ONE list, « À traiter », holds
EVERYTHING blocked that needs an intervention, in the app or elsewhere: a disk full, a ratio too low, a tracker
unreachable (« qui fait de la place sur le disque ? ») as well as an identity, a Plex match or an error.

- Each card says its cause, what lifts it, and links to where it is settled (Système › Disques, « Voir le tracker »,
  its settings).
- The pipeline RESUMES ON ITS OWN as soon as the engine sees the cause lifted, and the card leaves. A block that needs
  a judgement (an identity, a Plex match, a tunnel error) waits for his hand.
- The Acquisition badge counts the whole list.
- This AMENDS ruling 7 of 09-15 (« À traiter = ce que seule sa main débloque ») and moves the deferred card from
  « En cours » to « À traiter » — a maquette change to draw.
- *Cost*: each external cause needs a watch on its own lift.

**Q8 — A tunnel whose medium disappears. A.** The tunnel closes with its reason; the card says it once in
« À traiter », dismissed by « × » (A6: « × » = seen); filed by hand elsewhere, it simply leaves (ruling 6). A medium
that comes back later starts a new tunnel.

**Q9 — A season ask meets an episode already downloading. HIS RULE after discussion** (« oui, enregistre »). Nothing is
cancelled and nothing is filtered: every tunnel runs to its end. An episode grabbed BEFORE the season ask is not
covered by 17:36's « aucun téléchargement … se lance en parallèle », which forbids only launches AFTER the ask; that
rule stands.

- **At filing, the LAST CHOSEN wins**, for ALL media (films too): the release's added/grab date decides, not its
  arrival time.
- A file with no known choice date (filed before the switchover) counts as older than anything.
- An older-chosen release that arrives after is NOT filed; its torrent keeps seeding; its tunnel closes with the
  reason « remplacé par un choix plus récent », said once in « À traiter » and dismissed by « × ».
- *His why*: the pack usually brings a better or corrected version (codec, corruption, missing subtitle or audio) and
  a coherent quality across the season.
- **Backend demand**: at filing, the engine must know the choice date of the release that filed the file in place. It
  is not yet verified in the code — K4b checks it first.

**Q10 — The ratio alert's channel. HIS WORD.** FCM is the channel (« Telegram est pollué et je veux m'en débarrasser »).
Telegram is refused as the alert channel; his wish to be rid of it is noted, its removal is NOT ordered and is not
planned here. No hurry, but the FCM project can be prepared now: notifications and web push on the installed PWA,
Android and iOS. The alert threshold defaults to ratio **1.2**, configurable tracker by tracker
(`tracker.providers.<name>.economy.alert_threshold`).

**Q11 — The shape of the rebuild. D** (2026-10-02, « Aller go pour D ! »). Neither a rebuild from nothing nor a
`/api/v1` grafted into today's `web/`: a new application layer and a new HTTP v1, written from the contract, on the
KEPT engine (§ 2, « Where each row lands under D »).

- **A new application layer**, a separate package (`personalscraper/app/`) owning `app.db`: the use-case services —
  accounts and rights, requesters, the tunnel and its supervisor, journeys, the « À traiter » cards, the cross-seed
  pairs — and the engine filed under `web/` today (its read-models, runners and queues), moved out and freed of HTTP.
- **A new HTTP v1**, a separate package whose models are written against `openapi.json`; a route calls one service;
  the measure of the end is `compare-contracts.py` at zero rows against v1.
- **The kept engine** — `api/`, sorter, process, scraper, verify, dispatch, trailers, indexer, acquire — extended,
  never rewritten; the tunnel's steps call its one-medium kernels.
- **The CLI and the web are two in-process clients of the same service**; no action goes through a CLI subprocess with
  text arguments any more.
- **v0 is FROZEN** — a production fix only, a `Deprecation` header once a v1 twin exists — and deleted in one block at
  the switchover (`web/routes`, `web/models`, `frontend/src`).
- Ten lots, K0 one part heavier: the engine moved out of `web/` and the app + v1 scaffold (§ 6).
- *Why*: the engine is healthy and well tested one medium at a time; two defects are structural — engine filed inside
  `web/`, and the CLI used as a text API — and D fixes both without paying the engine's lessons a second time.

**Q12 — The reprise's route. B** (2026-10-02). The reprise tool calls the application layer's services IN-PROCESS:
no import route, no table-to-table copy, the same validations as the API. It keeps the intent of Q3's « la reprise
passe par l'API »; the letter is replaced (the contract has no operation that writes an obligation, a ratio state, a
wanted row with its tried releases, or the cross-seed history).

**Q13 — Preprod and prod, separated. HIS DESIGN** (2026-10-02). The question asked who updates prod's index after a
preprod dispatch; he reframed it into the separation of the two environments, and the question is moot: preprod has
its own library. § 4 states the design in full:

- preprod shares NOTHING with prod but, possibly, the torrent client: its own databases (full freedom of schema), its
  own configuration, its own staging, its own « disques de préprod » (dedicated mount points on the NTFS disks, the
  same filesystem), outside Plex's production libraries (a dedicated Plex preprod library is his affair), FCM on a
  dedicated preprod channel;
- a daily cron at 02:00 purges preprod's downloads ONLY once their seed obligations are met — the tracker accounts
  are shared, and a purge before would be a hit-and-run on them;
- a guard by mount point confines every preprod write and purge to preprod's own folders (rights may be added);
- **the torrent client — B, else A** (« Ok, B sinon A »): B, a second qBittorrent dedicated to preprod, if EVERY
  active tracker (C411 and tr4ker today; v3x, draupnirr and digitalcore once T1 lands) accepts two clients on one
  account and one IP — to verify before building; otherwise A, one shared qBittorrent, preprod in its own category
  and save path, its torrents also tagged `seed-pure` so today's prod ingest skips them.
- It SUPERSEDES Q2's B′ and Q4's « one qBittorrent, one category per environment; preprod files into prod's
  library ». Noted by him for later: an analysis of the disk I/O load, prod and preprod alike.

**Q14 — The supervisor first. B** (2026-10-02). K4a is the supervisor ALONE — its lease, its visible queue, running
today's `run` UNCHANGED; the web and the CLI only enqueue — right after K2 and BEFORE K3. It is proved on preprod
(its own small test arrivals), then on prod; its rollback is the watcher put back in `ecosystem.config.js`. Then K3
(the acquisition model), then K4b (the tunnels per release). *Why*: the riskiest change of the mission — the trigger
authority of all of production — made early and alone, so it reads clearly.

**Q15 — Media identity. A** (2026-10-02). The v1 engine identifies a medium by its PROVIDER ID everywhere — TVDB
first for a show, per the existing separation of ids —; the title is only a search fallback. Two rows sharing an id
are duplicates to REPORT, never merged in silence. The keys are reviewed in `acquire` and the indexer during K2–K3.
The contract's `readLibraryMembership` said the opposite (« provider ids are not an identity (two rows can share
one) », keyed by exact title and year); it is now keyed by provider and provider id, its `rows` counting the rows holding the
id. It closes the B-476 / B-477 / B-573 family at its source.

**Q16 — Where the kept Plex token lives. A** (2026-10-02). The Plex token kept after a sign-in (round 4 P-3, kept and
encrypted for a future feature) is stored ENCRYPTED in the application layer's `app.db` by K1 — the key outside the
base, with rotation and revocation. The plex-sso brick stays STATELESS: it hands the token to its caller, as its
DESIGN already says. One `app.db` per environment: a preprod Plex sign-in gives prod no token.


---

## 6. A first cut of the backend lots

Each lot is DONE when its operations leave the computed register (`compare-contracts.py` against the v1 routes),
its events reach the stream, the maquette's mocks for them are retired on preprod, and ONE reader has used the
surfaces it unblocks on preprod at 390 px. Order (§ 5 Q11, Q14): the foundation every route needs, then the reads
that give the most screen for the least risk, then the supervisor ALONE, then the acquisition model, the tunnels,
and the engines.

**How production stays safe while the lots land** (§ 5 Q11): v0 and its crons do not change during the mission
(a production fix only); an addition to the engine that production runs (a setter, a column, `released_at`) arrives
with its regression test seen red before the change, and runs on preprod before it reaches `prod`; the engine's
migrations stay additive until the switchover; the supervisor (K4a) passes through preprod first with a one-line
rollback; the switchover (K9) is rehearsed on preprod.

| Lot | What | Unblocks on the screen |
| --- | --- | --- |
| **K0 — the foundation** | One part heavier than the earlier cut (§ 5 Q11). **The engine moved**: the engine filed under `web/` moved to `app/` with NO behaviour change — proved by the existing suite, unchanged and green, and `make openapi` with no v0 drift; the `conf` ↔ `api` import cycle broken (`conf/models/_ranking.py:20` imports `api`, `api/torrent/qbittorrent.py:45` imports `conf`); the composition root out of `cli_helpers` (`_build_app_context`, borrowed today by the web and by `trailers/cli.py:38`). **The v1 skeleton from the contract**: `Problem` (X1, B-267), the contract's names and statuses (X2, X3), the code sets (X4), the `/api/v1` mount, the v0 `Deprecation` header. **The stores**: `app.db`, the new baselines, one file per environment for every store (Q2, Q13) — the `app` baseline creates `push_subscription` (`personalscraper/app/store/migrations/001_baseline.sql`; the store is `personalscraper/push/store.py`, fcm-push phase 2; its foreign key to the accounts lands with K1). **The git flow's tooling**: `develop`, the poller (Q1). **The preprod** (Q13, § 4): FIRST the verification that decides its torrent client — does every active tracker (C411, tr4ker; v3x, draupnirr, digitalcore once T1 lands) accept two clients on one account and one IP? — then the client so decided (B; else A with its category, save path, `seed-pure` tag, refused shared hashes, own lockout path, no global caps); the mount-point guard and a REAL mount check replacing `config.path.exists()` (`dispatch/disk_scanner.py:58`); its own config, `data_dir`, staging space, disks, databases, PM2 apps and FCM channel; the 02:00 purge armed only on a WRITTEN obligation state — the engine writes an obligation met (`satisfied_at`) and its release (`released_at`), neither written today — refusing any torrent whose obligation it does not know | every refusal read as a refusal, not queued; the binding possible on preprod |
| **K1 — accounts and rights** | `app.db` accounts and roles, `authorise(right)` on every route (X6), `readAccount`, Plex SSO, the kept Plex token stored ENCRYPTED in `app.db` — the key outside the base, rotation, revocation; the plex-sso brick stays stateless (Q16) —, the forbidden-writes list, Comptes' operations, escalation refused, E8 | the sign-in gate (Plex first), Profil, Comptes, the bar composed by rights, every « réservé » state, every 403 |
| **K2 — the library** | listing, categories, recent, incomplete, the sheet's facts and its film variant, seasons, rescrape, deletion with the journal and Plex, E1, E2; **identity by provider id** (Q15): membership by provider id (the contract corrected ahead of it), the indexer's keys reviewed, two rows sharing an id reported as duplicates | Médiathèque's three tabs and filters, the media sheet, « Récupérer la saison » reading true holes |
| **K4a — the supervisor alone** | (§ 5 Q5, Q14) the supervisor, its lease replacing `pipeline.lock`, its VISIBLE queue, running today's `run` UNCHANGED; the web and the CLI only enqueue, in-process; proved on preprod on its own small test arrivals, then on prod; rollback = the watcher put back in `ecosystem.config.js` | a run asked is queued visibly, never refused (`{state, uid}`, `queued` a state) |
| **K3 — the acquisition model** | requesters and their settings (the quality setter does not exist today), reassign, restore, suggestions, search, the follows' shapes, the season grab by medium (a one-off `request` for an unfollowed show), releases with season / episode, the season's exclusivity (SR3, SR5, SR6; SR2 is ruled by Q9, last chosen wins), the ranking by ratio; the `acquire` keys reviewed for identity by provider id (Q15) | « Suivis », the follow sheet, Découvrir, quality and pause, « Réaffecter… », the season recovery's line and card |
| **K4b — the tunnels** | one tunnel per release (Q6) on the engine's one-medium kernels, under the supervisor with its bound `max_parallel` and the § 20 levers; the persisted tunnel state per acquisition, « À traiter » holding every block with its cause and auto-resume (Q7), a vanished medium closed and said once (Q8), the « last chosen wins » filing rule (Q9) — first checking that the engine knows, at filing, the choice date of the release that filed the file in place — , journeys per acquisition (SR4, SR1), the one card read-model on the contract's ladder, the decisions' reshape, `reopenDecision`, the resolve's inverse and the resolve as a tunnel's resume, the staged medium's verbs, the Plex match confirmed or corrected, E4, E9 | « En cours », « À traiter », the journey sheet, « Corriger », « Mis de côté » (the deferred card moves from « En cours » to « À traiter » — a maquette change to draw, amending ruling 7 of 09-15), Système's « Pipeline » levers |
| **K5 — trackers and ratio** | starts with the ratio hole: where each tracker publishes an account's ratio and volumes, or nothing — `ratio_state` is never written today and no tracker client reads them; then `readTrackers`, the downloads' and obligations' shapes, the deferral's kind, `removeDownload` writing `released_at` (« libérée ») on every gesture that ends an obligation, a broken obligation seen, health, T1, T2, the alert threshold (default 1.2, per tracker) and its channel FCM (Q10; the FCM project — a Firebase project, web push on the installed PWA, Android and iOS — may be prepared from K0 on, no hurry, his words), E6, E7, E10 | the Trackers page, its two tabs and its badge, the ratio alert outside the app, a torrent's panel, « Retirer de qBittorrent » |
| **K6 — cross-seed** | the per-pair state written and the attempt on every tracker, the switch with `stopRunningCrossSeeds`, cut (`released_at` written, the pair « stoppé »), exclusions, hand search, `readMediaCrossSeed`, E5 | the six states on every row, the per-tracker switch, « Couper », « Ne plus partager ce titre », « Chercher un cross-seed », the sheet's admin block |
| **K7 — upload** | torrent creation and per-tracker publish, `accepts_uploads`, `creation_failed` / `publish_failed`, `via` | « Créer et publier un torrent », « Publié par vous », the upload failures at the badge |
| **K8 — Système and Maintenance** | services, dependencies, errors as codes, history with its failing step and blocked counts, the maintenance lock, schedulers, the settings' shape, E3 | Système's index and sections, Maintenance, Réglages and its save bar on real writes |
| **K9 — the reprise and the switchover** | the reprise tool calling the application layer's services in-process (Q12), carrying what Q3 = A lists (the index rebuilt by a full scan), a rehearsal on the preprod, then the day: v0 deleted in ONE block — `web/routes`, `web/models`, `frontend/src` — (`/api/v1` stays), the maquette served on :8710, the retirable operations removed (§ 1.7), cross-seed active by default (L17 H) | the app, whole, in production |
