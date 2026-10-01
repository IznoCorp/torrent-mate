// Where a card set aside lands: « Mis de côté » alone, whichever list of the
// queue's answer holds it (m3 of maquette-blocked's reading).
//
// WHAT MAKES THIS NON-VACUOUS. The row set aside is served IN FLIGHT, the list
// `todoCards` reads and `setAsideCards` did not: it fell into « En cours »,
// drawn as moving, and into no « Mis de côté ».
import { describe, expect, it } from "vitest";
import type { QueueCard } from "./engine-queue";
import { inFlightCards, setAsideCards, todoCards } from "./arrival-slots";

/**
 * A card on one rung.
 *
 * @param title Its title.
 * @param state The rung's state.
 * @returns The card.
 */
function card(title: string, state: string): QueueCard {
  return {
    title, secondaryLine: "", kind: "show", ids: null, poster: null,
    ladder: [{ rung: "downloading", when: "", state }] as QueueCard["ladder"],
  } as QueueCard;
}

describe("a card set aside in flight", () => {
  it("lands in « Mis de côté » and in no other list", () => {
    const aside = card("Silo", "aside");
    const queue = { blocked: [], arrivals: [], inFlight: [aside, card("Dune", "now")] };
    const lists = { now: inFlightCards(queue), todo: todoCards(queue), setAside: setAsideCards(queue) };
    expect(Object.entries(lists).filter(([, cards]) => cards.includes(aside)).map(([name]) => name))
      .toEqual(["setAside"]);
  });
});
