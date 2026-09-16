// The add act's label, on every branch it has.
//
// WHAT MAKES THIS NON-VACUOUS. Each expectation is the literal the engine's own
// copy produced for the same kind, mode and state, so a key missing or
// mis-aimed fails by naming the key i18next returns instead; the visit is set
// for each case, so a label read from the wrong mode or the wrong result fails a
// case.
import { beforeEach, describe, expect, it } from "vitest";
import "../../lib/unit-words";
import { addVerb } from "./add-label";
import { beginVisit, markAdded, setVisitMode } from "./add-visit";
import type { SearchResult } from "./types";

const film = { title: "Dune", year: "2021", kind: "Film", overview: "", owned: false, followed: false, ids: { tmdb: 438631 }, poster: null } as SearchResult;
const series = { ...film, title: "Silo", kind: "Série", ids: { tvdb: 403245 } } as SearchResult; // french-ok: a data value the search answers
const ownedFilm = { ...film, owned: true, ids: { tmdb: 1 } };

beforeEach(() => {
  beginVisit();
  setVisitMode("follow");
});

describe("addVerb", () => {
  it("says the act a film and a series take, with an ellipsis for what is held", () => {
    expect(addVerb(film)).toBe("Ajouter"); // french-ok: the engine's own output, asserted
    expect(addVerb(series)).toBe("Suivre"); // french-ok: the engine's own output, asserted
    expect(addVerb(ownedFilm)).toBe("Ajouter…"); // french-ok: the engine's own output, asserted
  });

  it("says what was done once it is, for that result and no other", () => {
    markAdded(film);
    markAdded(series);
    expect(addVerb(film)).toBe("✓ Ajouté"); // french-ok: the engine's own output, asserted
    expect(addVerb(series)).toBe("✓ Suivi"); // french-ok: the engine's own output, asserted
    expect(addVerb(ownedFilm)).toBe("Ajouter…"); // french-ok: the engine's own output, asserted
  });

  it("keeps a film and a series apart when they carry the same identifiers", () => {
    const seriesOfTheFilm = { ...series, ids: film.ids };
    markAdded(seriesOfTheFilm);
    expect(addVerb(film)).toBe("Ajouter"); // french-ok: the engine's own output, asserted
  });

  it("forgets what an earlier visit did", () => {
    markAdded(film);
    beginVisit();
    expect(addVerb(film)).toBe("Ajouter"); // french-ok: the engine's own output, asserted
  });

  it("associates, and never with an ellipsis, in the identify mode", () => {
    setVisitMode("identify");
    expect(addVerb(ownedFilm)).toBe("Associer"); // french-ok: the engine's own output, asserted
    markAdded(series);
    expect(addVerb(series)).toBe("✓ Associé"); // french-ok: the engine's own output, asserted
  });
});
