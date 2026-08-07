import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { BottomTabBar } from "@/components/layout/BottomTabBar";
import {
  BOTTOM_BAR_HEIGHT_VAR,
  aboveBottomBar,
} from "@/components/layout/bottom-bar-metrics";

afterEach(() => {
  cleanup();
});

/** Render the bottom tab bar behind the router context its `NavLink`s require. */
function renderBottomBar(initialPath = "/pipeline"): void {
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <BottomTabBar />
    </MemoryRouter>,
  );
}

describe("BottomTabBar", () => {
  it("rend exactement Acquisition · Médias · Pipeline · Contrôle", () => {
    renderBottomBar();

    const nav = screen.getByRole("navigation", {
      name: /navigation principale/i,
    });
    const links = within(nav).getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual([
      "Acquisition",
      "Médias",
      "Pipeline",
      "Contrôle",
    ]);
  });

  it("n'inclut ni la maintenance ni les stubs désactivés", () => {
    renderBottomBar();

    expect(
      screen.queryByRole("link", { name: "Maintenance" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Registre" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Config" }),
    ).not.toBeInTheDocument();
  });

  it("marque l'onglet courant via aria-current et text-primary", () => {
    renderBottomBar("/pipeline");

    const pipeline = screen.getByRole("link", { name: "Pipeline" });
    expect(pipeline).toHaveAttribute("aria-current", "page");
    expect(pipeline.className).toContain("text-primary");
  });
  // §10 — anything that must sit just above the bar reads its measured height
  // from this property. These two tests are what stop it silently reverting to
  // a literal offset, which is the exact defect §10 exists to fix.
  it("publie sa hauteur mesurée sur la racine du document", () => {
    renderBottomBar();
    const published = document.documentElement.style.getPropertyValue(
      BOTTOM_BAR_HEIGHT_VAR,
    );
    // jsdom lays nothing out, so the measured height is 0 — what this pins is
    // that the property is PUBLISHED from a measurement, not that the number is
    // right (only a real device can say that; it is on the staging checklist).
    expect(published).toMatch(/^\d+(\.\d+)?\w+$/);
  });

  it("retire la propriété au démontage — une route sans barre n'hérite pas d'une hauteur", () => {
    renderBottomBar();
    expect(
      document.documentElement.style.getPropertyValue(BOTTOM_BAR_HEIGHT_VAR),
    ).not.toBe("");
    cleanup();
    expect(
      document.documentElement.style.getPropertyValue(BOTTOM_BAR_HEIGHT_VAR),
    ).toBe("");
  });
  // The whole point of §10: this expression must TRACK the bar. A literal is the
  // original defect (`bottom: 84px`, calibrated on desktop, sliding under the
  // bar on iPhone) — so the assertion is on the SHAPE, and any regression to a
  // fixed length fails it.
  it("aboveBottomBar suit la barre et ne retombe jamais sur un littéral", () => {
    const expr = aboveBottomBar("0.75rem");

    expect(expr).toContain(`var(${BOTTOM_BAR_HEIGHT_VAR}`);
    expect(expr).toContain("0.75rem");
    // Le repli est 0px : sur les deux surfaces sans barre (page de connexion,
    // tout écran >= md où la barre est md:hidden), la surface se colle au bas
    // au lieu de flotter dans le vide.
    expect(expr).toMatch(/var\(--tm-bottom-bar-h,\s*0\w+\)/);
    // Pas une longueur fixe déguisée.
    expect(expr).not.toMatch(/^\s*\d+(\.\d+)?\w+\s*$/);
  });
});
