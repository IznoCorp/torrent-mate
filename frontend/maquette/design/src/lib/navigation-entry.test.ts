// The entry an arrival carries: three fields of what a tap knew, and never a body.
import { describe, expect, it } from "vitest";
import { carriedBy, carryingState, type CarriedIdentity } from "./navigation-entry";

describe("the carried entry", () => {
  it("writes exactly a title, a poster and the identifiers, whatever it is handed", () => {
    // A whole sheet handed to the writer: the browser's history has a size
    // ceiling, so nothing but the three fields may reach the entry.
    const sheet = {
      title: "Silo",
      poster: "assets/posters/silo.webp",
      ids: { tvdb: 403245 },
      overview: "a synopsis that must not travel",
      cast: [{ name: "Rebecca Ferguson" }],
    } as CarriedIdentity;
    const carried = carriedBy(carryingState(sheet));
    expect(Object.keys(carried ?? {}).sort()).toEqual(["ids", "poster", "title"]);
    expect(carried).toEqual({ title: "Silo", poster: "assets/posters/silo.webp", ids: { tvdb: 403245 } });
  });

  it("reads nothing from an entry no tap wrote", () => {
    expect(carriedBy({ tm: "nav", page: "lib" })).toBeUndefined();
    expect(carriedBy(null)).toBeUndefined();
    expect(carriedBy(undefined)).toBeUndefined();
  });
});
