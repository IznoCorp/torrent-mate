// What the « Trackers » page asks the server for.
//
// DECLARED BY THE FEATURE, never by the frame: the page's reads are its own,
// and the frame names the page once, in its navigation row.
import { useQuery } from "@tanstack/react-query";
import { read, sharedQueryClient } from "../../lib/query-client";
import type { Schemas } from "../../lib/contract-schemas";

/** One configured tracker, in the contract's names. */
export type Tracker = Schemas["Tracker"];

// THE CACHE KEYS, SPELLED AS LITERALS AND EXPORTED: the live relay's rules and
// the bar's badge key on them, and the relay's guard reads a key only where it
// is written out.
/** The key of the trackers' summary. */
export const trackersKey = ["/api/trackers"];

/**
 * Every configured tracker, its ratio, volumes, trend and health.
 *
 * @returns The query, its answer in the contract's names.
 */
export function useTrackers() {
  return useQuery({
    queryKey: trackersKey,
    queryFn: async () => read<Tracker[]>(trackersKey[0]),
  });
}

/** One entry of the download client, on the tracker it runs on. */
export type Download = Schemas["Download"];

/** One seeding obligation an entry owes its tracker. */
export type Obligation = Schemas["Obligation"];

/** The key of the download client's entries. */
export const downloadsKey = ["/api/acquisition/downloads"];

/** The key of the seeding obligations. */
export const obligationsKey = ["/api/acquisition/obligations"];

/**
 * Every entry the download client holds, one per tracker it runs on.
 *
 * @returns The query, its answer in the contract's names.
 */
export function useDownloads() {
  return useQuery({
    queryKey: downloadsKey,
    queryFn: async () => read<Schemas["Downloads"]>(downloadsKey[0]),
  });
}

/**
 * Every seeding obligation, running or closed.
 *
 * @returns The query, its answer in the contract's names.
 */
export function useObligations() {
  return useQuery({
    queryKey: obligationsKey,
    queryFn: async () => read<Schemas["Obligations"]>(obligationsKey[0]),
  });
}

/** One setting of the catalogue, in the contract's names. */
export type Setting = Schemas["Setting"];

/** The address of the settings catalogue — the one the settings page reads. */
const CATALOGUE_ADDRESS = "/api/config/schema";

/** The settings catalogue's read: its answer once there, and whether it failed. */
export type Catalogue = {
  /** The settings, every topic's in turn — undefined while the read is under way. */
  settings: Setting[] | undefined;
  /** Whether the read failed. */
  isError: boolean;
  /** Asks the read again. */
  retry: () => void;
};

/**
 * The settings catalogue, flattened: the SAME read the settings page makes,
 * under the same key, so both pages draw one answer. ITS WAIT AND ITS FAILURE
 * TRAVEL WITH IT: a caller must be able to tell « not yet » from « none ».
 *
 * @returns The catalogue's read.
 */
export function useSettingsCatalogue(): Catalogue {
  const query = useQuery({
    queryKey: [CATALOGUE_ADDRESS],
    queryFn: async () => read<Schemas["SettingsTopic"][]>(CATALOGUE_ADDRESS),
  });
  return {
    settings: query.data?.flatMap((topic) => topic.settings),
    isError: query.isError,
    retry: () => void query.refetch(),
  };
}

/** What the ratio alert says of the page's answers: per tracker, and per entry. */
export type Alert = {
  /** The trackers under their own alert threshold. */
  under: Set<string>;
  /** The trackers refusing the configured identifier — one unit each. */
  refused: Set<string>;
  /** The entries, `hash:tracker`, whose obligation is broken while they are still active. */
  breached: Set<string>;
  /** Per tracker, its broken obligations whose torrent is gone and that nobody has seen yet. */
  unseen: Map<string, number>;
};

/**
 * The ratio alert — ONE derivation, read by every place it is drawn (§ 13).
 *
 * A tracker is in alert under its OWN threshold, never another's; a refused
 * identifier is the tracker's, counted once for it, never once per torrent it
 * affects (the cause lives on the tracker); an obligation is in breach when it
 * is broken, neither met nor released, on an entry still in the client; a
 * broken obligation whose torrent is gone counts until it is marked seen, one
 * unit each.
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
    unseen: new Map(trackers.map((tracker) => [
      tracker.name, tracker.brokenObligations.filter((row) => !row.seen).length,
    ])),
  };
}

/**
 * The Trackers tab's badge: every unit of the alert, summed — the page's own
 * derivation read from the cache, never a second count (ruling 12, § 13).
 *
 * @returns How many things are in alert, 0 before the reads have answered.
 */
export function trackersBadge(): number {
  const trackers = sharedQueryClient?.getQueryData<Tracker[]>(trackersKey) ?? [];
  const downloads = sharedQueryClient?.getQueryData<Schemas["Downloads"]>(downloadsKey)?.downloads ?? [];
  const obligations = sharedQueryClient?.getQueryData<Schemas["Obligations"]>(obligationsKey)?.items ?? [];
  const alert = alertOf(trackers, downloads, obligations);
  const unseen = [...alert.unseen.values()].reduce((total, count) => total + count, 0);
  return alert.under.size + alert.refused.size + alert.breached.size + unseen;
}

/**
 * The reads the badge derives from, OBSERVED on every page the bar is drawn on,
 * so a live event refetches them and the badge moves without the page open.
 */
export function useTrackersBadgeReads(): void {
  useTrackers();
  useDownloads();
  useObligations();
}
