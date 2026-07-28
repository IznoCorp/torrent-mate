/**
 * buildIdFollowBody — the add-by-id → CreateFollowRequest mapping (ACC-05).
 *
 * Each provider must send the right typed field (TVDB/TMDB → int, IMDB → the
 * ``tt…`` string), and a malformed id yields null (button stays disabled).
 */

import { describe, expect, it } from "vitest";

import { buildIdFollowBody } from "./useFollowedPanel";

describe("buildIdFollowBody", () => {
  it("maps TVDB to tvdb_id (int) with kind show", () => {
    expect(buildIdFollowBody("tvdb", "255968")).toEqual({
      tvdb_id: 255968,
      kind: "show",
    });
  });

  it("maps TMDB to tmdb_id (int) with kind show", () => {
    expect(buildIdFollowBody("tmdb", "1399")).toEqual({
      tmdb_id: 1399,
      kind: "show",
    });
  });

  it("maps IMDB to imdb_id (string) with kind show", () => {
    expect(buildIdFollowBody("imdb", "tt0903747")).toEqual({
      imdb_id: "tt0903747",
      kind: "show",
    });
  });

  it("trims whitespace before mapping", () => {
    expect(buildIdFollowBody("imdb", "  tt0903747  ")).toEqual({
      imdb_id: "tt0903747",
      kind: "show",
    });
  });

  it("rejects an empty id (null)", () => {
    expect(buildIdFollowBody("tvdb", "")).toBeNull();
    expect(buildIdFollowBody("imdb", "   ")).toBeNull();
  });

  it("rejects a malformed IMDB id (must be tt<digits>)", () => {
    expect(buildIdFollowBody("imdb", "0903747")).toBeNull();
    expect(buildIdFollowBody("imdb", "tt")).toBeNull();
    expect(buildIdFollowBody("imdb", "ttabc")).toBeNull();
    expect(buildIdFollowBody("imdb", "nm0000123")).toBeNull();
  });

  it("rejects a non-integer / non-positive TVDB or TMDB id", () => {
    expect(buildIdFollowBody("tvdb", "12.5")).toBeNull();
    expect(buildIdFollowBody("tmdb", "0")).toBeNull();
    expect(buildIdFollowBody("tvdb", "-5")).toBeNull();
    expect(buildIdFollowBody("tmdb", "abc")).toBeNull();
    // An IMDB-shaped value under a numeric provider is not a number → null.
    expect(buildIdFollowBody("tvdb", "tt0903747")).toBeNull();
  });
});
