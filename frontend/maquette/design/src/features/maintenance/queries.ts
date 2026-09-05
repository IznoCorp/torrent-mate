// What Maintenance asks the server for.
//
// TWO READS. The actions it offers, and the journal of what deleting has
// already done. `MAINT_TOPICS` and `RISQUES` stay where they are: the register
// classifies them `interface` — a rubric's name and the sentence warning what a
// rubric DELETES are the interface's own words, and routing them through a mock
// would have the interface asking a server for its own copy.
import { useQuery } from "@tanstack/react-query";
import { read } from "../../lib/query-client";
import { toEngineShape } from "../../engine/engine-shape";
import type { DeletionJournal, MaintenanceAction } from "./reference";

/**
 * The actions maintenance offers, as a query DEFINITION.
 *
 * A DEFINITION AND NOT ONLY A HOOK because two readers want it and only one of
 * them renders: the page subscribes, and the command PANEL is produced from a
 * click — and from a cold load at `?panel=action:<id>`, where no page has
 * mounted at all. Asking through the same definition is what stops the two from
 * drifting into two shapes of one answer (§13).
 */
export const maintenanceActionsQuery = {
  queryKey: ["/api/maintenance/actions"],
  queryFn: async () =>
    toEngineShape<MaintenanceAction[]>("MAINT_ACTIONS", await read("/api/maintenance/actions")),
};

/** The actions maintenance offers. */
export function useMaintenanceActions() {
  return useQuery(maintenanceActionsQuery);
}

/** What deleting has already done. */
export function useDeletionJournal() {
  return useQuery({
    queryKey: ["/api/maintenance/destructive-log"],
    queryFn: async () =>
      toEngineShape<DeletionJournal>("JOURNAL", await read("/api/maintenance/destructive-log")),
  });
}
