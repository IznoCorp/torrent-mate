// What the « Trackers » page asks the server for.
//
// DECLARED BY THE FEATURE, never by the frame: the page's reads are its own,
// and the frame names the page once, in its navigation row.
import { useQuery } from "@tanstack/react-query";
import { read } from "../../lib/query-client";
import type { Schemas } from "../../lib/contract-schemas";

/** One configured tracker, in the contract's names. */
export type Tracker = Schemas["Tracker"];

/** The address of the trackers' summary. */
const TRACKERS_ADDRESS = "/api/trackers";

/**
 * Every configured tracker, its ratio, volumes, trend and health.
 *
 * @returns The query, its answer in the contract's names.
 */
export function useTrackers() {
  return useQuery({
    queryKey: [TRACKERS_ADDRESS],
    queryFn: async () => read<Tracker[]>(TRACKERS_ADDRESS),
  });
}
