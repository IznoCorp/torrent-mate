// The actions, and what they cost.
import DELETION_JOURNAL from "../seeds/deletion-journal.json";
import MAINTENANCE_ACTIONS from "../seeds/maintenance-actions.json";
import { GET, POST, field, route } from "./shared";
import { mockState } from "../state";
import type { MockRoute } from "../router";
import type { components } from "../../contract/types";

type PipelineState = components["schemas"]["PipelineState"];

// Shared with the pipeline: an action asked for during a run is QUEUED and
// visibly so, never refused.
const RUNNING: PipelineState = "running";
const QUEUED: PipelineState = "queued";
const IDLE: PipelineState = "idle";

/** Every route this subject answers. */
export function maintenanceRoutes(): MockRoute[] {
  return [
    route("readMaintenanceActions", GET, "/api/maintenance/actions", () => MAINTENANCE_ACTIONS),
    route(
      "runMaintenanceAction",
      POST,
      "/api/maintenance/actions/{actionId}/run",
      (request) => {
        const held = mockState();
        const known = MAINTENANCE_ACTIONS.find(
          (action) => action.id === request.parameters.actionId,
        );
        if (known === undefined) return null;
        // A DRY run changes nothing, including the state: that is the whole of
        // what a blank run means, and answering « running » to one would be the
        // interface lying about what it just did.
        if (field(request.body, "dryRun") === true) {
          return { state: held.pipelineState, uid: null };
        }
        held.pipelineState = held.pipelineState === IDLE ? RUNNING : QUEUED;
        // NOT the last run's identifier. A run that has just been asked for has
        // no record yet, and answering the previous one's uid made a maintenance
        // action claim the pipeline's last run as its own.
        return { state: held.pipelineState, uid: null };
      },
    ),
    route("readDeletionJournal", GET, "/api/maintenance/destructive-log", () => DELETION_JOURNAL),
  ];
}
