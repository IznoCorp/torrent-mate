# Phase 7 — The map: Acquisition, Système, Maintenance

## Steps

1. `features/acquisition/live.ts`, `features/system/live.ts`, `features/maintenance/live.ts`.
2. Acquisition is where the backend emits most: `GrabSucceeded` `GrabFailed` `GrabReswitched`
   `WantedEnqueued` `WantedAbandoned` `SeriesFollowed` `SeriesUnfollowed` `DownloadStarted`
   `DownloadProgressed` `DownloadCompleted` `RatioMeasured` `SeedObligation*` `TrackerAuthFailed`
   `CrossSeed*`.
   **`DownloadProgressed` is the one to think about rather than map by reflex**: it fires per
   torrent per tick, and mapping it to a list key would invalidate that list continuously — a
   poll wearing an event's clothes. It is decided in this phase with its reason written down,
   either way.
3. The unhandled list is completed here: every type the mock stream can emit is mapped or
   explicitly listed as refreshing nothing, and the count of unmatched events reaching the browser
   is surfaced. **An event nobody handles is not an error; an event nobody can COUNT is how a map
   silently stops covering its subject.**

## The rule

R91 extended. Plus one hold on the unhandled counter: emit an unmapped type, assert the counter
moved by one and no cache entry did.

**Mutation**: map `DownloadProgressed` to the follows list. The hold must fall naming the
invalidation storm — which is the contract's third clause (« no polling remains ») caught in the
one form a grep for `setInterval` can never see.
