// R-L17-a's enumerations half: the six words, and no bare code (NE-DOIT-PAS-4).
import { describe, expect, it } from "vitest";
import i18next from "../../lib/unit-words";
import contract from "../../../../contract/openapi.json";
import { isFailure as layerCounts } from "../../mocks/cross-seed-state";
import {
  CROSS_SEED_TONE, REASON_FAMILY, familyWord, isFailure, isSearchable, reasonSentence, rosterLine, stateWord,
  type CrossSeedPair, type CrossSeedReason, type CrossSeedState,
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
    tracker: "tr4ker", state: "error", reason, candidate: null, waitReason: null, at: null, stoppedAt: null,
    stopCause: null, entryHash: null, excluded: false, searching: false,
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
    for (const reason of REASONS) expect(isFailure(refused(reason)), reason).toBe(layerCounts(refused(reason)));
  });
});

describe("the search offered", () => {
  const pair = (state: CrossSeedState, excluded = false): CrossSeedPair => ({ ...refused("fetch_failed"), state, excluded });

  it("resumes a stopped pair once its exclusion is undone, never while it is excluded", () => {
    expect(isSearchable(pair("stopped"), false, true)).toBe(true);
    expect(isSearchable(pair("stopped", true), false, true)).toBe(false);
    expect(isSearchable(pair("active"), false, true)).toBe(false);
    expect(isSearchable(pair("trackerWithout"), false, true)).toBe(false);
  });

  it("offers nothing while the original still downloads", () => {
    for (const state of ["noMatch", "error", "notSearched", "stopped"] as CrossSeedState[]) {
      expect(isSearchable(pair(state), false, false), state).toBe(false);
      expect(isSearchable(pair(state), false, true), state).toBe(true);
    }
  });
});

describe("the kinds of trouble", () => {
  it("gives the candidate that is the original itself its own word, never the files-mismatch one", () => {
    expect(familyWord("self_candidate")).not.toBe(familyWord("file_list_mismatch"));
    expect(i18next.exists("screens.crossSeed.families.self")).toBe(true);
  });
});

describe("the roster's line", () => {
  const summary = { enabled: true, engineEnabled: true, active: 2, failed: 0, lastInjectedAt: null };

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
