// The season a release covers is the one the release carries, not the one its name says.
import { describe, expect, it } from "vitest";
import { episodeSeason } from "./season";

describe("episodeSeason", () => {
  it("reads the season of an episode from its fields, whatever its name says", () => {
    expect(episodeSeason({ season: 3, episode: 7 })).toBe(3);
  });

  it("answers null for a season pack, even when its name looks like an episode", () => {
    expect(episodeSeason({ season: 3, episode: null })).toBeNull();
  });

  it("answers null for a film", () => {
    expect(episodeSeason({ season: null, episode: null })).toBeNull();
  });
});
