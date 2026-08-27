// Turning a contract-shaped value back into the shape the dying engine draws.
//
// WHY THIS EXISTS AT ALL, and it is a transitional thing with a date. L09 moves
// where a surface's DATA comes from; it does not rewrite the markup. Several
// surfaces are still drawn by producers that live in `legacy.js` — `cardHTML`,
// `secInner`, `factRowsHTML` — and those read the engine's own field names
// (`t`, `s`, `r`, `d`, `c`). The data now arrives from the mock layer in the
// CONTRACT's names (`title`, `secondaryLine`, `reason`, `folder`, `candidates`),
// because L08 renamed every key into full English words on its way out.
//
// So something has to speak both, for exactly as long as those producers live.
// It dies with them at L13, and nothing here outlives that.
//
// IT IS DRIVEN BY THE DECLARATION, NEVER BY A TABLE WRITTEN HERE. L08 wrote the
// projection down — `frontend/maquette/fixture-projections.json` — and the
// builder and the correspondence guard both read it. This reads the SAME file
// and inverts it. A hand-written map would be a second definition of one thing,
// and the drift would be invisible: each copy would stay internally consistent
// while describing different data. That is the shorthand block's own reasoning
// in that file, applied one step further along.
//
// IT LIVES IN `engine/` BECAUSE THAT IS WHAT IT DIES WITH. It knows no domain
// — it takes a family NAME and answers with a converted value — so `lib/`
// would satisfy invariant 10 too. Lifetime is what decides between them: the
// engine's bucket is the one L13 empties, and a conversion INTO the engine's
// shape has no meaning after the engine. Putting it in `lib/` would leave a
// file nobody could justify on the day the reason for it went.
//
// AND IT IS THE ONE MODULE THAT IMPORTS FROM OUTSIDE THE TREE.
// `fixture-projections.json` sits beside the harness, not under `design/`,
// because the builder and the correspondence guard read it too. Importing it
// rather than keeping a copy is the whole point — a copy is a second
// definition, and its drift would be invisible. The cost is 12 480 bytes in a
// bundle of 2.8 MB, for as long as the engine lives.
// `check-frontend-boundaries.py --arm tree` names this file as the only one
// allowed to do it, and refuses the next.
import projections from "../../../fixture-projections.json";

/** One level's key map, engine name to contract name, as the file declares it. */
type Renames = Record<string, string>;

/** A family's projection, as the file declares it. */
type Projection = {
  rename?: Record<string, Renames>;
  tuples?: Record<string, string[]>;
  $card?: boolean;
  $fact?: boolean;
};

const FAMILIES = projections.families as unknown as Record<string, Projection>;
const SHORTHANDS = projections.$shorthands as unknown as Record<string, Projection>;

/**
 * Expands a family's shorthand into the projection it stands for.
 *
 * Sixteen families share two shapes; the file says so once and both the builder
 * and the guard expand it from there. So does this.
 *
 * @param family The family name, as the register spells it.
 * @returns Its projection, shorthand expanded.
 * @throws When the family is not declared — an unknown family is a caller
 *     asking for a conversion nobody wrote down, and answering the identity
 *     would render the contract's own names into the engine's markup.
 */
function projectionOf(family: string): Projection {
  const declared = FAMILIES[family];
  if (declared === undefined) {
    throw new Error(
      `engine-shape: ${family} is not a declared fixture family — ` +
        "the conversion it asks for exists nowhere",
    );
  }
  for (const [name, shorthand] of Object.entries(SHORTHANDS)) {
    if (name.startsWith("$") && declared[name as "$card" | "$fact"]) {
      return { ...shorthand, ...declared };
    }
  }
  return declared;
}

/**
 * Inverts one key map: contract name back to engine name.
 *
 * @param renames The declared map, engine name to contract name.
 * @returns The same pairs the other way round.
 */
function inverted(renames: Renames): Renames {
  return Object.fromEntries(
    Object.entries(renames).map(([engine, contract]) => [contract, engine]),
  );
}

/**
 * Renames one object's own keys, leaving everything it does not name alone.
 *
 * A FIELD THE MAP DOES NOT NAME IS KEPT VERBATIM, and that is the projection's
 * own rule read backwards: it renamed the keys it listed and carried the rest,
 * so a field like `strip` or `chip` crosses both ways untouched.
 *
 * @param value The object to rename.
 * @param renames The contract-to-engine map.
 * @returns A new object wearing the engine's names.
 */
function renamedKeys(value: unknown, renames: Renames): unknown {
  // A VALUE THAT IS NOT A PLAIN OBJECT CROSSES UNTOUCHED, and leaving that out
  // is how a string becomes an object of its own characters. A suggestion's
  // `why` is a MIXED array — « Recoupé par », then `{emphasis: "4"}`, then
  // « titres de votre médiathèque » — and renaming a string's keys turned each
  // sentence into `{0: "R", 1: "e", …}`, which the engine rendered as
  // `undefined` in bold. Found by R11, which watches for exactly that word
  // reaching the screen.
  if (value === null || typeof value !== "object" || Array.isArray(value)) return value;
  const out: Record<string, unknown> = {};
  for (const [key, held] of Object.entries(value as Record<string, unknown>)) {
    out[renames[key] ?? key] = held;
  }
  return out;
}

/**
 * The path of the LEVEL that contains a declared path's last segment.
 *
 * A segment names the ENGINE's field (`c` in `[]/c[]`) while the value being
 * walked still wears the CONTRACT's (`candidates`), so the segment has to be
 * looked up in the map that renamed it — which is the map declared one level up.
 *
 * @param path A declared path.
 * @returns The declared path of its parent level.
 */
function parentOf(path: string): string {
  const segments = path.split("/").filter((segment) => segment !== "");
  const above = segments.slice(0, -1);
  if (above.length === 0) return "";
  if (above.length === 1 && above[0] === "[]") return "[]";
  return "/" + above.join("/");
}

/**
 * Walks one declared path and renames the level it lands on.
 *
 * THE GRAMMAR IS THE FILE'S OWN, and a first version of this misread it. Paths
 * are `""` (the root object), `"[]"` (every element of a root array), and any
 * number of `/name` or `/name[]` steps after either — so `"[]/c[]"` is TWO
 * steps, « every root element, then every element of its `c` », and reading it
 * as one segment called `[]` left every candidate wearing its contract names.
 * The unit test named that exact failure before the oracle could have.
 *
 * A step that finds nothing STOPS rather than throwing: the projection carries
 * optional fields (`choice` is absent on a dismissed decision), and a missing
 * one is data, not a broken path.
 *
 * @param value The value being converted, contract-shaped.
 * @param path The declared path.
 * @param renames The map declared for the level that path names.
 * @param all Every path the family declares, so a segment can be translated.
 * @returns The value with that level renamed.
 */
function atPath(
  value: unknown,
  path: string,
  renames: Renames,
  all: Record<string, Renames>,
): unknown {
  const segments = path.split("/").filter((segment) => segment !== "");
  const parent = all[parentOf(path)] ?? {};

  const walk = (held: unknown, index: number): unknown => {
    if (held === undefined || held === null) return held;
    if (index === segments.length) {
      return Array.isArray(held)
        ? (held as unknown[]).map((entry) => renamedKeys(entry, inverted(renames)))
        : renamedKeys(held, inverted(renames));
    }
    const segment = segments[index];
    if (segment === "[]") {
      return (held as unknown[]).map((entry) => walk(entry, index + 1));
    }
    // `*` IS EVERY KEY OF AN OBJECT, and the media sheet is where it appears:
    // `/eps/*[]` means « for each season number, for each episode ». A walker
    // that did not know it would treat `*` as a field name, find nothing, and
    // stop — leaving every episode wearing the contract's names, which the
    // engine renders as blank rows.
    if (segment === "*" || segment === "*[]") {
      // AND `*[]` IS THE FORM THAT ACTUALLY APPEARS. `/eps/*[]` is « for each
      // season number, for each episode », and a first version matched only the
      // bare `*` — so the segment fell through to the field lookup, found no
      // field called `*`, and returned the episodes untouched. They kept the
      // contract's names and the engine drew blank rows, which the oracle saw
      // as ten pixels.
      const walkEach = segment.endsWith("[]");
      const entries = Object.entries(held as Record<string, unknown>);
      return Object.fromEntries(
        entries.map(([key, value]) => [
          key,
          walkEach && Array.isArray(value)
            ? (value as unknown[]).map((one) => walk(one, index + 1))
            : walk(value, index + 1),
        ]));
    }
    const walkList = segment.endsWith("[]");
    const engineName = walkList ? segment.slice(0, -2) : segment;
    // The LAST segment is the one the parent map renamed; an intermediate one
    // was renamed by its own parent, which is `all` read at that depth. Both
    // are covered by looking the segment up in every declared level: a name
    // appears in exactly one of them, or the declaration is ambiguous and the
    // builder would have said so first.
    const contractName =
      parent[engineName]
      ?? Object.values(all).map((level) => level[engineName]).find(Boolean)
      ?? engineName;
    const entry = held as Record<string, unknown>;
    const inner = entry[contractName];
    if (inner === undefined) return entry;
    const converted = walkList
      ? (inner as unknown[]).map((one) => walk(one, index + 1))
      : walk(inner, index + 1);
    return { ...entry, [contractName]: converted };
  };

  return walk(value, 0);
}


/**
 * Turns a tuple the projection flattened back into the array the engine reads.
 *
 * @param value The value being converted.
 * @param tuples The declared tuple fields and their member order.
 * @returns The value with each declared tuple back as an array.
 */
function tuplesRestored(value: unknown, tuples: Record<string, string[]>): unknown {
  const one = (entry: Record<string, unknown>): Record<string, unknown> => {
    const out = { ...entry };
    for (const [field, members] of Object.entries(tuples)) {
      const held = out[field];
      if (held !== null && typeof held === "object" && !Array.isArray(held)) {
        out[field] = members.map((member) => (held as Record<string, unknown>)[member]);
      }
    }
    return out;
  };
  return Array.isArray(value)
    ? (value as Record<string, unknown>[]).map(one)
    : one(value as Record<string, unknown>);
}

/**
 * Converts ONE ENTRY of a family the projection keys by data.
 *
 * WHY IT IS SEPARATE. A family marked `keyedByData` is a MAP — `SHEETS_RAW` is
 * every media sheet, keyed by title — and its declared paths describe one
 * VALUE of that map rather than the map itself. The layer serves one sheet at
 * an address, not the map, so the paths are applied to what arrived.
 *
 * @param family The fixture family it stands for, as the register spells it.
 * @param value One entry, as the layer answered it.
 * @returns The same entry wearing the engine's own field names.
 */
export function toEngineShapeEntry<Result>(family: string, value: unknown): Result {
  return convert(projectionOf(family), value) as Result;
}

/**
 * Converts one contract-shaped value into the shape the engine's markup reads.
 *
 * @param family The fixture family it stands for, as the register spells it.
 * @param value The value the mock layer answered with.
 * @returns The same data wearing the engine's own field names.
 */
export function toEngineShape<Result>(family: string, value: unknown): Result {
  return convert(projectionOf(family), value) as Result;
}

/**
 * Applies one projection's declared paths, deepest first.
 *
 * @param projection The projection, shorthand expanded.
 * @param value What to convert.
 * @returns The converted value.
 */
function convert(projection: Projection, value: unknown): unknown {
  let held = value;
  // ROOT FIRST, THEN DEEPER. A deeper path names its segment in the ENGINE's
  // vocabulary; renaming the root before descending would leave the segment
  // lookup asking for a key that had just been renamed away.
  const depth = (path: string) => path.split("/").filter((s) => s !== "").length;
  const paths = Object.entries(projection.rename ?? {}).sort(
    (left, right) => depth(right[0]) - depth(left[0]),
  );
  for (const [path, renames] of paths) {
    held = atPath(held, path, renames, projection.rename ?? {});
  }
  if (projection.tuples) held = tuplesRestored(held, projection.tuples);
  return held;
}
