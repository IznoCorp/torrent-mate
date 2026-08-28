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
export const accountLiveRules: readonly LiveRule[] = [];

/** Why nothing does. */
export const accountLiveExemptions: LiveExemptions = {
  types: [],
  keys: ["/api/auth/me"],
  because:
    "who is signed in changes when they sign in or out, which is a navigation "
    + "and not an event. A session ENDING does reach the interface — as the "
    + "relay's `refused` condition, drawn by the shell (D-L10-5)",
};
