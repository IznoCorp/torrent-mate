// The cross-seed's words: the operator's six states, their tones, and the
// reasons a refusal gives, grouped by the kind of trouble.
//
// THE WORD CARRIES THE MEANING, the tone only helps (§ 12): every state is one
// of the six words the operator wrote (§ 19; OPEN 5 = A; round 10 Q5 = A), and
// every reason a sentence in clear French, never the engine's bare code
// (NE-DOIT-PAS-4). THE COUNTS ARE THE SERVER'S: nothing here counts a pair —
// the summary read says how many are active and how many failed (§ 13).
import i18next from "i18next";
import type { Schemas } from "../../lib/contract-schemas";
import type { ChipTone } from "../../ui/variants";

/** One (torrent, tracker) pair of a cross-seed, in the contract's names. */
export type CrossSeedPair = Schemas["CrossSeedPair"];

/** One of the six states. */
export type CrossSeedState = CrossSeedPair["state"];

/** A refusal's code, the engine's twelve and the upload's two (L23 § 2.2). */
export type CrossSeedReason = NonNullable<CrossSeedPair["reason"]>;

/** The kind of trouble a refusal is: § 19 point 1 asks that a mismatch is not read as a failure. */
export type ReasonFamily = "files" | "self" | "attempt" | "engine";

/** The tone each state wears on its chip. */
export const CROSS_SEED_TONE: Readonly<Record<CrossSeedState, ChipTone>> = {
  active: "success",
  stopped: "waiting",
  trackerWithout: "neutral",
  error: "danger",
  noMatch: "neutral",
  notSearched: "waiting",
};

/** The kind of trouble each code is (DESIGN § 2.2). */
export const REASON_FAMILY: Readonly<Record<CrossSeedReason, ReasonFamily>> = {
  piece_length_mismatch: "files",
  file_list_mismatch: "files",
  root_name_mismatch: "files",
  v2_hybrid: "files",
  self_candidate: "self",
  fetch_failed: "attempt",
  verify_timeout: "attempt",
  recheck_failed: "attempt",
  magnet_not_supported: "attempt",
  parse_failed: "attempt",
  inject_failed: "engine",
  obligation_write_failed: "engine",
  // THE RESERVED SLOT, FILLED (round 8 Q8, « le cas A »): an upload that could
  // not be created or published is the engine not finishing, never a mismatch.
  creation_failed: "engine",
  publish_failed: "engine",
};

/** The families that are FAILURES — the badge's term; « pas les mêmes fichiers » is an ordinary outcome. */
export const COUNTED_FAMILIES: ReadonlySet<ReasonFamily> = new Set(["attempt", "engine"]);

/**
 * A state in the operator's word.
 *
 * @param state The pair's state.
 * @returns The word.
 */
export function stateWord(state: CrossSeedState): string {
  return i18next.t(`screens.crossSeed.states.${state}`);
}

/**
 * A refusal's reason in a sentence.
 *
 * @param reason The code.
 * @returns The sentence.
 */
export function reasonSentence(reason: CrossSeedReason): string {
  return i18next.t(`screens.crossSeed.reasons.${reason}`);
}

/**
 * The kind of trouble a refusal is, in words.
 *
 * @param reason The code.
 * @returns The family's name.
 */
export function familyWord(reason: CrossSeedReason): string {
  return i18next.t(`screens.crossSeed.families.${REASON_FAMILY[reason]}`);
}

/**
 * Whether a pair's refusal is a failure — the badge's own reading.
 *
 * @param pair The pair.
 * @returns True on an « erreur » whose reason is of a counted family.
 */
export function isFailure(pair: CrossSeedPair): boolean {
  return pair.state === "error" && pair.reason !== null && COUNTED_FAMILIES.has(REASON_FAMILY[pair.reason]);
}

/**
 * One tracker's cross-seed at rest, in one sentence (S1).
 *
 * THE ENGINE'S OWN SWITCH IS SAID FIRST, and the tracker's own SECOND, on the
 * same line (M6): two facts, neither hiding the other. A switch off cuts NEW
 * cross-seeds only, so the torrents still running there are said too.
 *
 * @param summary The tracker's cross-seed, as the summary read answers it.
 * @returns The sentence.
 */
export function rosterLine(summary: Schemas["TrackerCrossSeed"]): string {
  const say = (key: string, values: Record<string, unknown> = {}) => i18next.t(`screens.crossSeed.line.${key}`, values);
  let line: string;
  if (!summary.engineEnabled) {
    line = say("engineOffOwn", { engine: say("engineOff"), own: say(summary.enabled ? "ownOn" : "ownOff") });
  } else if (!summary.enabled) {
    line = summary.active === 0 ? say("off") : say("offRunning", { count: summary.active });
  } else {
    line = summary.active === 0 ? say("activeNone") : say("active", { count: summary.active });
  }
  return summary.failed === 0 ? line : say("failures", { line, count: summary.failed });
}

// The states a search may be asked on (§ 17 point 1): nothing is offered that the
// engine would refuse to act on. « stoppé » is one: resuming a stopped pair IS
// the search (§ 3.3), which its exclusion alone withholds.
const SEARCHABLE: ReadonlySet<CrossSeedState> = new Set(["noMatch", "error", "notSearched", "stopped"]);

/**
 * Whether a pair is one the engine would otherwise act on, its own tracker's
 * switch left aside — the shared half `isSearchable` and `isSwitchedOff` split on.
 *
 * @param pair The pair.
 * @param titleExcluded Whether its whole title is excluded.
 * @param originComplete Whether the original is complete.
 * @returns True on a pair with no match, in error, not yet searched or stopped,
 *     neither excluded nor already searching, its original complete.
 */
function isEligible(pair: CrossSeedPair, titleExcluded: boolean, originComplete: boolean): boolean {
  return SEARCHABLE.has(pair.state) && !pair.excluded && !pair.searching && !titleExcluded && originComplete;
}

/** Who switched a tracker itself off: the operator, or a failure (« Injoignable », a refused identifier). */
export type TrackerOff = NonNullable<Schemas["Tracker"]["disabled"]>["by"];

/**
 * Whether a tracker is ITSELF switched off, and by whom — the engine neither
 * searches nor publishes anything on a tracker off or down, whatever its two
 * cross-seed switches say (§ 17 point 1).
 *
 * @param tracker The tracker as `/api/v1/trackers` answers it, or undefined while unread.
 * @returns Who switched it off, or null while it is on (or unread: nothing is said that is not read).
 */
export function trackerOffBy(tracker: Schemas["Tracker"] | undefined): TrackerOff | null {
  if (tracker === undefined) return null;
  if (tracker.disabled !== null) return tracker.disabled.by;
  return tracker.enabled ? null : "operator";
}

/**
 * Whether « Chercher un cross-seed » is offered on a pair.
 *
 * @param pair The pair.
 * @param titleExcluded Whether its whole title is excluded.
 * @param originComplete Whether the original is complete: the engine searches
 *     nothing for a torrent still downloading, and the pair's line says so.
 * @param trackerEnabled Whether the pair's OWN tracker carries its cross-seed
 *     switch on: a switch off refuses the search just as the engine would
 *     (§ 17 point 1), whatever the pair's state.
 * @param trackerOn Whether the pair's tracker is itself on — neither switched
 *     off by the operator nor down.
 * @returns True on a pair with no match, in error, not yet searched or stopped,
 *     neither excluded nor already searching, its original complete, its
 *     tracker on and its switch on.
 */
export function isSearchable(
  pair: CrossSeedPair, titleExcluded: boolean, originComplete: boolean, trackerEnabled: boolean, trackerOn: boolean,
): boolean {
  return isEligible(pair, titleExcluded, originComplete) && trackerOn && trackerEnabled;
}

/**
 * Whether a pair reads eligible for a search EXCEPT its own tracker's switch is
 * off — the reason a row gives instead of the button (§ 17 point 1: the true
 * reason, never a silent absence). A tracker itself off is said instead.
 *
 * @param pair The pair.
 * @param titleExcluded Whether its whole title is excluded.
 * @param originComplete Whether the original is complete.
 * @param trackerEnabled Whether the pair's own tracker carries its switch on.
 * @param trackerOn Whether the pair's tracker is itself on.
 * @returns True when the switch alone is what withholds the search.
 */
export function isSwitchedOff(
  pair: CrossSeedPair, titleExcluded: boolean, originComplete: boolean, trackerEnabled: boolean, trackerOn: boolean,
): boolean {
  return isEligible(pair, titleExcluded, originComplete) && trackerOn && !trackerEnabled;
}

/**
 * Whether a pair reads eligible for a search EXCEPT its tracker is itself off
 * or down — the reason a row gives instead of both acts (§ 17 point 1), before
 * any of its switches: nothing is searched nor published on it.
 *
 * @param pair The pair.
 * @param titleExcluded Whether its whole title is excluded.
 * @param originComplete Whether the original is complete.
 * @param trackerOn Whether the pair's tracker is itself on.
 * @returns True when the tracker's own state is what withholds the acts.
 */
export function isTrackerOff(
  pair: CrossSeedPair, titleExcluded: boolean, originComplete: boolean, trackerOn: boolean,
): boolean {
  return isEligible(pair, titleExcluded, originComplete) && !trackerOn;
}

/**
 * Whether a client entry is complete — the engine's condition for searching its cross-seed.
 *
 * @param entry The origin's entry, or its progress.
 * @returns True once every byte is held.
 */
export function isComplete(entry: { progress: number }): boolean {
  return entry.progress >= 1;
}

// The states an upload may be asked on (L23 § 1 clause 1): only where nothing
// already cross-seeds. Never « stoppé » — resuming a stopped pair IS the search.
const UPLOADABLE: ReadonlySet<CrossSeedState> = new Set(["noMatch", "error", "notSearched"]);

/** What « Créer et publier un torrent » reads of a pair's origin and tracker. */
export type UploadGate = {
  /** Whether the whole title is excluded. */
  titleExcluded: boolean;
  /** Whether the origin is active in the client, complete and seeding (round 11 OPEN 1 = A). */
  originSeeding: boolean;
  /** Whether the pair's tracker is itself on — neither switched off by the operator nor down. */
  trackerOn: boolean;
  /** Whether the pair's tracker carries its cross-seed switch on. */
  trackerEnabled: boolean;
  /** Whether the pair's tracker carries its « accepte les uploads » switch on (round 11 OPEN 2 = B). */
  acceptsUploads: boolean;
};

/**
 * Whether a pair reads eligible for an upload, its tracker's two switches left
 * aside — the shared half `isUploadable` and `isUploadRefused` split on.
 *
 * @param pair The pair.
 * @param gate What the gesture reads of its origin.
 * @returns True on a pair with no match, in error or not yet searched, neither
 *     excluded nor already searching or uploading, its origin seeding.
 */
function isUploadEligible(pair: CrossSeedPair, gate: UploadGate): boolean {
  return UPLOADABLE.has(pair.state) && !pair.excluded && !pair.searching && !pair.uploading
    && !gate.titleExcluded && gate.originSeeding;
}

/**
 * Whether « Créer et publier un torrent » is offered on a pair (L23 § 2.3).
 *
 * @param pair The pair.
 * @param gate What the gesture reads of its origin and its tracker.
 * @returns True where nothing already cross-seeds and the engine would act.
 */
export function isUploadable(pair: CrossSeedPair, gate: UploadGate): boolean {
  return isUploadEligible(pair, gate) && gate.trackerOn && gate.trackerEnabled && gate.acceptsUploads;
}

/**
 * Whether a pair reads eligible for an upload EXCEPT its tracker refuses
 * uploads — the reason a row gives instead of the act (§ 17 point 1: the true
 * reason, never a silent absence). The tracker off and the cross-seed switch
 * off are said already.
 *
 * @param pair The pair.
 * @param gate What the gesture reads of its origin and its tracker.
 * @returns True when the « accepte les uploads » switch alone withholds it.
 */
export function isUploadRefused(pair: CrossSeedPair, gate: UploadGate): boolean {
  return isUploadEligible(pair, gate) && gate.trackerOn && gate.trackerEnabled && !gate.acceptsUploads;
}

/**
 * Whether a client entry is active, complete and seeding — the one torrent an
 * upload may be created from (round 11 OPEN 1 = A).
 *
 * @param entry The origin's entry.
 * @returns True on a complete entry the client is seeding.
 */
export function isSeeding(entry: { progress: number; state: string }): boolean {
  return isComplete(entry) && entry.state === "seeding";
}
