// The follow vocabulary, held on the COMMITTED resources — the words the page
// reads — and on the shapes the engine's own copies answered before they moved.
//
// WHAT MAKES THIS NON-VACUOUS. Every word and sentence is the literal the
// engine's own copy produced for the same input, so a key missing or mis-aimed
// fails by naming the key i18next returns instead; each function is asserted on every branch
// it has (a film and a series, a readable cron and one that is not, a slot
// later today and one that wraps to tomorrow).
import { describe, expect, it } from "vitest";
import "../../lib/unit-words";
import {
  STATUS_TONE,
  URGENCY,
  cadenceSentence,
  followFraction,
  followGroups,
  followStatusLabel,
  gridBadge,
  nextSearchTime,
} from "./follow-vocabulary";
import type { Follow } from "./types";

const series = (status: string, extra: Partial<Follow> = {}): Follow => ({
  t: "Silo",
  k: "show",
  y: 2023,
  st: status,
  ...extra,
});
const film = (status: string): Follow => ({ t: "Dune", k: "movie", y: 2021, st: status });

describe("followStatusLabel", () => {
  it("says a series' status with the series word", () => {
    expect(followStatusLabel(series("up_to_date"))).toBe("À jour"); // french-ok: the engine's own output, asserted
    expect(followStatusLabel(series("pending"))).toBe("En attente de torrent");
  });

  it("says a film's three own statuses with the film word, and the rest with the series word", () => {
    expect(followStatusLabel(film("up_to_date"))).toBe("Acquis");
    expect(followStatusLabel(film("ended"))).toBe("Acquis");
    expect(followStatusLabel(film("disabled"))).toBe("Recherche arrêtée"); // french-ok: the engine's own output, asserted
    expect(followStatusLabel(film("to_grab"))).toBe("À récupérer"); // french-ok: the engine's own output, asserted
  });

  it("has a word, a tone and an urgency for each of the eight statuses", () => {
    const statuses = Object.keys(URGENCY);
    expect(statuses).toHaveLength(8);
    for (const status of statuses) {
      expect(followStatusLabel(series(status))).not.toContain("screens.");
      expect(STATUS_TONE[status]).toBeTruthy();
    }
  });
});

describe("followFraction and gridBadge", () => {
  it("gives a film no fraction and a series its held/aired, or « — » with no catalogue", () => {
    expect(followFraction(film("pending"))).toBeNull();
    expect(followFraction(series("pending", { aired: 7, own: 6 }))).toBe("6/7");
    expect(followFraction(series("pending"))).toBe("—");
  });

  it("badges what is actionable, marks what has no verdict, and says nothing otherwise", () => {
    expect(gridBadge(film("pending"))).toEqual({ txt: "•", tone: "pending" });
    expect(gridBadge(series("to_grab", { aired: 10, own: 7 }))).toEqual({ txt: "3", tone: "to_grab" });
    expect(gridBadge(series("acquiring", { aired: 5, own: 5 }))).toEqual({ txt: "1", tone: "acquiring" });
    expect(gridBadge(series("verifying"))).toEqual({ txt: "?", tone: "muted" });
    expect(gridBadge(series("up_to_date"))).toBeNull();
  });
});

describe("followGroups", () => {
  it("lists the five groups in order, every status in exactly one", () => {
    const groups = followGroups();
    expect(groups.map((group) => group.label)).toEqual([
      "Demandent quelque chose",
      "En cours",
      "À jour", // french-ok: the engine's own output, asserted
      "Terminées", // french-ok: the engine's own output, asserted
      "En pause",
    ]);
    expect(groups.flatMap((group) => group.statuses).sort()).toEqual(Object.keys(URGENCY).sort());
  });
});

describe("cadenceSentence and nextSearchTime", () => {
  it("says a readable schedule as a sentence", () => {
    expect(cadenceSentence("20 3,15 * * *")).toBe(
      "Recherche automatique : 2 fois par jour, à 3 h 20 et 15 h 20", // french-ok: the engine's own output, asserted
    );
    expect(cadenceSentence("5 4 * * *")).toBe("Recherche automatique : une fois par jour, à 4 h 05"); // french-ok: the engine's own output, asserted
    expect(cadenceSentence("0 1,2,3 * * *")).toBe(
      "Recherche automatique : 3 fois par jour, à 1 h 00, 2 h 00 et 3 h 00", // french-ok: the engine's own output, asserted
    );
  });

  it("says an unreadable schedule raw, escaped, and says it could not read it", () => {
    expect(cadenceSentence("*/5 <x> * * 1")).toBe(
      "Recherche automatique : */5 &lt;x&gt; * * 1 (cadence non interprétée)", // french-ok: the engine's own output, asserted
    );
    expect(nextSearchTime("*/5 * * * 1", new Date(2026, 7, 10, 12, 0))).toBeNull();
  });

  it("names the next slot today, and tomorrow's first once today's have passed", () => {
    expect(nextSearchTime("20 3,15 * * *", new Date(2026, 7, 10, 12, 0))).toBe("15 h 20");
    expect(nextSearchTime("20 3,15 * * *", new Date(2026, 7, 10, 15, 20))).toBe("3 h 20");
    expect(nextSearchTime("20 3,15 * * *", new Date(2026, 7, 10, 15, 19))).toBe("15 h 20");
  });
});
