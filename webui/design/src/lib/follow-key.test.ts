// The key a title is crossed to at an act's door (K3-G1).
//
// WHAT MAKES THIS NON-VACUOUS. The follows' read is mocked to hold two follows, one of them a
// film whose TVDB id comes before its TMDB id in the record: a rule that took the first
// provider it met, or matched on a part of the title, would answer the wrong key.
import { describe, expect, it, vi } from "vitest";

vi.mock("./query-client", () => ({
  sharedQueryClient: undefined,
  read: async () => [
    { title: "Silo", kind: "show", ids: { tmdb: 125988, tvdb: "403245" } },
    { title: "Wicker", kind: "movie", ids: { tvdb: 7, tmdb: 99 } },
  ],
}));

const { followKeyOf, followKeyOfTitle, followSegment } = await import("./follow-key");

describe("the key of a medium", () => {
  it("is TVDB first for a show and TMDB first for a film", () => {
    expect(followKeyOf({ ids: { tmdb: 1, tvdb: 2 }, kind: "show" })).toBe("tvdb:2");
    expect(followKeyOf({ ids: { tmdb: 1, tvdb: 2 }, kind: "movie" })).toBe("tmdb:1");
  });

  it("is none for a medium that names no provider", () => {
    expect(followKeyOf({ ids: {}, kind: "show" })).toBeNull();
    expect(followKeyOf({ ids: null, kind: "show" })).toBeNull();
  });

  it("travels with its colon encoded", () => {
    expect(followSegment("tvdb:403245")).toBe("tvdb%3A403245");
  });
});

describe("the key of a title", () => {
  it("is read from the follows when no landed read carries the identity", async () => {
    expect(await followKeyOfTitle("Silo")).toBe("tvdb:403245");
    expect(await followKeyOfTitle("Wicker")).toBe("tmdb:99");
  });

  it("is none for a title nothing identifies", async () => {
    expect(await followKeyOfTitle("A title nobody holds")).toBeNull();
  });
});
