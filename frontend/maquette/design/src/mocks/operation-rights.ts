// THE RIGHT EVERY OPERATION ASKS FOR — the refusal side of § 17, in one table.
//
// EVERY OPERATION THE LAYER ANSWERS IS NAMED HERE, a write AND a read (F28,
// F30): `operation-rights.test.ts` refuses a route this table does not name, so
// a new operation cannot arrive ungated by forgetting. `null` is a DECISION —
// the session's own acts, and the reads every account makes — never a default.
//
// A LIST IS « ANY OF »: Système's status is read by whoever may open Système or
// Maintenance, the settings catalogue by whoever opens the configuration or a
// page that shows a setting. A write names exactly one right, because the
// forbidden-writes list (ruling 23) subtracts rights and a write must be
// subtractable by name.
//
// THE ACQUISITION READS ARE NOT REFUSED: an account that may not see another's
// acquisitions reads its own subset on a 200 (`acquisition.see.others` is a
// filter, never a 403), and an account with no acquisition right reads an empty
// one.
import type { Right } from "../lib/rights";

/** What one operation asks for: a right, any of several, or nothing. */
export type Asked = Right | readonly Right[] | null;

// The acquisition section's own door: requesting, or seeing everyone's.
const ACQUISITION: readonly Right[] = ["acquisition.request", "acquisition.see.others"];
// Piloting a tunnel: one's own, or any.
const PILOT: readonly Right[] = ["acquisition.pilot.own", "acquisition.pilot.any"];

/** Every operation, and what it asks for. */
export const OPERATION_RIGHTS: Readonly<Record<string, Asked>> = {
  // The session's own acts: every identity, under any ceiling (F28).
  readAccount: null,
  signIn: null,
  signOut: null,
  signInWithPlex: null,
  readVersion: null,
  // The account's own notification choices and its devices' tokens: each
  // account reads its own, and the read answers only the types its rights
  // receive (ruling Q1 A). Writing them is a right, so the read-only
  // instance's ceiling subtracts it like any other write.
  readNotificationPreferences: null,
  updateNotificationPreference: "notifications.manage",
  registerPushDevice: "notifications.manage",
  // The roster: « Comptes » manages it; the reassign chooser reads it narrowly (F46).
  readAccounts: ["accounts.manage", "acquisition.reassign"],
  createAccount: "accounts.manage",
  updateAccount: "accounts.manage",
  createRole: "accounts.manage",
  updateRole: "accounts.manage",

  readLibraryItems: "library.read",
  readLibraryCategories: "library.read",
  readLibraryRecent: "library.read",
  readLibraryIncomplete: "library.read",
  readLibraryMembership: "library.read",
  readMediaSheet: "library.read",
  readMediaSeasons: "library.read",
  deleteLibraryItems: "library.delete",
  rescrapeMedia: "library.rescrape",

  readFollows: null,
  readFollowCompleteness: null,
  readAcquisitionQueue: null,
  readAcquisitionStatus: null,
  readJourney: null,
  readDecisions: ACQUISITION,
  readStaging: ACQUISITION,
  readStagedMediaCopies: ACQUISITION,
  readStagingDestinations: ACQUISITION,
  readSuggestions: "acquisition.request",
  searchProviders: "acquisition.request",
  readReleases: PILOT,
  createFollow: "acquisition.request",
  updateFollow: "acquisition.follow",
  deleteFollow: "acquisition.follow",
  restoreFollow: "acquisition.follow",
  searchForFollow: PILOT,
  grabForFollow: PILOT,
  grabSeasonForFollow: PILOT,
  requeueJourney: PILOT,
  // THE ACCOUNT'S OWN SEEN MARK on a closed tunnel (BK5): whoever reads
  // « À traiter » reads its closures, and marks them seen for itself.
  dismissClosure: "acquisition.todo.view",
  rescrapeJourney: PILOT,
  setAcquisitionQuality: "acquisition.quality.own",
  setAcquisitionPause: "acquisition.pause.own",
  reassignRequester: "acquisition.reassign",

  runDetection: "pipeline.control",
  deleteStagedMedia: "pipeline.control",
  continueStagedMedia: "pipeline.control",
  discardStagedMedia: "pipeline.control",
  reclassifyStagedMedia: "pipeline.control",
  restoreReclassifiedMedia: "pipeline.control",
  resolvePlexMatch: "pipeline.control",
  resolveDecision: "pipeline.control",
  reopenDecision: "pipeline.control",
  enqueueForResolution: "pipeline.control",
  dismissDecision: "pipeline.control",
  searchForDecision: "pipeline.control",
  runPipeline: "pipeline.control",
  pausePipeline: "pipeline.control",
  resumePipeline: "pipeline.control",
  killPipeline: "pipeline.control",
  setWatcher: "pipeline.control",
  runMaintenanceAction: "pipeline.control",

  readPipeline: "system.view",
  readPipelineHistory: "system.view",
  readRun: "system.view",
  readServices: "system.view",
  readDependencies: "system.view",
  readErrors: "system.view",
  readSchedulers: "system.view",
  readDisks: "system.view",
  readIndexHealth: "system.view",
  readMaintenanceActions: "system.view",
  readDeletionJournal: "system.view",
  readLocks: "system.view",

  readTrackers: "trackers.view",
  readDownloads: "trackers.view",
  readObligations: "trackers.view",
  // THE MEDIA SHEET'S BLOCK summarises the Trackers page: the same right (L18 § 1.2).
  readMediaCrossSeed: "trackers.view",
  removeDownload: "trackers.control",
  markBrokenObligationSeen: "trackers.control",
  cutCrossSeed: "trackers.control",
  searchCrossSeed: "trackers.control",
  // PUBLISHING AT A THIRD PARTY is its own right, never implied by `trackers.control` (L23 DESIGN § 0.2).
  uploadCrossSeed: "trackers.upload",
  writeCrossSeedExclusion: "trackers.control",
  undoCrossSeedExclusion: "trackers.control",

  readSettings: ["configuration.view", "trackers.view", "system.view"],
  readConfigurationStatus: ["configuration.view", "system.view"],
  readSecrets: "configuration.view",
  readConfigurationFiles: "configuration.view",
  readConfigurationFile: "configuration.view",
  updateSecrets: "configuration.write",
  updateConfigurationFile: "configuration.write",
  restartWeb: "configuration.write",
  previewRanking: "configuration.write",
};

/**
 * Whether the signed-in account may call one operation.
 *
 * @param asked What the operation asks for.
 * @param holdsAny The account's own test, from the model.
 * @returns True when nothing is asked or one asked right is held.
 */
export function allowed(asked: Asked, holdsAny: (rights: readonly Right[]) => boolean): boolean {
  if (asked === null) return true;
  return holdsAny(typeof asked === "string" ? [asked] : asked);
}

/**
 * The operations that act on ONE acquisition and ask it to be the caller's own
 * (§ 17's own tunnel, F27): `acquisition.pilot.own` opens them on an
 * acquisition the caller is among the requesters of, `acquisition.pilot.any` on
 * every one.
 */
export const OWN_SCOPED: ReadonlySet<string> = new Set([
  "searchForFollow",
  "grabForFollow",
  "grabSeasonForFollow",
  "requeueJourney",
  "rescrapeJourney",
  "updateFollow",
  "deleteFollow",
]);

/**
 * The acquisition one call acts on, by its title.
 *
 * @param parameters What the path template captured.
 * @param query The request's query.
 * @returns The title — a follow's id and a journey's subject are its title here.
 */
export function subjectOf(parameters: Record<string, string>, query: URLSearchParams): string {
  return parameters.followedId ?? parameters.infoHash ?? query.get("title") ?? "";
}
