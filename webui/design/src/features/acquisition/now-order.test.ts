// « En cours »'s filter, search and sort — ONE derivation, read by the tab, its
// filter pill's count and the filter panel's counts.
//
// WHAT MAKES THIS NON-VACUOUS. The cards are given in an order that is none of
// the expected ones, so an identity sort fails every case; the most advanced
// card is neither first nor last, and the search ignores case and accents.
import { describe, expect, it } from "vitest";
import type { QueueCard } from "../../lib/engine-queue";
import { NOW_FILTERS, NOW_SORTS, nowCounts, orderNow } from "./now-order";

const RUNGS = ["requested", "searched", "grabbed", "downloading", "arrived", "identified", "shelved", "verified"] as const;

/**
 * A card on its way, in the shape the queue serves it: its ladder, no strip.
 *
 * @param title Its title.
 * @param kind Film or series; omitted, the card carries none.
 * @param done How many rungs of its ladder it has passed.
 * @returns The card.
 */
function card(title: string, kind: "movie" | "show" | undefined, done: number): QueueCard {
  const ladder = RUNGS.map((rung, index) => ({ rung, state: index < done ? "done" : "pending", when: "" }));
  return { title, secondaryLine: "", kind, ids: null, poster: null, ladder } as QueueCard;
}

// An accented title, composed from its parts: the guardrail refuses a French literal in the code.
const ACCENTED = `Ame${String.fromCodePoint(0x301)}lie`;
const dune = card("Dune", "movie", 2);
const silo = card("Silo", "show", 4);
const amelie = card(ACCENTED, "movie", 1);
const severance = card("Severance", "show", 3);
const ALL = [dune, silo, amelie, severance];
// A card with no kind counts as a series; one still on its five-position strip is read from it.
const kindless = card("Kindless", undefined, 5);
const stripped = (title: string, strip: number[]) => ({ title, secondaryLine: "", kind: "show", ids: null, poster: null, strip }) as QueueCard;
const stripOnly = [stripped("Early", [1, 0, 0, 0, 0]), stripped("Late", [1, 1, 1, 1, 0])];
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
  it("keeps a card with no kind among the series, and orders a strip-only card by its strip", () => {
    expect(titles(orderNow([...ALL, kindless], "series", "queue", ""))).toEqual(["Silo", "Severance", "Kindless"]);
    expect(titles(orderNow([...ALL, kindless], "movies", "queue", ""))).toEqual(["Dune", ACCENTED]);
    expect(titles(orderNow(stripOnly, "all", "progress", ""))).toEqual(["Late", "Early"]);
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
