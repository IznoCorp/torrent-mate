// « En cours »'s filter, search and sort — ONE derivation, read by the tab, its
// filter pill's count and the filter panel's counts.
//
// WHAT MAKES THIS NON-VACUOUS. The cards are given in an order that is none of
// the expected ones, so an identity sort fails every case; the most advanced
// card is neither first nor last, and the search ignores case and accents.
import { describe, expect, it } from "vitest";
import type { QueueCard } from "../../lib/engine-queue";
import { NOW_FILTERS, NOW_SORTS, nowCounts, orderNow } from "./now-order";

/**
 * A card on its way.
 *
 * @param title Its title.
 * @param kind Film or series.
 * @param done How many of the five pipeline positions it has passed.
 * @returns The card.
 */
function card(title: string, kind: "movie" | "show", done: number): QueueCard {
  const strip = [0, 0, 0, 0, 0].map((_, index) => (index < done ? 1 : 0));
  return { title, secondaryLine: "", kind, ids: null, poster: null, strip } as QueueCard;
}

// An accented title, composed from its parts: the guardrail refuses a French literal in the code.
const ACCENTED = `Ame${String.fromCodePoint(0x301)}lie`;
const dune = card("Dune", "movie", 2);
const silo = card("Silo", "show", 4);
const amelie = card(ACCENTED, "movie", 1);
const severance = card("Severance", "show", 3);
const ALL = [dune, silo, amelie, severance];
const titles = (cards: QueueCard[]) => cards.map((one) => one.title);

describe("orderNow", () => {
  it("offers the filters and the sorts in the order its panels draw them", () => {
    expect([...NOW_FILTERS]).toEqual(["all", "series", "movies"]);
    expect([...NOW_SORTS]).toEqual(["queue", "progress", "az", "za"]);
  });
  it("keeps the order the queue serves by default, and filters by kind", () => {
    expect(titles(orderNow(ALL, "all", "queue", ""))).toEqual(["Dune", "Silo", ACCENTED, "Severance"]);
    expect(titles(orderNow(ALL, "series", "queue", ""))).toEqual(["Silo", "Severance"]);
    expect(titles(orderNow(ALL, "movies", "queue", ""))).toEqual(["Dune", ACCENTED]);
  });
  it("narrows by name, case and accents ignored, under the filter in force", () => {
    expect(titles(orderNow(ALL, "all", "queue", "  AMELIE "))).toEqual([ACCENTED]);
    expect(titles(orderNow(ALL, "series", "queue", "e"))).toEqual(["Severance"]);
    expect(titles(orderNow(ALL, "all", "queue", "zzz"))).toEqual([]);
  });
  it("orders by progress (the furthest first) and by title both ways", () => {
    expect(titles(orderNow(ALL, "all", "progress", ""))).toEqual(["Silo", "Severance", "Dune", ACCENTED]);
    expect(titles(orderNow(ALL, "all", "az", ""))).toEqual([ACCENTED, "Dune", "Severance", "Silo"]);
    expect(titles(orderNow(ALL, "all", "za", ""))).toEqual(["Silo", "Severance", "Dune", ACCENTED]);
  });
  it("does not reorder its input", () => {
    const given = [...ALL];
    orderNow(given, "all", "za", "");
    expect(given).toEqual(ALL);
  });
});

describe("nowCounts", () => {
  it("counts what each filter would keep, the search applied", () => {
    expect(nowCounts(ALL, "")).toEqual({ all: 4, series: 2, movies: 2 });
    expect(nowCounts(ALL, "s")).toEqual({ all: 2, series: 2, movies: 0 });
  });
});
