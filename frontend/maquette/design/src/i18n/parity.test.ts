// The English catalogue is the French one in another language: the same keys, the same
// shape, the same interpolation, the same plural forms. `en.json` is read by the language
// switch (phase 2); until then this test is what keeps a missing, extra or mangled leaf
// from reaching an English reader as a raw key or a literal `{{name}}`.
import { describe, expect, it } from "vitest";
import EN from "./en.json";
import FR from "./fr.json";

type Leaf = string | string[];

/**
 * Every leaf of a catalogue, keyed by its dotted path. A list of strings is one leaf: the
 * code reads it whole (`returnObjects`), so its length is part of its shape.
 *
 * @param node A subtree of a catalogue.
 * @param path The key path down to it.
 * @returns The `[path, leaf]` pairs under it, in file order.
 */
function leaves(node: unknown, path: string): [string, Leaf][] {
  if (typeof node === "string" || Array.isArray(node)) return [[path, node as Leaf]];
  if (node === null || typeof node !== "object") return [[path, String(node) as Leaf]];
  return Object.entries(node).flatMap(([key, child]) => leaves(child, path ? `${path}.${key}` : key));
}

/**
 * The strings a leaf holds.
 *
 * @param leaf A string or a list of strings.
 * @returns Its strings.
 */
function texts(leaf: Leaf): string[] {
  return typeof leaf === "string" ? [leaf] : leaf;
}

/**
 * The `{{name}}` placeholders of a leaf, sorted so two leaves compare regardless of word order.
 *
 * @param leaf A string or a list of strings.
 * @returns The placeholder names, one per occurrence.
 */
function placeholders(leaf: Leaf): string[] {
  return texts(leaf).flatMap((text) => [...text.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1])).sort();
}

const FR_LEAVES = leaves(FR, "");
const EN_LEAVES = new Map(leaves(EN, ""));

describe("the English catalogue", () => {
  it("has exactly the key set of the French one — same nesting, same leaves, plural forms included", () => {
    expect([...EN_LEAVES.keys()].sort()).toEqual(FR_LEAVES.map(([key]) => key).sort());
  });

  it("has the same kind of leaf as the French one at every key (string or list of the same length)", () => {
    const drift = FR_LEAVES.filter(([key, fr]) => {
      const en = EN_LEAVES.get(key);
      if (en === undefined || typeof en !== typeof fr) return true;
      return Array.isArray(fr) && fr.length !== (en as string[]).length;
    }).map(([key]) => key);
    expect(drift).toEqual([]);
  });

  it("keeps the interpolation placeholders of every leaf", () => {
    const drift = FR_LEAVES.filter(([key, fr]) => {
      const en = EN_LEAVES.get(key);
      return en !== undefined && placeholders(en).join() !== placeholders(fr).join();
    }).map(([key]) => key);
    expect(drift).toEqual([]);
  });

  it("has no empty leaf where the French one has text", () => {
    const empty = FR_LEAVES.flatMap(([key, fr]) => {
      const en = EN_LEAVES.get(key);
      if (en === undefined) return [];
      return texts(fr).flatMap((text, index) => (text !== "" && texts(en)[index]?.trim() === "" ? [key] : []));
    });
    expect(empty).toEqual([]);
  });

  it("carries no Markdown emphasis marker, which would be drawn as typed", () => {
    const marked = [...EN_LEAVES].filter(([, leaf]) => texts(leaf).some((text) => text.includes("**"))).map(([key]) => key);
    expect(marked).toEqual([]);
  });
});
