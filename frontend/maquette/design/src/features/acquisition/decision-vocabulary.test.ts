// The arbitration vocabulary, held on the COMMITTED resources.
//
// WHAT MAKES THIS NON-VACUOUS. Every word is the literal the engine's own copy
// produced for the same token, and each function is also asserted on a token
// the interface has no word for — the branch where a missing key would
// otherwise print the key itself instead of the fallback the readers expect.
import { describe, expect, it } from "vitest";
import "../../lib/unit-words";
import {
  REASON_TONE,
  decisionState,
  decisionStateDetail,
  reasonDetail,
  reasonLabel,
  viaLabel,
} from "./decision-vocabulary";

describe("the reason a decision is asked for", () => {
  it("has a word, a sentence and a tone for each of the four reasons", () => {
    expect(reasonLabel("below_threshold")).toBe("Confiance faible");
    expect(reasonLabel("manual")).toBe("Envoi manuel");
    expect(reasonDetail("ambiguous")).toBe(
      "Plusieurs candidats étaient trop proches pour trancher automatiquement.", // french-ok: the engine's own output, asserted
    );
    for (const reason of Object.keys(REASON_TONE)) {
      expect(reasonLabel(reason)).not.toBe(reason);
      expect(reasonDetail(reason)).not.toBe("");
    }
    expect(Object.keys(REASON_TONE)).toHaveLength(4);
  });

  it("says an unknown reason as its token, with no sentence", () => {
    expect(reasonLabel("unheard_of")).toBe("unheard_of");
    expect(reasonDetail("unheard_of")).toBe("");
  });
});

describe("a settled decision's state and how its choice was reached", () => {
  it("pairs each state's tone with its word, and explains it", () => {
    expect(decisionState("resolved")).toEqual(["success", "Réglée"]); // french-ok: the engine's own output, asserted
    expect(decisionState("dismissed")).toEqual(["neutral", "Laissée telle quelle"]); // french-ok: the engine's own output, asserted
    expect(decisionState("superseded")).toEqual(["info", "Remplacée depuis"]); // french-ok: the engine's own output, asserted
    expect(decisionStateDetail("resolved")).toBe(
      "Un candidat a été choisi, et un re-scrapage ciblé a été lancé.", // french-ok: the engine's own output, asserted
    );
  });

  it("draws no chip for an unknown state, and says an unknown way as its token", () => {
    expect(decisionState("pending")).toBeNull();
    expect(decisionStateDetail("pending")).toBe("");
    expect(viaLabel("pick")).toBe("choisi dans la liste"); // french-ok: the engine's own output, asserted
    expect(viaLabel("search_override")).toBe("trouvé par une recherche manuelle"); // french-ok: the engine's own output, asserted
    expect(viaLabel("telepathy")).toBe("telepathy");
  });
});
