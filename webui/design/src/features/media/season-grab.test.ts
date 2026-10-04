// A season's ask says where it went — held on the committed words (B-562).
//
// WHAT MAKES THIS NON-VACUOUS. The same answer is given for a followed show and
// for one nobody follows, so the only thing that can tell the two sentences apart
// is the follow the verb reads; the followed leg holds the count sentence, the
// one-off leg the sentence naming « En cours », and each names its key's text.
import { beforeEach, describe, expect, it, vi } from "vitest";
import i18next from "../../lib/unit-words";

const shown: string[] = [];
let followed: string[] = [];

vi.mock("../../lib/query-client", () => ({
  HELD: Symbol("held"),
  isRequestFailure: () => false,
  send: async () => ({ season: 5, absorbedCount: 23, queued: false, reused: false, runUid: null }),
}));

vi.mock("../../lib/shell-doors", () => ({
  panel: undefined,
  toast: { show: ({ message }: { message: string }) => shown.push(message) },
  get followedTitles() {
    return () => followed;
  },
}));

const { grabSeason } = await import("./season-grab");

describe("grabSeason's sentence", () => {
  beforeEach(() => {
    shown.length = 0;
  });

  it("says a one-off season ask went to « En cours », with its own words", async () => {
    followed = [];
    await grabSeason("Les Animaniacs", 5); // french-ok: a media title, the fixture's own
    expect(shown).toEqual([
      i18next.t("verbs.media.seasonAskedOneOff", { season: 5, title: "Les Animaniacs" }), // french-ok: a media title
    ]);
    expect(shown[0]).toContain("« En cours »");
  });

  it("keeps the follow's count sentence for a followed show", async () => {
    followed = ["Silo"];
    await grabSeason("Silo", 5);
    expect(shown).toEqual([i18next.t("verbs.media.seasonAsked", { season: 5, count: 23, title: "Silo" })]);
  });
});
