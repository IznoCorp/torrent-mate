// Invariant 7 of `docs/reference/frontend-architecture.md`: two features never
// import each other — they compose in the route, and what two of them share
// lives in `lib/` or `ui/`.
//
// WHY A TEST: the acquisition card read its sizes from the Trackers feature
// (`../trackers/format`), and nothing caught it before the lot's reading did
// (M2 of maquette-blocked).
import { describe, expect, it } from "vitest";

// Every feature module, as its source text.
const SOURCES = import.meta.glob<string>(["./*/**/*.ts", "./*/**/*.tsx", "!./**/*.test.ts", "!./**/*.test.tsx"], {
  query: "?raw",
  import: "default",
  eager: true,
});

// An import that climbs ONE level out of a feature into another one.
const SIBLING_IMPORT = /from\s+"\.\.\/([a-z-]+)\//g;

// Grandfathered until its surface's wave converts it — never extended.
const GRANDFATHERED = new Set(["./media/media-screen.tsx -> acquisition"]);

describe("features never import each other (invariant 7)", () => {
  it("no feature module imports another feature's", () => {
    const crossings: string[] = [];
    for (const [path, source] of Object.entries(SOURCES)) {
      const own = path.split("/")[1];
      for (const match of source.matchAll(SIBLING_IMPORT)) {
        const crossing = `${path} -> ${match[1]}`;
        if (match[1] !== own && !GRANDFATHERED.has(crossing)) crossings.push(crossing);
      }
    }
    expect(crossings).toEqual([]);
  });
});
