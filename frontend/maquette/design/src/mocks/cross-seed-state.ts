// What the layer holds of the cross-seed: each origin torrent's pairs, tracker
// by tracker, and the engine's search quota — mutable, so a gesture can move them.
//
// INVENTED, and said so (L17 DESIGN § 2.3): nothing records a per-pair state
// today, so the seed is composed from the design's cases. HELD BESIDE THE
// LAYER'S STATE, AND RENEWED WITH IT, the trackers' subject's own discipline.
//
// THE DEFAULT IS THE LIVE STATES (round 9 Q9): the configuration's « off » are
// example values, never the operator's choice, so the layer turns every
// cross-seed switch ON when it seeds its settings. « le moteur est coupé » and a
// tracker's own switch off are named scenarios, reached through a dial. So is
// an upload refused (L23): by default a torrent created and published is taken.
import CROSS_SEED from "./seeds/cross-seed.json";
import { mockState } from "./state";
import type { components } from "../contract/types";

type Schemas = components["schemas"];

/** The cross-seed subject, as the layer holds it. */
export type CrossSeedHeld = {
  /** Per origin hash, its pairs and whether its whole title is excluded. */
  torrents: Record<string, Schemas["TorrentCrossSeed"]>;
  quota: Schemas["CrossSeedQuota"];
  /** Every search asked, in order: what a rule reads the request by. */
  searches: { infoHash: string; tracker: string | null }[];
  /** Every upload asked, in order: what a rule reads the request by. */
  uploads: { infoHash: string; tracker: string }[];
  /**
   * How an upload asked on a pair ends, keyed `<origin hash>:<tracker>` — a
   * dial's choice; a pair the dial never named is published (L23 § 2.3).
   */
  uploadOutcomes: Record<string, UploadOutcome>;
};

/** The two codes an upload is refused by (L23 § 2.2). */
export type UploadRefusal = "creation_failed" | "publish_failed";

/** How an upload ends: published, or refused with one of its two codes and the tracker's own words. */
export type UploadOutcome = { reason: null } | { reason: UploadRefusal; trackerReason: string | null };

/**
 * An upload's refusal as the engine would answer it: a publication refused
 * carries the tracker's own words (round 11 OPEN 3 = A), a creation never
 * reached the tracker and carries none.
 *
 * @param reason The code.
 * @returns The outcome.
 */
function refusalOf(reason: UploadRefusal): UploadOutcome {
  return { reason, trackerReason: reason === "publish_failed" ? CROSS_SEED.publishRefusal : null };
}

// WHERE THE SWITCHES ARE SET: the tracker's own, and the engine's.
const SETTING_PREFIX = "tracker.providers.";
const CROSS_SEED_SUFFIX = ".cross_seed";
// A tracker's « accepte les uploads » switch, distinct from its cross-seed one (round 11 OPEN 2 = B).
const UPLOADS_SUFFIX = ".accepts_uploads";
const ENGINE_KEY = "cross_seed.enabled";

// The reasons that COUNT — the attempt failed, the engine could not finish, an
// upload's creation or publication among them (OPEN 8 = A, round 8 Q8). An
// ordinary mismatch is not a failure.
const FAILURES: ReadonlySet<string> = new Set([
  "fetch_failed", "verify_timeout", "recheck_failed", "magnet_not_supported", "parse_failed",
  "inject_failed", "obligation_write_failed", "creation_failed", "publish_failed",
]);

// The milliseconds in a second: the layer dates in Unix-epoch seconds.
const MILLISECONDS_PER_SECOND = 1000;

/**
 * The settings key of one tracker's cross-seed switch.
 *
 * @param tracker The tracker's configured name.
 * @returns The key.
 */
export function crossSeedKey(tracker: string): string {
  return SETTING_PREFIX + tracker + CROSS_SEED_SUFFIX;
}

/**
 * The settings key of one tracker's « accepte les uploads » switch.
 *
 * @param tracker The tracker's configured name.
 * @returns The key.
 */
export function uploadsKey(tracker: string): string {
  return SETTING_PREFIX + tracker + UPLOADS_SUFFIX;
}

/**
 * Whether a settings key is a cross-seed switch — the engine's, a tracker's, or
 * a tracker's « accepte les uploads ».
 *
 * @param key The setting's key.
 * @returns True for any of the three.
 */
function isCrossSeedSwitch(key: string): boolean {
  return key === ENGINE_KEY
    || (key.startsWith(SETTING_PREFIX) && (key.endsWith(CROSS_SEED_SUFFIX) || key.endsWith(UPLOADS_SUFFIX)));
}

/**
 * Turns every cross-seed switch on — the DEFAULT scenario's live states. Called
 * where the layer seeds its settings, so Réglages and the Trackers page read
 * the same switches from the first answer.
 *
 * @param settings The settings, as just copied from their seed.
 * @returns The same settings, the switches on.
 */
export function liveCrossSeedSettings(settings: Schemas["SettingsTopic"][]): Schemas["SettingsTopic"][] {
  for (const setting of settings.flatMap((topic) => topic.settings)) {
    if (!isCrossSeedSwitch(setting.key)) continue;
    setting.raw = true;
    setting.displayedValue = String(true);
  }
  return settings;
}

/**
 * The raw value of one boolean setting, where the settings write puts it.
 *
 * @param key The setting's key.
 * @returns Its value, or true when no setting names it.
 */
export function switchOf(key: string): boolean {
  const setting = mockState().settings.flatMap((topic) => topic.settings).find((one) => one.key === key);
  return typeof setting?.raw === "boolean" ? setting.raw : true;
}

/**
 * Sets one boolean setting, where the settings write puts it.
 *
 * @param key The setting's key.
 * @param value Its value.
 */
function setSwitch(key: string, value: boolean): void {
  for (const setting of mockState().settings.flatMap((topic) => topic.settings)) {
    if (setting.key !== key) continue;
    setting.raw = value;
    setting.displayedValue = String(value);
  }
}

const held = new WeakMap<object, CrossSeedHeld>();

/**
 * The cross-seed subject for the layer's current state, seeded on first read.
 *
 * @returns What the layer holds.
 */
export function crossSeedState(): CrossSeedHeld {
  const owner = mockState();
  let subject = held.get(owner);
  if (subject === undefined) {
    subject = {
      torrents: structuredClone(CROSS_SEED.torrents) as unknown as Record<string, Schemas["TorrentCrossSeed"]>,
      quota: structuredClone(CROSS_SEED.quota),
      searches: [],
      uploads: [],
      uploadOutcomes: {},
    };
    held.set(owner, subject);
  }
  return subject;
}

/** The obligations a cross-seed created — invented rows, the trackers' subject seeds them in. */
export const CROSS_SEED_OBLIGATIONS = CROSS_SEED.obligations as Omit<Schemas["Obligation"], "crossSeedOf">[];

/**
 * Whether a pair's refusal counts as a FAILURE.
 *
 * @param pair The pair.
 * @returns True on `error` with a failure-kind reason.
 */
export function isFailure(pair: Schemas["CrossSeedPair"]): boolean {
  return pair.state === "error" && pair.reason !== null && FAILURES.has(pair.reason);
}

/**
 * One origin's cross-seed, as the downloads read answers it.
 *
 * @param entry The client's entry.
 * @returns Its pairs on an origin, null on a cross-seed's own entry.
 */
export function crossSeedOfEntry(entry: Omit<Schemas["Download"], "crossSeed">): Schemas["TorrentCrossSeed"] | null {
  if (entry.provenance !== "downloaded") return null;
  return crossSeedState().torrents[entry.infoHash] ?? { pairs: [], titleExcluded: false };
}

/**
 * One tracker's cross-seed summary, DERIVED from the same pairs the downloads
 * read answers — never a second count that could disagree (R-L17-b). ONLY THE
 * TORRENTS STILL IN THE CLIENT count: an origin removed takes its pairs out of
 * the failures and the running torrents alike.
 *
 * @param tracker The tracker's configured name.
 * @param downloads The client's entries, the torrents still in it.
 * @returns The summary.
 */
export function trackerCrossSeed(
  tracker: string, downloads: readonly Pick<Schemas["Download"], "infoHash">[],
): Schemas["TrackerCrossSeed"] {
  const present = new Set(downloads.map((entry) => entry.infoHash));
  const pairs = Object.entries(crossSeedState().torrents)
    .flatMap(([infoHash, torrent]) => present.has(infoHash) ? torrent.pairs : [])
    .filter((pair) => pair.tracker === tracker);
  const injected = pairs.filter((pair) => pair.state === "active" && pair.at !== null).map((pair) => pair.at as number);
  return {
    enabled: switchOf(crossSeedKey(tracker)),
    acceptsUploads: switchOf(uploadsKey(tracker)),
    engineEnabled: switchOf(ENGINE_KEY),
    active: pairs.filter((pair) => pair.state === "active").length,
    failed: pairs.filter(isFailure).length,
    lastInjectedAt: injected.length === 0 ? null : Math.max(...injected),
  };
}

// WHICH ORIGIN EACH CROSS-SEED OBLIGATION IS THE COPY OF, read once off the seed:
// the pair that injected the entry the obligation is owed on. A cut empties the
// pair's `entryHash`; the obligation still says whose copy it was.
const BORN_OF: ReadonlyMap<string, string> = new Map(Object.entries(CROSS_SEED.torrents).flatMap(
  ([origin, torrent]) => torrent.pairs.flatMap((pair) => pair.entryHash === null ? [] : [[pair.entryHash, origin] as const])));

/**
 * The origin an obligation is the copy of, when a cross-seed created it.
 *
 * @param obligation The obligation.
 * @param downloads The client's entries, where the origin's title is read.
 * @returns The origin, or null.
 */
export function crossSeedOrigin(
  obligation: Omit<Schemas["Obligation"], "crossSeedOf">, downloads: Omit<Schemas["Download"], "crossSeed">[],
): Schemas["CrossSeedOrigin"] | null {
  const infoHash = BORN_OF.get(obligation.infoHash);
  if (infoHash === undefined) return null;
  const origin = downloads.find((entry) => entry.infoHash === infoHash);
  return { infoHash, title: origin?.title ?? obligation.title ?? "", media: origin?.ids ?? null };
}

/** The instant the layer dates a gesture at, Unix-epoch seconds. */
export function nowSeconds(): number {
  return Math.floor(Date.now() / MILLISECONDS_PER_SECOND);
}

/**
 * Stops every running pair on one tracker — the switch's « running ones too ».
 *
 * @param tracker The tracker's configured name.
 * @returns The client entries the stop removed.
 */
export function stopRunningOn(tracker: string): string[] {
  const stopped: string[] = [];
  for (const torrent of Object.values(crossSeedState().torrents)) {
    for (const pair of torrent.pairs) {
      if (pair.tracker !== tracker || pair.state !== "active") continue;
      if (pair.entryHash !== null) stopped.push(pair.entryHash);
      Object.assign(pair, { state: "stopped", stoppedAt: nowSeconds(), stopCause: "switch", entryHash: null });
    }
  }
  return stopped;
}

/** The dials a named state turns to reach a cross-seed state no verb produces. */
export type CrossSeedDials = {
  poseCrossSeedEngineOff: () => void;
  poseCrossSeedSwitchOff: (tracker: string) => void;
  poseCrossSeedPair: (infoHash: string, tracker: string, fields: Partial<Schemas["CrossSeedPair"]>) => void;
  crossSeedSearches: () => CrossSeedHeld["searches"];
  poseCrossSeedQuotaSpent: () => void;
  poseUploadsOff: (tracker: string) => void;
  poseUploadOutcome: (infoHash: string, tracker: string, reason: UploadRefusal | null) => void;
  posePairRefusedByUpload: (infoHash: string, tracker: string, reason: UploadRefusal) => void;
  crossSeedUploads: () => CrossSeedHeld["uploads"];
};

/** Those dials, over the cross-seed subject. */
export const crossSeedDials: CrossSeedDials = {
  // « LE MOTEUR EST COUPÉ » — the engine's own switch off; nothing running moves (M6).
  poseCrossSeedEngineOff: () => setSwitch(ENGINE_KEY, false),
  // ONE TRACKER'S OWN SWITCH OFF, its running pairs untouched.
  poseCrossSeedSwitchOff: (tracker: string) => setSwitch(crossSeedKey(tracker), false),
  // A DERIVATION, SHOWN AS ONE: a pair posed in a state no seed row holds.
  poseCrossSeedPair: (infoHash: string, tracker: string, fields: Partial<Schemas["CrossSeedPair"]>) => {
    const pair = crossSeedState().torrents[infoHash]?.pairs.find((one) => one.tracker === tracker);
    if (pair !== undefined) Object.assign(pair, fields);
  },
  // THE ENGINE'S DAILY QUOTA SPENT: a search asked now waits for tomorrow, still « en file ».
  poseCrossSeedQuotaSpent: () => {
    const quota = crossSeedState().quota;
    quota.used = quota.perDay;
  },
  // NOT A DIAL — a reading: the searches the layer was asked for.
  crossSeedSearches: () => structuredClone(crossSeedState().searches),
  // ONE TRACKER'S « ACCEPTE LES UPLOADS » OFF, its cross-seed switch untouched (round 11 OPEN 2 = B).
  poseUploadsOff: (tracker: string) => setSwitch(uploadsKey(tracker), false),
  // HOW AN UPLOAD ON ONE PAIR WILL END: the engine's refusal is a scenario, never the default.
  poseUploadOutcome: (infoHash: string, tracker: string, reason: UploadRefusal | null) => {
    crossSeedState().uploadOutcomes[`${infoHash}:${tracker}`] = reason === null ? { reason: null } : refusalOf(reason);
  },
  // A DERIVATION, SHOWN AS ONE: a pair an upload was refused on, as its outcome leaves it.
  posePairRefusedByUpload: (infoHash: string, tracker: string, reason: UploadRefusal) => {
    const pair = crossSeedState().torrents[infoHash]?.pairs.find((one) => one.tracker === tracker);
    if (pair === undefined) return;
    Object.assign(pair, refusalOf(reason), {
      state: "error", via: "upload", candidate: null, waitReason: null, at: nowSeconds(), excluded: false,
    });
  },
  // NOT A DIAL — a reading: the uploads the layer was asked for.
  crossSeedUploads: () => structuredClone(crossSeedState().uploads),
};
