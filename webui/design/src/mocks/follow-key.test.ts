// A follow is addressed by its medium's key, in the layer and in the interface alike (K3-G1).
//
// WHAT MAKES THIS NON-VACUOUS. The layer reads the key with its own rule and the interface with
// its own (`lib/follow-key.ts`); the first leg holds the two to the same answer over every
// seeded follow, so either drifting fails. The others call the operations the way the
// interface does, with a key and with a title, and read what a server answers: a key names the
// follow, a title names nothing, a key nothing holds is a 404, and a body outside the contract's
// enum is refused.
import { beforeEach, describe, expect, it } from "vitest";
import FOLLOWS from "./seeds/follows.json";
import { routes } from "./handlers";
import { resolve } from "./router";
import { settled } from "./router";
import { followForKey, keyOfMedium, mediumOfKey, removedIndexForKey } from "./follow-key";
import { resetMockState } from "./state";
import { followKeyOf } from "../lib/follow-key";

type Answer = { status: number; payload: any };

/**
 * Calls one operation as the interface would, and reads the answer as the wire carries it.
 *
 * @param method The method.
 * @param path The path, its identifier already encoded.
 * @param body The request body, if any.
 * @param query The query, if any.
 * @returns The status and the body.
 */
function call(method: string, path: string, body?: unknown, query = ""): Answer {
  const found = resolve(routes(), method, path);
  if (found === null) throw new Error(`no route ${method} ${path}`);
  const answer = found.route.handle({ path, parameters: found.parameters, query: new URLSearchParams(query), body });
  return settled(200, answer as never) as Answer;
}

const KEY = (follow: { ids?: unknown; kind?: string }) => keyOfMedium(follow) as string;
const encoded = (key: string) => encodeURIComponent(key);

describe("the key a follow is addressed by", () => {
  beforeEach(() => resetMockState());

  it("is the same in the layer and in the interface, for every seeded follow", () => {
    for (const follow of FOLLOWS) {
      expect(keyOfMedium(follow), follow.title).toBe(followKeyOf(follow as never));
    }
  });

  it("is TVDB first for a show and TMDB first for a film", () => {
    const ids = { tmdb: 1, tvdb: 2, imdb: "tt3" };
    expect(keyOfMedium({ ids, kind: "show" })).toBe("tvdb:2");
    expect(keyOfMedium({ ids, kind: "movie" })).toBe("tmdb:1");
    expect(keyOfMedium({ ids: { imdb: "tt3" }, kind: "show" })).toBe("imdb:tt3");
    expect(keyOfMedium({ ids: {}, kind: "show" })).toBeNull();
  });

  it("names the follow, and refuses a title for one", () => {
    const [first] = FOLLOWS;
    expect(followForKey(KEY(first))?.title).toBe(first.title);
    expect(followForKey(first.title)).toBeUndefined();
    expect(mediumOfKey(first.title)).toBeNull();
    expect(removedIndexForKey(KEY(first))).toBe(-1);
  });
});

describe("the follow operations, by key", () => {
  beforeEach(() => resetMockState());
  const follow = FOLLOWS.find((one) => one.kind === "show")!;
  const base = () => `/acquisition/followed/${encoded(KEY(follow))}`;

  it("answers 404 to a key no follow holds, on every operation that names one", () => {
    const unknown = `/acquisition/followed/${encoded("tvdb:0")}`;
    expect(call("PATCH", unknown, { status: "pending" }).status).toBe(404);
    expect(call("DELETE", unknown).status).toBe(404);
    expect(call("POST", `${unknown}/search`).status).toBe(404);
    expect(call("POST", `${unknown}/grab`).status).toBe(404);
    expect(call("PUT", `${unknown}/pause`, { paused: true }).status).toBe(404);
    expect(call("PUT", `${unknown}/quality`, { profile: "1080p" }).status).toBe(404);
    expect(call("GET", `${unknown}/completeness`).status).toBe(404);
    expect(call("POST", `${unknown}/restore`).status).toBe(404);
  });

  it("answers a title as it answers any key nothing holds", () => {
    expect(call("POST", `/acquisition/followed/${encoded(follow.title)}/search`).status).toBe(404);
  });

  it("writes the status the body names, and only one of the contract's enum", () => {
    expect(call("PATCH", base(), { status: "to_grab" }).status).toBe(400);
    expect(call("PATCH", base(), { status: "free text" }).status).toBe(400);
    const done = call("PATCH", base(), { status: "up_to_date" });
    expect(done.status).toBe(200);
    expect(done.payload.status).toBe("up_to_date");
  });

  it("removes a follow by key and puts it back by the same key", () => {
    expect(call("DELETE", base()).status).toBe(200);
    expect(followForKey(KEY(follow))).toBeUndefined();
    expect(removedIndexForKey(KEY(follow))).toBe(0);
    const back = call("POST", `${base()}/restore`);
    expect(back.status).toBe(200);
    expect(back.payload.title).toBe(follow.title);
  });

  it("counts a search against the follow the key names", () => {
    const before = followForKey(KEY(follow))!.searches;
    expect(call("POST", `${base()}/search`).status).toBe(200);
    expect(followForKey(KEY(follow))!.searches).toBe(before + 1);
  });

  it("refuses a grab of a release it does not hold", () => {
    expect(call("POST", `${base()}/grab`, { releaseId: "no such release" }).status).toBe(400);
    expect(call("POST", `${base()}/grab`, {}).status).toBe(200);
  });
});

describe("the releases, by key", () => {
  beforeEach(() => resetMockState());

  it("answers the releases of the medium the key names, each carrying its handle, season and episode", () => {
    const withReleases = FOLLOWS.find((one) => call("GET", "/acquisition/releases", undefined, `followedId=${encoded(KEY(one))}`).payload.length > 0)!;
    const key = KEY(withReleases);
    const all = call("GET", "/acquisition/releases", undefined, `followedId=${encoded(key)}`).payload;
    for (const release of all) {
      expect(typeof release.id).toBe("string");
      expect(release).toHaveProperty("season");
      expect(release).toHaveProperty("episode");
    }
    const every = call("GET", "/acquisition/releases").payload;
    expect(every.length).toBeGreaterThanOrEqual(all.length);
  });

  it("filters on the season and the episode the release itself carries", () => {
    const every = call("GET", "/acquisition/releases").payload as { season: number | null; episode: number | null }[];
    const numbered = every.find((release) => release.season !== null && release.episode !== null)!;
    const asked = call("GET", "/acquisition/releases", undefined, `season=${numbered.season}&episode=${numbered.episode}`).payload as typeof every;
    expect(asked.length).toBeGreaterThan(0);
    for (const release of asked) {
      expect(release.season === null || release.season === numbered.season).toBe(true);
      expect(release.episode === null || release.episode === numbered.episode).toBe(true);
    }
  });

  it("answers nothing for a key that names no medium", () => {
    expect(call("GET", "/acquisition/releases", undefined, `followedId=${encoded("tvdb:0")}`).payload).toEqual([]);
  });
});
