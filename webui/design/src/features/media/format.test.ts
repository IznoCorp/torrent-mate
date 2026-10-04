// How the media sheet writes a date and an episode's state, held on the
// COMMITTED resources.
//
// WHAT MAKES THIS NON-VACUOUS. Every expectation is the literal the engine's own
// copy produced for the same input, so a key missing or mis-aimed fails by
// naming the key i18next returns instead. The date is asserted on the first and
// the last month, so an off-by-one in the month index fails at one end; the
// state words on all six states the legend draws and on one it does not.
import { describe, expect, it } from "vitest";
import "../../lib/unit-words";
import { dateLabel, episodeRanges, episodeStateLabel } from "./format";

describe("dateLabel", () => {
  it("writes the day, the month's short name and the year", () => {
    expect(dateLabel("2026-01-05")).toBe("5 janv. 2026");
    expect(dateLabel("2025-12-31")).toBe("31 déc. 2025"); // french-ok: the engine's own output, asserted
  });

  it("writes nothing when there is no date", () => {
    expect(dateLabel(null)).toBeNull();
    expect(dateLabel("")).toBeNull();
  });
});

describe("episodeStateLabel", () => {
  it("says each of the six episode states", () => {
    expect(
      ["unverified", "announced", "pending", "to_grab", "acquiring", "in_library"].map(episodeStateLabel),
    ).toEqual([
      "Non vérifié", // french-ok: the engine's own output, asserted
      "Annoncé", // french-ok: the engine's own output, asserted
      "En attente de torrent",
      "À récupérer", // french-ok: the engine's own output, asserted
      "En cours d'acquisition",
      "En médiathèque", // french-ok: the engine's own output, asserted
    ]);
  });

  it("says nothing for a state it has no word for", () => {
    expect(episodeStateLabel("lost")).toBe("");
  });
});

describe("episodeRanges", () => {
  it("says the missing episodes by their codes, never as a bare count", () => {
    expect(episodeRanges([7])).toBe("E07");
    expect(episodeRanges([14, 3, 12, 13, 7])).toBe("E03, E07, E12–E14");
    expect(episodeRanges([1, 2])).toBe("E01, E02");
  });
});
