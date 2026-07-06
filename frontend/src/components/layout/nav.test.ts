import { describe, expect, it } from "vitest";

import {
  BOTTOM_TAB_ITEMS,
  BOTTOM_TAB_PATHS,
  NAV_ITEMS,
  NAV_SECTIONS,
} from "@/components/layout/nav";

describe("nav model", () => {
  it("groupe les sections dans l'ordre Supervision / Système / Configuration", () => {
    expect(NAV_SECTIONS.map((section) => section.title)).toEqual([
      "Supervision",
      "Système",
      "Configuration",
    ]);
  });

  it("liste les destinations de chaque section dans l'ordre attendu", () => {
    const byTitle = Object.fromEntries(
      NAV_SECTIONS.map((section) => [
        section.title,
        section.items.map((item) => item.to),
      ]),
    );

    expect(byTitle.Supervision).toEqual([
      "/",
      "/pipeline",
      "/scraping",
      "/acquisition",
    ]);
    expect(byTitle["Système"]).toEqual(["/maintenance"]);
    expect(byTitle.Configuration).toEqual(["/registry", "/config"]);
  });

  it("marque Registre (S6) et Config (S4) comme désactivés avec leur tag de vague", () => {
    const disabled = NAV_ITEMS.filter((item) => item.disabled);
    expect(disabled.map((item) => [item.to, item.wave])).toEqual([
      ["/registry", "S6"],
      ["/config", "S4"],
    ]);
    // Every other entry stays interactive.
    expect(
      NAV_ITEMS.filter((item) => item.disabled !== true).map((item) => item.to),
    ).toEqual(["/", "/pipeline", "/scraping", "/acquisition", "/maintenance"]);
  });

  it("dérive NAV_ITEMS de la projection à plat des sections", () => {
    expect(NAV_ITEMS.map((item) => item.to)).toEqual([
      "/",
      "/pipeline",
      "/scraping",
      "/acquisition",
      "/maintenance",
      "/registry",
      "/config",
    ]);
  });

  it("réduit la barre d'onglets mobile à Pipeline · Scraping · Acquisition · Maintenance", () => {
    expect(BOTTOM_TAB_PATHS).toEqual([
      "/pipeline",
      "/scraping",
      "/acquisition",
      "/maintenance",
    ]);
    expect(BOTTOM_TAB_ITEMS.map((item) => item.label)).toEqual([
      "Pipeline",
      "Scraping",
      "Acquisition",
      "Maintenance",
    ]);
    // The dashboard and the disabled stubs are excluded from the bottom bar.
    expect(BOTTOM_TAB_ITEMS.some((item) => item.to === "/")).toBe(false);
    expect(BOTTOM_TAB_ITEMS.some((item) => item.disabled)).toBe(false);
  });
});
