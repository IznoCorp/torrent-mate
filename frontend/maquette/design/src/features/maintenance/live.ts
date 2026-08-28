// What a server event refreshes on maintenance.
import type { LiveExemptions, LiveRule } from "../../lib/live-rule";

/** The actions, and whether each can run now. */
const ACTIONS_KEY = ["/api/maintenance/actions"];
/** The append-only record of what was destroyed, by whom and when. */
const DESTRUCTIVE_LOG_KEY = ["/api/maintenance/destructive-log"];

/** What a server event refreshes on maintenance. */
export const maintenanceLiveRules: readonly LiveRule[] = [
  {
    types: ["PipelineStarted", "PipelineEnded"],
    keys: [ACTIONS_KEY],
    because:
      "a running pipeline holds `pipeline.lock`, and an action that cannot run "
      + "while it does must SAY so rather than be offered and refused — which "
      + "is §8 and DOIT-4 read together",
  },
  {
    types: ["ItemDispatched"],
    keys: [DESTRUCTIVE_LOG_KEY],
    because:
      "a dispatch that REPLACED an existing folder is a destruction, and §7 "
      + "requires it leave a trace in the append-only journal — a journal that "
      + "only fills on reload is a journal nobody watches",
  },
];

/** The events that reach maintenance and deliberately refresh nothing. */
export const maintenanceLiveExemptions: LiveExemptions = {
  types: ["PipelinePaused", "PipelineResumed"],
  because:
    "a paused run still holds the lock, so nothing an action can do changes — "
    + "and the actions read is about what is POSSIBLE, not about what is "
    + "happening",
};
