// A tap on the release picker takes a release of the title ON SCREEN, whichever list answered last (O-14).
//
// WHAT MAKES THIS NON-VACUOUS. The cache holds the lists of two titles and the one counting every release,
// and the one on screen is the OLDEST of them: the state a settled search leaves when it reads every cached
// list again and another title's answers last. The verb is run as the tap runs it, against the lookup the
// application installs.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../../lib/unit-words";
import { createQueryClient } from "../../lib/query-client";

const taken: [string, string | undefined][] = [];
const verbs = new Map<string, (value: string) => void>();

vi.mock("../../lib/shell-doors", () => ({
  toast: { show: () => undefined },
  panel: { close: () => undefined, redraw: () => undefined, produce: () => undefined },
  bridge: { back: () => undefined },
  screens: {},
  redraw: () => undefined,
}));
vi.mock("../../lib/queue", () => ({
  queueActions: { take: (title: string, releaseId?: string) => void taken.push([title, releaseId]) },
}));
vi.mock("../../lib/verbs", () => ({
  registerVerb: (name: string, run: (value: string) => void) => void verbs.set(name, run),
}));

const { installReleasesLookup } = await import("./queries");
await import("./verbs");

const client = createQueryClient();
installReleasesLookup(client);

/** Caches the list of one title, as answered at *updatedAt*. */
function answered(title: string, id: string, updatedAt: number): void {
  client.setQueryData(["/api/v1/acquisition/releases", title],
    [{ id, name: `${title} ${id}`, resolution: "1080p", source: "WEB-DL", language: "MULTi" }], { updatedAt });
}

describe("a tap on the release picker", () => {
  beforeEach(() => {
    taken.length = 0;
    // The picker's address carries the title as the library wrote it, year and all.
    vi.stubGlobal("window", { location: { pathname: `/releases/${encodeURIComponent("Silo (2023)")}` } });
  });

  afterEach(() => {
    client.clear();
    vi.unstubAllGlobals();
  });

  it("takes the row of the title on screen though other lists were answered since", () => {
    answered("Silo", "silo-1", 1_000);
    answered("Ted Lasso", "ted-1", 2_000);
    answered("", "any-1", 3_000);

    verbs.get("pick-release")?.("0");

    expect(taken).toEqual([["Silo (2023)", "silo-1"]]);
  });

  it("takes nothing when the title on screen has no list, whatever another title holds", () => {
    answered("Ted Lasso", "ted-1", 2_000);

    verbs.get("pick-release")?.("0");

    expect(taken).toEqual([]);
  });
});
