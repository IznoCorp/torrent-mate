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

/** One setting of the catalogue, in the contract's names. */
export type Setting = Schemas["Setting"];

/** The address of the settings catalogue — the one the settings page reads. */
const CATALOGUE_ADDRESS = "/api/config/schema";

/**
 * The settings catalogue, flattened: the SAME read the settings page makes,
 * under the same key, so both pages draw one answer.
 *
 * @returns The settings, every topic's in turn, once answered.
 */
export function useSettingsCatalogue(): Setting[] | undefined {
  const { data } = useQuery({
    queryKey: [CATALOGUE_ADDRESS],
    queryFn: async () => read<Schemas["SettingsTopic"][]>(CATALOGUE_ADDRESS),
  });
  return data?.flatMap((topic) => topic.settings);
}
