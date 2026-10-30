// What the episode popover says of an episode the catalogue gives no title.
//
// WHAT MAKES THIS NON-VACUOUS. The catalogue is read from the shared cache, so
// the test lands a real sheet there and taps a real `data-ep`; a titled episode
// of the same season proves the same assertion can see a title, and an
// unguarded `" · " + episode.title` would say « S01E03 · null » and fail it.
import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import "../../i18n";
import { installSharedQueryClient } from "../../lib/query-client";
import { episodeSaying } from "./popover-episode";

/**
 * Lands a one-season sheet in the shared cache and taps one of its episodes.
 *
 * @param number The episode's number, as the cell writes it in `data-ep`.
 * @returns What the popover says of it.
 */
function tap(number: number): ReturnType<typeof episodeSaying> {
  const client = new QueryClient();
  client.setQueryData(["/api/v1/media", "sheet"], {
    title: "Some Show",
    ids: { tvdb: 7 },
    episodes: {
      "1": [
        { number: 3, title: null, airDate: "2020-01-05" },
        { number: 4, title: "Pilot", airDate: "2020-01-12" },
      ],
    },
  });
  installSharedQueryClient(client);
  return episodeSaying({ dataset: { ep: `Some Show|1|${number}|in_library` } } as unknown as HTMLElement);
}

describe("episodeSaying", () => {
  it("names an untitled episode by its number alone", () => {
    const saying = tap(3);
    expect(saying?.title).toBe("S01E03");
    expect(saying?.title).not.toContain("·");
    expect(saying?.title).not.toContain("null");
  });

  it("still names a titled episode by its number and its title", () => {
    expect(tap(4)?.title).toBe("S01E04 · Pilot");
  });
});
