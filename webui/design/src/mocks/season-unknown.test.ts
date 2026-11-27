// A one-off season of a show the mock marks as uncatalogued is refused, as the server refuses it.
//
// WHAT MAKES THIS NON-VACUOUS. The same ask is made before the show is marked and after: the first is
// answered with a season, the second with `409 acquisition.season_unknown` and a queue that did not move.
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
