// The actions, and what they cost.
import JOURNAL from "../seeds/JOURNAL.json";
import MAINT_ACTIONS from "../seeds/MAINT_ACTIONS.json";
import MAINT_TOPICS from "../seeds/MAINT_TOPICS.json";
import { GET, POST, route } from "./shared";
import { mockState } from "../state";
import type { MockRoute } from "../router";

// The contract's own vocabulary, shared with the pipeline: an action asked for
// during a run is QUEUED and visibly so, never refused (DOIT-4).
const RUNNING = "running";
const QUEUED = "queued";

/** Every route this subject answers. */
export function maintenanceRoutes(): MockRoute[] {
  return [
    route("readMaintenanceTopics", GET, "/api/maintenance/topics", () => MAINT_TOPICS),
    route("readMaintenanceActions", GET, "/api/maintenance/actions", () => MAINT_ACTIONS),
    route(
      "runMaintenanceAction",
      POST,
      "/api/maintenance/actions/{actionId}/run",
      (request) => {
        const held = mockState();
        const known = MAINT_ACTIONS.find(
          (action) => action.id === request.parameters.actionId,
        );
        if (known === undefined) return null;
        const state = held.pipelineState === RUNNING ? QUEUED : RUNNING;
        return { state, uid: held.pipeline.last.uid };
      },
    ),
    route("readDeletionJournal", GET, "/api/maintenance/destructive-log", () => JOURNAL),
  ];
}
