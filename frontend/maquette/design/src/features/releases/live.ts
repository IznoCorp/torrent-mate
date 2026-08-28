// What a server event refreshes on this feature: NOTHING, and that is written
// down rather than left as an absent file.
//
// A FEATURE WITH NO `live.ts` IS INDISTINGUISHABLE FROM A FEATURE NOBODY
// THOUGHT ABOUT. `check-live-relay.py --arm map-completeness` reads every
// address each feature's `queries.ts` asks for, and refuses one that no rule
// refreshes and no exemption names — so this file is what makes « nothing
// refreshes it » a decision.
import type { LiveExemptions, LiveRule } from "../../lib/live-rule";

/** No server event refreshes this feature. */
export const releasesLiveRules: readonly LiveRule[] = [];

/** Why nothing does. */
export const releasesLiveExemptions: LiveExemptions = {
  types: [],
  keys: ["/api/acquisition/releases"],
  because:
    "the release candidates for one wanted item are a SEARCH RESULT the reader "
    + "asked for and is choosing from. Refreshing the list under a finger about "
    + "to tap a row is worse than showing one a few seconds old — the row moves "
    + "and the tap lands on another release",
};
