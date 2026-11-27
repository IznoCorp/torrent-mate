// A season the server cannot count is refused, and said in the refusal's own terms.
//
// WHAT MAKES THIS NON-VACUOUS. The layer refuses with the code the contract declares; the verb must
// name that reason (never « did not go through »), and tell its caller so the season's row words it.
import { beforeEach, describe, expect, it, vi } from "vitest";
import i18next from "../../lib/unit-words";

const shown: string[] = [];
let refusal: unknown;

vi.mock("../../lib/query-client", () => ({
  HELD: Symbol("held"),
  isRequestFailure: () => true,
  send: async () => {
    throw refusal;
  },
}));
vi.mock("../../lib/follow-key", () => ({
  followKeyOfTitle: async () => "tvdb:1",
  followSegment: encodeURIComponent,
}));
vi.mock("../../lib/shell-doors", () => ({
  panel: undefined,
  toast: { show: ({ message }: { message: string }) => shown.push(message) },
  followedTitles: undefined,
}));

const { grabSeason } = await import("./season-grab");

describe("grabSeason refused", () => {
  beforeEach(() => {
    shown.length = 0;
  });

  it("says the episode list is not known, and reports it to the season's row", async () => {
    refusal = { status: 409, title: "no", detail: "no", code: "acquisition.season_unknown" };
    let reported = 0;

    await grabSeason("Silo", 5, () => {
      reported += 1;
    });

    expect(shown).toEqual([i18next.t("verbs.media.seasonUnknown", { season: 5, title: "Silo" })]);
    expect(shown[0]).toContain("liste des épisodes"); // french-ok: the sentence, asserted as drawn
    expect(reported).toBe(1);
  });

  it("keeps the generic words for another refusal, and reports nothing", async () => {
    refusal = { status: 409, title: "no", detail: "no", code: "follow.ambiguous" };
    let reported = 0;

    await grabSeason("Silo", 5, () => {
      reported += 1;
    });

    expect(shown).toEqual([i18next.t("verbs.media.seasonRefused", { season: 5, title: "Silo" })]);
    expect(reported).toBe(0);
  });
});
