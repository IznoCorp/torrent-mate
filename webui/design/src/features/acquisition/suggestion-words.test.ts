// A suggestion's words are the interface's own: the server sends a code and the values (K3-G7).
//
// WHAT MAKES THIS NON-VACUOUS. Each reason the contract can send is worded and read back whole, in
// French, with the piece that is emphasised; a year nobody knows is checked to leave no « null » and
// no stray separator behind.
import { describe, expect, it } from "vitest";
import i18next from "i18next";
import FRENCH from "../../i18n/fr.json";
import SUGGESTIONS from "../../mocks/seeds/suggestions.json";
import type { Schemas } from "../../lib/contract-schemas";
import { factsLine, reasonPieces, reasonSegments } from "./suggestion-words";

await i18next.init({
  lng: "fr",
  resources: { fr: { translation: FRENCH } },
  interpolation: { escapeValue: false },
});

type Reason = Schemas["SuggestionReason"];

/** A reason's sentence, whole. */
const whole = (why: Reason) =>
  reasonPieces(why).map((piece) => (typeof piece === "string" ? piece : piece.emphasis)).join("");

/** What a reason's sentence emphasises. */
const emphasised = (why: Reason) =>
  reasonPieces(why).flatMap((piece) => (typeof piece === "string" ? [] : [piece.emphasis]));

describe("a suggestion's reason", () => {
  it("names the owned titles and emphasises the first", () => {
    const why: Reason = { code: "similar_to_owned", titles: ["Supergirl", "Disclosure Day"], count: null };
    expect(whole(why)).toBe("Parce que vous avez Supergirl et Disclosure Day."); // french-ok: the rendered words this test asserts
    expect(emphasised(why)).toEqual(["Supergirl"]);
  });

  it("names the followed title", () => {
    const why: Reason = { code: "similar_to_followed", titles: ["Silo"], count: null };
    expect(whole(why)).toBe("Parce que vous suivez Silo.");
    expect(emphasised(why)).toEqual(["Silo"]);
  });

  it("emphasises the count, not a title, when the titles were counted", () => {
    const why: Reason = { code: "similar_to_owned", titles: ["Ninja Turtles", "Supergirl"], count: 4 };
    expect(whole(why)).toBe("Recoupé par 4 titres de votre médiathèque, dont Ninja Turtles et Supergirl."); // french-ok: the rendered words this test asserts
    expect(emphasised(why)).toEqual(["4"]);
  });

  it("counts without naming when no title is served", () => {
    const why: Reason = { code: "similar_to_followed", titles: [], count: 1 };
    expect(whole(why)).toBe("Recoupé par 1 titre que vous suivez."); // french-ok: the rendered words this test asserts
    expect(emphasised(why)).toEqual(["1"]);
  });

  it.each(["similar_to_owned", "similar_to_followed"] as const)(
    "says a whole sentence for %s when the server can name no title",
    (code) => {
      const why: Reason = { code, titles: [], count: null };
      expect(whole(why)).toMatch(/^Proche de .+\.$/);
      expect(emphasised(why)).toEqual([]);
    },
  );

  it("keeps a title that carries the sentence's own punctuation as one piece", () => {
    const why: Reason = { code: "similar_to_owned", titles: ["Moi, et {{titles}}."], count: null };
    expect(emphasised(why)).toEqual(["Moi, et {{titles}}."]);
  });

  it("hands the panel the same pieces under its own name for emphasis", () => {
    const why: Reason = { code: "similar_to_followed", titles: ["Silo"], count: null };
    expect(reasonSegments(why)).toContainEqual({ e: "Silo" });
  });

  it("words every seeded card without a code or a placeholder left in it", () => {
    for (const suggestion of SUGGESTIONS as unknown as Schemas["Suggestion"][]) {
      expect(whole(suggestion.why)).not.toMatch(/discover\.|\{\{|undefined|null/);
    }
  });
});

describe("a suggestion's facts line", () => {
  it("says the year and the kind in the interface's words", () => {
    expect(factsLine({ year: 2020, kind: "movie" })).toBe("2020 · Film");
    expect(factsLine({ year: 2024, kind: "show" })).toBe("2024 · Série"); // french-ok: the rendered words this test asserts
  });

  it("says the kind alone when no year is known", () => {
    expect(factsLine({ year: null, kind: "show" })).toBe("Série"); // french-ok: the rendered words this test asserts
  });
});
