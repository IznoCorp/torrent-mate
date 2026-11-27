// A one-off season of a show the mock marks as uncatalogued is refused, as the server refuses it.
//
// WHAT MAKES THIS NON-VACUOUS. The same ask is made before the show is marked and after: the first is
// answered with a season, the second with `409 acquisition.season_unknown` and a queue that did not move.
// The same two reads are made before and after: the marked show serves no episode list.
import { beforeEach, describe, expect, it } from "vitest";
import INCOMPLETE_SHOWS from "./seeds/incomplete-shows.json";
import { routes } from "./handlers";
import { resolve, settled } from "./router";
import { followForKey, keyOfMedium } from "./follow-key";
import { mockState, resetMockState } from "./state";
import { poseUncatalogued } from "./handlers/season-recovery";

type Answer = { status: number; payload: any };

// An incomplete show nobody follows: a season of it is a one-off.
const SHOW = (INCOMPLETE_SHOWS as { title: string; ids: Record<string, unknown> }[])
  .find((one) => one.title === "Les aventures de Tintin")!; // french-ok: a media title, the fixture's own
const KEY = keyOfMedium({ ids: SHOW.ids, kind: "show" })!;
const SEASON = 3;

/** Asks the season the way the interface does. */
function ask(): Answer {
  const path = `/acquisition/follows/${encodeURIComponent(KEY)}/seasons/${SEASON}/grab`;
  const found = resolve(routes(), "POST", path);
  if (found === null) throw new Error(`no route ${path}`);
  const answer = found.route.handle({ path, parameters: found.parameters, query: new URLSearchParams(), body: undefined });
  return settled(201, answer as never) as Answer;
}

/** How many cards each world holds in flight. */
const inFlight = () => [mockState().inFlight.length, mockState().inFlightReel.length];

beforeEach(() => resetMockState());

describe("a season of a show the mock marks as uncatalogued", () => {
  it("is a one-off the mock takes while the show is not marked", () => {
    expect(followForKey(KEY)).toBeUndefined();
    expect(ask().status).toBe(201);
  });

  it("is refused 409 acquisition.season_unknown once marked, and queues nothing", () => {
    poseUncatalogued(SHOW.title);
    const before = inFlight();

    const answer = ask();

    expect([answer.status, answer.payload.code, answer.payload.params]).toEqual(
      [409, "acquisition.season_unknown", { followedId: KEY }],
    );
    expect(inFlight()).toEqual(before);
  });
});

/** Reads one of the show's two media answers, as the sheet and the follow panel do. */
function read(tail: string): any {
  const path = `/media/tvdb/${SHOW.ids.tvdb}${tail}`;
  const found = resolve(routes(), "GET", path);
  if (found === null) throw new Error(`no route ${path}`);
  return found.route.handle({ path, parameters: found.parameters, query: new URLSearchParams(), body: undefined });
}

describe("the reads of a show the mock marks as uncatalogued", () => {
  it("serve its episode list while the show is not marked", () => {
    expect(Object.keys(read("").episodes)).toContain(String(SEASON));
    expect(read("/seasons").aired[String(SEASON)]).toBeGreaterThan(0);
  });

  it("serve no episode list on the sheet, and no date on its seasons", () => {
    const listed = read("").seasons.map((one: { number: number }) => one.number);
    poseUncatalogued(SHOW.title);

    const sheet = read("");

    expect(sheet.episodes).toBeNull();
    expect(sheet.seasons.map((one: { number: number }) => one.number)).toEqual(listed);
    expect(sheet.seasons.map((one: { airDate: unknown }) => one.airDate)).toEqual(listed.map(() => null));
  });

  it("serve the held seasons only, with nothing known of them", () => {
    const { owned } = read("/seasons");
    const held = Object.keys(owned).map(Number).sort((left, right) => left - right);
    poseUncatalogued(SHOW.title);

    const answer = read("/seasons");

    expect(answer.owned).toEqual(owned);
    expect(answer.seasons).toEqual(
      held.map((number) => ({ number, episodes: null, airDate: null, offCatalogue: [] })),
    );
    expect(answer.aired).toEqual(Object.fromEntries(held.map((number) => [String(number), null])));
  });
});
