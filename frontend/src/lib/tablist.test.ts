/**
 * lib/tablist — WAI-ARIA tablist keyboard contract (ACQUISITION-7, ticket 250).
 *
 * Unit tests for the shared arrow-key handler: next/previous with wrap-around,
 * Home/End jumps, focus move onto the newly-active tab, and inert non-arrow
 * keys.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { handleTablistKeyDown } from "@/lib/tablist";

type Key = "ArrowRight" | "ArrowLeft" | "Home" | "End" | "Enter";

const IDS = ["a", "b", "c"] as const;

/** Build a minimal React-like keyboard event for the handler. */
function makeEvent(key: Key): {
  key: string;
  preventDefault: ReturnType<typeof vi.fn>;
} {
  return { key, preventDefault: vi.fn() };
}

/** Mount focusable buttons with the ids the handler focuses. */
function mountButtons(): void {
  document.body.innerHTML = IDS.map(
    (id) => `<button id="tab-${id}">${id}</button>`,
  ).join("");
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("handleTablistKeyDown", () => {
  it("ArrowRight active l'onglet suivant et le focus", () => {
    mountButtons();
    const activate = vi.fn();
    const event = makeEvent("ArrowRight");
    handleTablistKeyDown(
      event as unknown as Parameters<typeof handleTablistKeyDown>[0],
      IDS,
      "a",
      activate,
      (id) => `tab-${id}`,
    );
    expect(activate).toHaveBeenCalledWith("b");
    expect(event.preventDefault).toHaveBeenCalled();
    expect(document.activeElement?.id).toBe("tab-b");
  });

  it("ArrowRight depuis le dernier onglet boucle sur le premier", () => {
    mountButtons();
    const activate = vi.fn();
    handleTablistKeyDown(
      makeEvent("ArrowRight") as unknown as Parameters<
        typeof handleTablistKeyDown
      >[0],
      IDS,
      "c",
      activate,
      (id) => `tab-${id}`,
    );
    expect(activate).toHaveBeenCalledWith("a");
  });

  it("ArrowLeft depuis le premier onglet boucle sur le dernier", () => {
    mountButtons();
    const activate = vi.fn();
    handleTablistKeyDown(
      makeEvent("ArrowLeft") as unknown as Parameters<
        typeof handleTablistKeyDown
      >[0],
      IDS,
      "a",
      activate,
      (id) => `tab-${id}`,
    );
    expect(activate).toHaveBeenCalledWith("c");
  });

  it("Home et End sautent aux extrêmes", () => {
    mountButtons();
    const activate = vi.fn();
    handleTablistKeyDown(
      makeEvent("End") as unknown as Parameters<typeof handleTablistKeyDown>[0],
      IDS,
      "a",
      activate,
      (id) => `tab-${id}`,
    );
    expect(activate).toHaveBeenLastCalledWith("c");
    handleTablistKeyDown(
      makeEvent("Home") as unknown as Parameters<
        typeof handleTablistKeyDown
      >[0],
      IDS,
      "c",
      activate,
      (id) => `tab-${id}`,
    );
    expect(activate).toHaveBeenLastCalledWith("a");
  });

  it("ignore les touches hors contrat (pas de preventDefault, pas d'activation)", () => {
    mountButtons();
    const activate = vi.fn();
    const event = makeEvent("Enter");
    handleTablistKeyDown(
      event as unknown as Parameters<typeof handleTablistKeyDown>[0],
      IDS,
      "a",
      activate,
      (id) => `tab-${id}`,
    );
    expect(activate).not.toHaveBeenCalled();
    expect(event.preventDefault).not.toHaveBeenCalled();
  });
});
