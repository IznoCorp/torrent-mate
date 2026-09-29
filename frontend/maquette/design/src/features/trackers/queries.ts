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

/** What the ratio alert says of the page's answers: per tracker, and per entry. */
export type Alert = {
  /** The trackers under their own alert threshold. */
  under: Set<string>;
  /** The trackers refusing the configured identifier — one unit each. */
  refused: Set<string>;
  /** The entries, `hash:tracker`, whose obligation is broken while they are still active. */
  breached: Set<string>;
};

/**
 * The ratio alert — ONE derivation, read by every place it is drawn (§ 13).
 *
 * A tracker is in alert under its OWN threshold, never another's; a refused
 * identifier is the tracker's, counted once for it, never once per torrent it
 * affects (the cause lives on the tracker); an obligation is in breach when it
 * is broken, neither met nor released, on an entry still in the client.
 *
 * @param trackers The trackers' summary.
 * @param downloads The client's entries.
 * @param obligations The seeding obligations.
 * @returns What is in alert.
 */
export function alertOf(trackers: Tracker[], downloads: Download[], obligations: Obligation[]): Alert {
  const active = new Set(downloads.map((entry) => `${entry.infoHash}:${entry.tracker}`));
  return {
    under: new Set(trackers.filter((tracker) => tracker.alertThreshold !== null && tracker.ratio !== null
      && tracker.ratio < tracker.alertThreshold).map((tracker) => tracker.name)),
    refused: new Set(trackers.filter((tracker) => tracker.identifierRefusedSince !== null)
      .map((tracker) => tracker.name)),
    breached: new Set(obligations
      .filter((obligation) => obligation.breachedAt !== null && obligation.satisfiedAt === null
        && obligation.releasedAt === null)
      .map((obligation) => `${obligation.infoHash}:${obligation.sourceTracker}`)
      .filter((key) => active.has(key))),
  };
}
