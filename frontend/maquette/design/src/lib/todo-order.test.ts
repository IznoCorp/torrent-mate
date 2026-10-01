// « À traiter »'s order and filter (DECIDED 1): urgency groups, newest first
// inside each, a card with no time last; the filter by cause; the counts.
//
// WHAT MAKES THIS NON-VACUOUS. The cards are given in an order that is none of
// the expected ones, so an identity sort fails every case; the groups and the
// times disagree on purpose (the newest card is a closure, last by urgency).
import { describe, expect, it } from "vitest";
import type { QueueCard } from "./engine-queue";
import { causeOf, orderTodo, todoCounts } from "./todo-order";

/**
 * A card stopped on one rung.
 *
 * @param title Its title.
 * @param rung What its stopped rung carries.
 * @param extra Other fields of the card.
 * @returns The card.
 */
function card(title: string, rung: Record<string, unknown>, extra: Partial<QueueCard> = {}): QueueCard {
  return {
    title, secondaryLine: "", kind: "show", ids: null, poster: null,
    ladder: [{ rung: "arrived", when: "", ...rung }] as QueueCard["ladder"],
    ...extra,
  } as QueueCard;
}

const resolve = card("Lucky", { state: "blocked" });
const step = card("Furious", { state: "blocked", blockedSince: 300 }, { failedStep: "scrape" });
const disk = card("Silo", { state: "waiting", resumes: "auto", reason: "insufficient_space", blockedSince: 200 });
const ratio = card("Dune", { state: "waiting", resumes: "auto", reason: "ratio_below_threshold", blockedSince: 400 });
const closed = card("Alien", { state: "done" }, { closure: { reason: "torrent_removed", at: 900, winner: null } });
const ALL = [closed, disk, resolve, ratio, step];
const titles = (cards: QueueCard[]) => cards.map((one) => one.title);

describe("orderTodo", () => {
  it("orders by urgency: judgement, then external, then closures — newest first, no time last", () => {
    expect(titles(orderTodo(ALL, "all", "urgency"))).toEqual(["Furious", "Lucky", "Dune", "Silo", "Alien"]);
  });
  it("orders by time alone, both ways, a card with no time last", () => {
    expect(titles(orderTodo(ALL, "all", "newest"))).toEqual(["Alien", "Dune", "Furious", "Silo", "Lucky"]);
    expect(titles(orderTodo(ALL, "all", "oldest"))).toEqual(["Silo", "Furious", "Dune", "Alien", "Lucky"]);
  });
  it("keeps one cause", () => {
    expect(titles(orderTodo(ALL, "disks", "urgency"))).toEqual(["Silo"]);
    expect(titles(orderTodo(ALL, "closed", "urgency"))).toEqual(["Alien"]);
  });
});

describe("causeOf and todoCounts", () => {
  it("names a waiting rung the engine does not resume as no external cause", () => {
    expect(causeOf(card("Queued", { state: "waiting", reason: "insufficient_space" }))).toBe("resolve");
  });
  it("counts every cause, and the whole", () => {
    expect(todoCounts(ALL)).toEqual({ all: 5, resolve: 1, plex: 0, step: 1, disks: 1, ratio: 1, unreachable: 0, closed: 1 });
  });
});
