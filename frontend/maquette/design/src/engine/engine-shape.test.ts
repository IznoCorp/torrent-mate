// The inverse projection, tested against the seeds it will really be given.
//
// WHAT MAKES THIS NON-VACUOUS. The inputs are the COMMITTED SEEDS — extracted
// from `legacy.js` by a declared projection and held byte for byte against it by
// `scripts/check-mock-seeds.py --arm correspondence`. So this asserts against
// the engine's own data, one artefact removed, rather than against something
// this file made up.
//
// THE PROPERTY IS THE POINT, and it is the failure mode the adapter can have
// without anything looking wrong: a declared path that walks nothing. The
// conversion would silently do less, contract names would reach the engine's
// markup, and the markup renders either way — it would just render the wrong
// words. So the test asks the DECLARATION what names must not survive, rather
// than listing them here where they would rot.
//
// WHAT IT DOES NOT READ: whether the engine's producers like the result. That
// is the oracle's, and it is the stronger check of the two — a wrong conversion
// moves a rectangle. This one runs in a runner, so it says WHICH field went
// wrong instead of which region did.
import { describe, expect, it } from "vitest";
import projections from "../../../fixture-projections.json";
import { toEngineShape, toEngineShapeEntry } from "./engine-shape";
import PIPELINE from "../mocks/seeds/pipeline.json";
import PENDING_DECISIONS from "../mocks/seeds/pending-decisions.json";
import SETTLED_DECISIONS from "../mocks/seeds/settled-decisions.json";
import STUCK from "../mocks/seeds/stuck.json";
import MEDIA_SHEETS from "../mocks/seeds/media-sheets.json";
import SUGGESTIONS from "../mocks/seeds/suggestions.json";

type Renames = Record<string, string>;
type Projection = { rename?: Record<string, Renames>; tuples?: Record<string, string[]>;
                    $card?: boolean; $fact?: boolean };

const FAMILIES = projections.families as unknown as Record<string, Projection>;
const SHORTHANDS = projections.$shorthands as unknown as Record<string, Projection>;

/** Every contract name the declaration introduces for one family. */
function contractNames(family: string): string[] {
  const declared = FAMILIES[family];
  const expanded = declared.$card ? { ...SHORTHANDS.$card, ...declared }
    : declared.$fact ? { ...SHORTHANDS.$fact, ...declared }
    : declared;
  return Object.values(expanded.rename ?? {}).flatMap((level) => Object.values(level));
}

/** Every key present anywhere in a value, however deep. */
function keysAnywhere(value: unknown, seen: Set<string> = new Set()): Set<string> {
  if (Array.isArray(value)) {
    value.forEach((entry) => keysAnywhere(entry, seen));
    return seen;
  }
  if (value !== null && typeof value === "object") {
    for (const [key, held] of Object.entries(value)) {
      seen.add(key);
      keysAnywhere(held, seen);
    }
  }
  return seen;
}

const CASES: [string, unknown][] = [
  ["PIPELINE", PIPELINE],
  ["PENDING_DECISIONS", PENDING_DECISIONS],
  ["DECISIONS_REGLEES", SETTLED_DECISIONS],
  ["STUCK_REAL", STUCK],
];

describe("toEngineShape", () => {
  it.each(CASES)("leaves no contract-only name behind in %s", (family, seed) => {
    const converted = toEngineShape(family, seed);
    const left = keysAnywhere(converted);
    // A name the declaration introduced must be GONE, unless the engine
    // happened to use the same word for something else at another level — the
    // declaration is what says which, so the intersection is computed from it
    // rather than listed here.
    const engineNames = new Set(
      Object.values(
        (FAMILIES[family].$card
          ? { ...SHORTHANDS.$card, ...FAMILIES[family] }
          : FAMILIES[family]).rename ?? {},
      ).flatMap((level) => Object.keys(level)),
    );
    const survivors = contractNames(family).filter(
      (name) => left.has(name) && !engineNames.has(name),
    );
    expect(survivors).toEqual([]);
  });

  it.each(CASES)("brings back the engine's own names in %s", (family, seed) => {
    const converted = toEngineShape(family, seed);
    const left = keysAnywhere(converted);
    const engineNames = Object.values(
      (FAMILIES[family].$card
        ? { ...SHORTHANDS.$card, ...FAMILIES[family] }
        : FAMILIES[family]).rename ?? {},
    ).flatMap((level) => Object.keys(level));
    // AND THE CORPUS IS ASSERTED, because « no survivor » is what an adapter
    // that returned an empty object would also report.
    expect(engineNames.length).toBeGreaterThan(0);
    const restored = engineNames.filter((name) => left.has(name));
    expect(restored.length).toBeGreaterThan(0);
  });

  it("restores a nested list the declaration names two levels down", () => {
    // `PENDING_DECISIONS` renames `c` → `candidates` at the root and then names
    // the path `[]/c[]` for the candidates themselves. A converter that renamed
    // the root and never descended would leave `title` inside each candidate,
    // and the card would draw an empty name.
    const converted = toEngineShape<Record<string, unknown>[]>(
      "PENDING_DECISIONS", PENDING_DECISIONS);
    const candidates = converted.find(
      (decision) => Array.isArray(decision.c) && (decision.c as unknown[]).length > 0);
    expect(candidates).toBeDefined();
    const first = (candidates!.c as Record<string, unknown>[])[0];
    expect(first).toHaveProperty("t");
    expect(first).toHaveProperty("p");
    expect(first).not.toHaveProperty("title");
    expect(first).not.toHaveProperty("provider");
  });

  it("restores the pipeline's own two-level paths", () => {
    const converted = toEngineShape<Record<string, unknown>>("PIPELINE", PIPELINE);
    expect(converted).toHaveProperty("declencheurs");
    const steps = converted.steps as Record<string, unknown>[];
    expect(steps[0]).toHaveProperty("n");
    expect(steps[0]).toHaveProperty("l");
    const last = converted.last as Record<string, unknown>;
    expect(last).toHaveProperty("duree");
    expect(last).toHaveProperty("declencheur");
    const facts = last.facts as Record<string, unknown>[];
    expect(facts[0]).toHaveProperty("n");
  });

  it("carries a field the declaration does not name, verbatim", () => {
    // `strip` is neither renamed nor tupled; the projection carried it across
    // and so must the inverse.
    const converted = toEngineShape<Record<string, unknown>[]>("STUCK_REAL", STUCK);
    expect(converted[0].strip).toEqual((STUCK as Record<string, unknown>[])[0].strip);
  });

  it("leaves a plain string inside a mixed array alone", () => {
    // A suggestion's `why` is « Recoupé par », then `{emphasis: "4"}`, then
    // « titres de votre médiathèque ». Renaming a STRING's keys turns it into
    // an object of its own characters, and the engine rendered the result as
    // `undefined` in bold — caught on screen by R11 before this test existed.
    const converted = toEngineShape<Record<string, unknown>[]>(
      "SUGGESTIONS", SUGGESTIONS);
    const why = converted[0].why as unknown[];
    expect(typeof why[0]).toBe("string");
    expect(why[0]).toBe((SUGGESTIONS as { why: unknown[] }[])[0].why[0]);
    expect(why[1]).toHaveProperty("e");
    expect(why[1]).not.toHaveProperty("emphasis");
  });

  it("walks `*[]`, which is every key of an object and then every element", () => {
    // `SHEETS_RAW` declares `/eps/*[]` — for each season number, for each
    // episode. A walker matching only the bare `*` fell through to the field
    // lookup, found no field called `*`, and left every episode wearing the
    // contract's names; the engine drew blank rows and the oracle saw ten
    // pixels.
    const sheets = MEDIA_SHEETS as Record<string, Record<string, unknown>>;
    const withEpisodes = Object.values(sheets).find(
      (sheet) => sheet.episodes !== undefined);
    expect(withEpisodes).toBeDefined();
    const converted = toEngineShapeEntry<Record<string, unknown>>(
      "SHEETS_RAW", withEpisodes!);
    const episodes = converted.eps as Record<string, Record<string, unknown>[]>;
    const first = Object.values(episodes)[0][0];
    expect(first).toHaveProperty("n");
    expect(first).toHaveProperty("t");
    expect(first).not.toHaveProperty("number");
    expect(first).not.toHaveProperty("airDate");
  });

  it("converts ONE ENTRY of a family the projection keys by data", () => {
    // `SHEETS_RAW` is a map keyed by title, and the layer serves one sheet at
    // an address. Its declared paths describe one VALUE of that map.
    const sheets = MEDIA_SHEETS as Record<string, Record<string, unknown>>;
    const one = Object.values(sheets)[0];
    const converted = toEngineShapeEntry<Record<string, unknown>>("SHEETS_RAW", one);
    expect(converted).toHaveProperty("k");
    expect(converted).toHaveProperty("ov");
    expect(converted).not.toHaveProperty("kind");
    expect(converted).not.toHaveProperty("overview");
  });

  it("refuses a family nobody declared rather than answering the identity", () => {
    expect(() => toEngineShape("NOT_A_FAMILY", {}))
      .toThrowError(/not a declared fixture family/);
  });
});
