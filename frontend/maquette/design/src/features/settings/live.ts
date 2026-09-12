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
export const settingsLiveRules: readonly LiveRule[] = [];

/** Why nothing does. */
export const settingsLiveExemptions: LiveExemptions = {
  types: [],
  keys: [
    "/api/config/schema",
    "/api/config/secrets",
    "/api/config/status",
  ],
  because:
    "the configuration changes when someone edits it, and the interface that "
    + "edited it already knows. A second operator's change arriving mid-edit "
    + "would overwrite an unsaved form, which §8's own « rien en silence » "
    + "forbids more strongly than it asks for freshness. The STATUS is the "
    + "same answer one level up — whether this instance may write, and whether "
    + "a restart is owed — and it moves for one reason only: a write this "
    + "interface just made, which invalidates it where it is made",
};
