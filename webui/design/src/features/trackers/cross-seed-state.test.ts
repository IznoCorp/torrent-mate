// R-L17-a's enumerations half: the six words, and no bare code (NE-DOIT-PAS-4).
import { describe, expect, it } from "vitest";
import i18next from "../../lib/unit-words";
import contract from "../../../../../contract/openapi.json";
import { isFailure as layerCounts } from "../../mocks/cross-seed-state";
import {
  CROSS_SEED_TONE, REASON_FAMILY, familyWord, isFailure, isSearchable, isSwitchedOff, isTrackerOff, isUploadRefused,
  isUploadable, reasonSentence, rosterLine, stateWord, trackerOffBy, type CrossSeedPair, type CrossSeedReason,
  type CrossSeedState,
} from "./cross-seed-state";

// The operator's six words, verbatim (§ 19; round 10 Q5 = A) — the rule's data.
const SIX = ["actif", "stoppé", "tracker sans cross-seed", "erreur de cross-seed", "sans correspondance", "pas encore cherché"]; // french-ok: the operator's words, rendered output asserted

const pairSchema = contract.components.schemas.CrossSeedPair.properties;
const STATES = pairSchema.state.enum as CrossSeedState[];
const REASONS = (pairSchema.reason.oneOf[0] as { enum: CrossSeedReason[] }).enum;

/**
 * A pair in error on a reason.
 *
 * @param reason The code.
 * @returns The pair.
 */
function refused(reason: CrossSeedReason): CrossSeedPair {
  return {
    tracker: "tr4ker", state: "error", reason, candidate: null, via: "search", trackerReason: null, waitReason: null,
    at: null, stoppedAt: null, stopCause: null, entryHash: null, excluded: false, searching: false, uploading: false,
  };
}

describe("the six words", () => {
  it("says every state the contract declares in the operator's own word, six of them", () => {
    expect(STATES.map(stateWord).sort()).toEqual([...SIX].sort());
    expect(Object.keys(CROSS_SEED_TONE).sort()).toEqual([...STATES].sort());
  });
});

describe("the reasons", () => {
  it("gives every code the contract declares a sentence, never the code itself", () => {
    for (const reason of REASONS) {
      const sentence = reasonSentence(reason);
      expect(i18next.exists(`screens.crossSeed.reasons.${reason}`), reason).toBe(true);
      expect(sentence).not.toContain(reason);
      expect(sentence).not.toContain("_");
    }
    expect(Object.keys(REASON_FAMILY).sort()).toEqual([...REASONS].sort());
  });

  it("counts a failed attempt and an unfinished injection, never a mismatch — as the layer does", () => {
    expect(isFailure(refused("file_list_mismatch"))).toBe(false);
    expect(isFailure(refused("self_candidate"))).toBe(false);
    expect(isFailure(refused("fetch_failed"))).toBe(true);
    expect(isFailure(refused("inject_failed"))).toBe(true);
    // THE UPLOAD'S TWO CODES, the reserved slot filled (round 8 Q8): failures, in
    // the family « the engine could not finish », never a family of their own.
    expect(isFailure(refused("creation_failed"))).toBe(true);
    expect(isFailure(refused("publish_failed"))).toBe(true);
    expect(REASON_FAMILY.creation_failed).toBe(REASON_FAMILY.inject_failed);
    expect(REASON_FAMILY.publish_failed).toBe(REASON_FAMILY.obligation_write_failed);
    for (const reason of REASONS) expect(isFailure(refused(reason)), reason).toBe(layerCounts(refused(reason)));
  });
});

describe("the search offered", () => {
  const pair = (state: CrossSeedState, excluded = false): CrossSeedPair => ({ ...refused("fetch_failed"), state, excluded });

  it("resumes a stopped pair once its exclusion is undone, never while it is excluded", () => {
    expect(isSearchable(pair("stopped"), false, true, true, true)).toBe(true);
    expect(isSearchable(pair("stopped", true), false, true, true, true)).toBe(false);
    expect(isSearchable(pair("active"), false, true, true, true)).toBe(false);
    expect(isSearchable(pair("trackerWithout"), false, true, true, true)).toBe(false);
  });

  it("offers nothing while the original still downloads", () => {
    for (const state of ["noMatch", "error", "notSearched", "stopped"] as CrossSeedState[]) {
      expect(isSearchable(pair(state), false, false, true, true), state).toBe(false);
      expect(isSearchable(pair(state), false, true, true, true), state).toBe(true);
    }
  });

  it("offers nothing on a pair whose own tracker's cross-seed switch is off, whatever its state (§ 17 point 1)", () => {
    for (const state of ["noMatch", "error", "notSearched", "stopped"] as CrossSeedState[]) {
      expect(isSearchable(pair(state), false, true, false, true), state).toBe(false);
      expect(isSwitchedOff(pair(state), false, true, false, true), state).toBe(true);
      expect(isSwitchedOff(pair(state), false, true, true, true), state).toBe(false);
    }
    // NEVER THE REASON when something else already withholds the search.
    expect(isSwitchedOff(pair("active"), false, true, false, true)).toBe(false);
    expect(isSwitchedOff(pair("stopped", true), false, true, false, true)).toBe(false);
    expect(isSwitchedOff(pair("stopped"), false, false, false, true)).toBe(false);
  });

  it("offers nothing on a tracker itself off or down, its switch on, and says the tracker, not the switch (§ 17 point 1)", () => {
    for (const state of ["noMatch", "error", "notSearched", "stopped"] as CrossSeedState[]) {
      expect(isSearchable(pair(state), false, true, true, false), state).toBe(false);
      expect(isTrackerOff(pair(state), false, true, false), state).toBe(true);
      expect(isTrackerOff(pair(state), false, true, true), state).toBe(false);
      expect(isSwitchedOff(pair(state), false, true, false, false), state).toBe(false);
    }
    expect(isTrackerOff(pair("active"), false, true, false)).toBe(false);
    expect(isTrackerOff(pair("stopped", true), false, true, false)).toBe(false);
  });
});

describe("the tracker itself off", () => {
  const tracker = (enabled: boolean, by: "operator" | "failure" | null) => ({
    enabled, disabled: by === null ? null : { by, reason: null, message: null, since: null },
  }) as unknown as Parameters<typeof trackerOffBy>[0];

  it("reads who switched it off, down or by the operator, and nothing while it is on or unread", () => {
    expect(trackerOffBy(tracker(true, null))).toBeNull();
    expect(trackerOffBy(tracker(false, "failure"))).toBe("failure");
    expect(trackerOffBy(tracker(false, "operator"))).toBe("operator");
    expect(trackerOffBy(tracker(false, null))).toBe("operator");
    expect(trackerOffBy(undefined)).toBeNull();
  });
});

describe("the upload offered (L23 § 2.3)", () => {
  const gate = { titleExcluded: false, originSeeding: true, trackerOn: true, trackerEnabled: true, acceptsUploads: true };
  const pair = (state: CrossSeedState, fields: Partial<CrossSeedPair> = {}): CrossSeedPair =>
    ({ ...refused("fetch_failed"), state, ...fields });

  it("is offered only where nothing already cross-seeds — never on a stopped, running or impossible pair", () => {
    for (const state of ["noMatch", "error", "notSearched"] as CrossSeedState[]) expect(isUploadable(pair(state), gate), state).toBe(true);
    for (const state of ["active", "stopped", "trackerWithout"] as CrossSeedState[]) expect(isUploadable(pair(state), gate), state).toBe(false);
  });

  it("is never offered on an excluded pair or title, a pair already searching or uploading, an origin not seeding", () => {
    expect(isUploadable(pair("noMatch", { excluded: true }), gate)).toBe(false);
    expect(isUploadable(pair("noMatch", { searching: true }), gate)).toBe(false);
    expect(isUploadable(pair("noMatch", { uploading: true }), gate)).toBe(false);
    expect(isUploadable(pair("noMatch"), { ...gate, titleExcluded: true })).toBe(false);
    expect(isUploadable(pair("noMatch"), { ...gate, originSeeding: false })).toBe(false);
  });

  it("reads both of the tracker's switches, and says when « accepte les uploads » alone withholds it", () => {
    expect(isUploadable(pair("noMatch"), { ...gate, trackerEnabled: false })).toBe(false);
    expect(isUploadable(pair("noMatch"), { ...gate, acceptsUploads: false })).toBe(false);
    expect(isUploadRefused(pair("noMatch"), { ...gate, acceptsUploads: false })).toBe(true);
    expect(isUploadRefused(pair("noMatch"), gate)).toBe(false);
    expect(isUploadRefused(pair("active"), { ...gate, acceptsUploads: false })).toBe(false);
    expect(isUploadRefused(pair("noMatch"), { ...gate, trackerEnabled: false, acceptsUploads: false })).toBe(false);
  });

  it("is never offered on a tracker itself off or down, both its switches on (§ 17 point 1)", () => {
    expect(isUploadable(pair("noMatch"), { ...gate, trackerOn: false })).toBe(false);
    expect(isUploadRefused(pair("noMatch"), { ...gate, trackerOn: false, acceptsUploads: false })).toBe(false);
  });
});

describe("the kinds of trouble", () => {
  it("gives the candidate that is the original itself its own word, never the files-mismatch one", () => {
    expect(familyWord("self_candidate")).not.toBe(familyWord("file_list_mismatch"));
    expect(i18next.exists("screens.crossSeed.families.self")).toBe(true);
  });
});

describe("the roster's line", () => {
  const summary = { enabled: true, acceptsUploads: true, engineEnabled: true, active: 2, failed: 0, lastInjectedAt: null };

  it("says the count the server gave, and its failures", () => {
    expect(rosterLine(summary)).toBe("Cross-seed : actif — 2 torrents");
    expect(rosterLine({ ...summary, failed: 1 })).toBe("Cross-seed : actif — 2 torrents · 1 échec"); // french-ok: the operator's words, rendered output asserted
  });

  it("says the engine off FIRST and the tracker's own switch SECOND (M6)", () => {
    expect(rosterLine({ ...summary, engineEnabled: false })).toBe("Cross-seed : le moteur est coupé · ce tracker : actif"); // french-ok: the operator's words, rendered output asserted
    expect(rosterLine({ ...summary, engineEnabled: false, enabled: false }))
      .toBe("Cross-seed : le moteur est coupé · ce tracker : coupé"); // french-ok: the operator's words, rendered output asserted
  });

  it("says a tracker switched off still runs what was running", () => {
    expect(rosterLine({ ...summary, enabled: false })).toBe("Cross-seed : coupé sur ce tracker — 2 torrents continuent"); // french-ok: the operator's words, rendered output asserted
  });
});
