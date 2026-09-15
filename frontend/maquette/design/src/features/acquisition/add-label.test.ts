// The add act's label, on every branch it has.
//
// WHAT MAKES THIS NON-VACUOUS. Each expectation is the literal the engine's own
// copy produced for the same kind, mode and state, so a key missing or
// mis-aimed fails by naming the key i18next returns instead; the store is
// written for each case, so a label read from the wrong field fails a case. The
// store is a stand-in holding the two fields the label reads: the function
// reads the store through `lib/store-access.ts`, and the real one is the shell's.
import { beforeEach, describe, expect, it } from "vitest";
import "../../lib/unit-words";
import { installStore } from "../../lib/store-access";
import { addVerb } from "./add-label";
import type { SearchResult } from "./reference";

let state: Record<string, unknown> = {};
const store = {
  read: () => ({ state }),
  write: (patch: Record<string, unknown>) => {
    state = { ...state, ...patch };
  },
};
installStore(store as unknown as Parameters<typeof installStore>[0]);

const film = { t: "Dune", y: "2021", k: "Film", ov: "", owned: false, followed: false } as SearchResult;
const series = { ...film, t: "Silo", k: "Série" } as SearchResult; // french-ok: a data value the search answers
const ownedFilm = { ...film, owned: true };

beforeEach(() => store.write({ addMode: "add", added: new Set<number>() }));

describe("addVerb", () => {
  it("says the act a film and a series take, with an ellipsis for what is held", () => {
    expect(addVerb(film, 0)).toBe("Ajouter"); // french-ok: the engine's own output, asserted
    expect(addVerb(series, 0)).toBe("Suivre"); // french-ok: the engine's own output, asserted
    expect(addVerb(ownedFilm, 0)).toBe("Ajouter…"); // french-ok: the engine's own output, asserted
  });

  it("says what was done once it is", () => {
    store.write({ added: new Set([0]) });
    expect(addVerb(film, 0)).toBe("✓ Ajouté"); // french-ok: the engine's own output, asserted
    expect(addVerb(series, 0)).toBe("✓ Suivi"); // french-ok: the engine's own output, asserted
    expect(addVerb(film, 1)).toBe("Ajouter"); // french-ok: the engine's own output, asserted
  });

  it("associates, and never with an ellipsis, in the identify mode", () => {
    store.write({ addMode: "identify" });
    expect(addVerb(ownedFilm, 0)).toBe("Associer"); // french-ok: the engine's own output, asserted
    store.write({ added: new Set([0]) });
    expect(addVerb(series, 0)).toBe("✓ Associé"); // french-ok: the engine's own output, asserted
  });
});
