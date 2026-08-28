// What a server event refreshes on maintenance.
import type { LiveExemptions, LiveRule } from "../../lib/live-rule";

/** The actions, and whether each can run now. */
const ACTIONS_KEY = ["/api/maintenance/actions"];
/** The append-only record of what was destroyed, by whom and when. */
const DESTRUCTIVE_LOG_KEY = ["/api/maintenance/destructive-log"];

/** What a server event refreshes on maintenance. */
export const maintenanceLiveRules: readonly LiveRule[] = [
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
  types: ["PipelineStarted", "PipelineEnded", "PipelinePaused", "PipelineResumed"],
  keys: ["/api/maintenance/actions"],
  /* every address this feature reads is refreshed by a rule above */
  because:
    "THE CATALOGUE CANNOT SAY WHAT CAN RUN NOW, so refreshing it on a pipeline "
    + "boundary returns byte-identical JSON. `MaintenanceAction` carries id, "
    + "label, description, group, risk, long and dryRun — and no availability. "
    + "A rule was written here claiming to serve §8 and DOIT-4 by refreshing it "
    + "when the lock is taken; it refreshed nothing and made the concern look "
    + "covered. Worse, a MAINTENANCE action holding `pipeline.lock` emits no "
    + "`PipelineStarted` at all, so the one case where an action blocks the "
    + "others is the case that rule could never have seen. Filed as a demand: "
    + "the read needs an availability field before any event can help it",
};
