import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Panel } from "./Panel";

/** The surface string this component owns. */
const SURFACE = "rounded-lg border border-border bg-card";

/**
 * A banner is not a panel. It floats over the interface with its own shadow and
 * its own width, and it is the only surface that legitimately repeats the
 * string — the audit says so and this test says where.
 */
const EXCEPTIONS = new Set([
  "src/components/InstallBanner.tsx",
  "src/components/ds/Panel.tsx",
  // This file, which has to name the string in order to look for it.
  "src/components/ds/Panel.test.tsx",
]);

/** Every `.tsx` under a directory, repo-relative. */
function fichiers(racine: string): string[] {
  const out: string[] = [];
  for (const entree of readdirSync(racine)) {
    const chemin = join(racine, entree);
    if (statSync(chemin).isDirectory()) {
      out.push(...fichiers(chemin));
    } else if (chemin.endsWith(".tsx")) {
      out.push(chemin);
    }
  }
  return out;
}

describe("Panel", () => {
  afterEach(cleanup);

  it("porte la surface, et laisse au bloc ce qu'il contient", () => {
    render(
      <Panel className="p-4" data-testid="p">
        du contenu
      </Panel>,
    );
    const el = screen.getByTestId("p");
    for (const classe of SURFACE.split(" ")) {
      expect(el.className).toContain(classe);
    }
    expect(el.className).toContain("p-4");
    expect(el.tagName).toBe("DIV");
  });

  it("se rend en l'élément demandé", () => {
    render(
      <Panel as="section" aria-label="Bloc" data-testid="p">
        du contenu
      </Panel>,
    );
    expect(screen.getByTestId("p").tagName).toBe("SECTION");
  });

  it("est le SEUL endroit qui écrit la surface", () => {
    // A surface has no content of its own to be recognised by, so a copy that
    // drifts by one token is invisible until it sits next to the original.
    const coupables = fichiers("src")
      .filter((f) => !EXCEPTIONS.has(f))
      .filter((f) => readFileSync(f, "utf8").includes(SURFACE));
    expect(coupables).toEqual([]);
  });
});
