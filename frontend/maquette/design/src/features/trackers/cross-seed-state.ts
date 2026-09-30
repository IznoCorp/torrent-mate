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

/** A refusal's code, the engine's twelve and the reserved upload slot. */
export type CrossSeedReason = NonNullable<CrossSeedPair["reason"]>;

/** The kind of trouble a refusal is: § 19 point 1 asks that a mismatch is not read as a failure. */
export type ReasonFamily = "files" | "self" | "attempt" | "engine" | "upload";

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
  upload_failed: "upload",
};

/** The families that are FAILURES — the badge's term; « pas les mêmes fichiers » is an ordinary outcome. */
export const COUNTED_FAMILIES: ReadonlySet<ReasonFamily> = new Set(["attempt", "engine", "upload"]);

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
 * Whether « Chercher un cross-seed » is offered on a pair.
 *
 * @param pair The pair.
 * @param titleExcluded Whether its whole title is excluded.
 * @param originComplete Whether the original is complete: the engine searches
 *     nothing for a torrent still downloading, and the pair's line says so.
 * @returns True on a pair with no match, in error, not yet searched or stopped,
 *     neither excluded nor already searching, its original complete.
 */
export function isSearchable(pair: CrossSeedPair, titleExcluded: boolean, originComplete: boolean): boolean {
  return SEARCHABLE.has(pair.state) && !pair.excluded && !pair.searching && !titleExcluded && originComplete;
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
