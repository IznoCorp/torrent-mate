import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

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
function files(racine: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(racine)) {
    const path = join(racine, entry);
    if (statSync(path).isDirectory()) {
      out.push(...files(path));
    } else if (path.endsWith(".tsx")) {
      out.push(path);
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
    for (const cssClass of SURFACE.split(" ")) {
      expect(el.className).toContain(cssClass);
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
    // Resolved from THIS file, not from the process cwd: reading "src"
    // relatively made the test pass only when the runner happened to be
    // started inside `frontend/`, and blow up with ENOENT anywhere else.
    const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../..", "src");
    // The absolute path is what gets READ; the `src/…` form is only the key the
    // exception list is written in. Using one for both put a relative path back
    // into `readFileSync`, which is the very cwd dependency this resolves.
    const offenders = files(root)
      .filter((absolute) => !EXCEPTIONS.has(absolute.slice(root.length - "src".length)))
      .filter((absolute) => readFileSync(absolute, "utf8").includes(SURFACE))
      .map((absolute) => absolute.slice(root.length - "src".length));
    expect(offenders).toEqual([]);
  });
});
