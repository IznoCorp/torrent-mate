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

/** One entry of the download client, on the tracker it runs on. */
export type Download = Schemas["Download"];

/** One seeding obligation an entry owes its tracker. */
export type Obligation = Schemas["Obligation"];

/** The address of the download client's entries. */
const DOWNLOADS_ADDRESS = "/api/acquisition/downloads";

/** The address of the seeding obligations. */
const OBLIGATIONS_ADDRESS = "/api/acquisition/obligations";

/**
 * Every entry the download client holds, one per tracker it runs on.
 *
 * @returns The query, its answer in the contract's names.
 */
export function useDownloads() {
  return useQuery({
    queryKey: [DOWNLOADS_ADDRESS],
    queryFn: async () => read<Schemas["Downloads"]>(DOWNLOADS_ADDRESS),
  });
}

/**
 * Every seeding obligation, running or closed.
 *
 * @returns The query, its answer in the contract's names.
 */
export function useObligations() {
  return useQuery({
    queryKey: [OBLIGATIONS_ADDRESS],
    queryFn: async () => read<Schemas["Obligations"]>(OBLIGATIONS_ADDRESS),
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
