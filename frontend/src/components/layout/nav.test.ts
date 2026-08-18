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
      "/acquisition",
      "/media",
      "/pipeline",
      "/control",
    ]);
    expect(byTitle["Système"]).toEqual(["/system"]);
    expect(byTitle.Configuration).toEqual(["/config"]);
  });

  it("Système (S3+) est désormais actif — plus aucun item désactivé", () => {
    const disabled = NAV_ITEMS.filter((item) => item.disabled);
    expect(disabled).toEqual([]);
    // Tous les items sont interactifs — Maintenance et Registre fusionnés dans /system.
    expect(
      NAV_ITEMS.map((item) => item.to),
    ).toEqual(["/acquisition", "/media", "/pipeline", "/control", "/system", "/config"]);
  });

  it("dérive NAV_ITEMS de la projection à plat des sections", () => {
    expect(NAV_ITEMS.map((item) => item.to)).toEqual([
      "/acquisition",
      "/media",
      "/pipeline",
      "/control",
      "/system",
      "/config",
    ]);
  });

  it("réduit la barre d'onglets mobile à Acquisition · Médias · Pipeline · Contrôle", () => {
    expect(BOTTOM_TAB_PATHS).toEqual([
      "/acquisition",
      "/media",
      "/pipeline",
      "/control",
    ]);
    expect(BOTTOM_TAB_ITEMS.map((item) => item.label)).toEqual([
      "Acquisition",
      "Médias",
      "Pipeline",
      "Contrôle",
    ]);
    // Systeme (replacing Maintenance) and the disabled stubs are excluded from
    // the bottom bar; the dashboard (control station, A3) leads it.
    expect(BOTTOM_TAB_ITEMS.some((item) => item.to === "/system")).toBe(false);
    expect(BOTTOM_TAB_ITEMS.some((item) => item.disabled)).toBe(false);
  });
});
