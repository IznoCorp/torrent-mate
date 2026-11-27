// A season the server cannot count is refused, and said in the refusal's own terms.
//
// WHAT MAKES THIS NON-VACUOUS. The layer refuses with the code the contract declares; the verb must
// name that reason (never « did not go through »), and tell its caller so the season's row words it.
// The row's note is read as DRAWN, through the ask both surfaces call: dropping the mark, or the
// forgetting a new ask does, changes what is rendered.
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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

const { askForSeason, grabSeason } = await import("./season-grab");
const { SeasonUnknown } = await import("./season-unknown");

/** The words one season's row draws about the ask, as text; empty when it draws none. */
function rowNote(client: QueryClient, title: string, season: number): string {
  const html = renderToStaticMarkup(
    createElement(QueryClientProvider, { client }, createElement(SeasonUnknown, { title, season })),
  );
  return html.replace(/<[^>]*>/g, "").replace(/&#x27;/g, "'");
}

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

describe("the season's row after askForSeason", () => {
  const UNKNOWN = { status: 409, title: "no", detail: "no", code: "acquisition.season_unknown" };

  it("words the refusal on the season asked, and on no other", async () => {
    refusal = UNKNOWN;
    const client = new QueryClient();
    expect(rowNote(client, "Silo", 5)).toBe("");

    await askForSeason(client, "Silo", 5);

    expect(rowNote(client, "Silo", 5)).toBe(i18next.t("refusals.acquisition.season_unknown"));
    expect(rowNote(client, "Silo", 4)).toBe("");
  });

  it("takes the words down when the season is asked again", async () => {
    refusal = UNKNOWN;
    const client = new QueryClient();
    await askForSeason(client, "Silo", 5);

    refusal = { status: 409, title: "no", detail: "no", code: "follow.ambiguous" };
    await askForSeason(client, "Silo", 5);

    expect(rowNote(client, "Silo", 5)).toBe("");
  });
});
