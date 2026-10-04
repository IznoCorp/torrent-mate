// B-670: Maintenance's destructive note drew its `**` — nothing renders Markdown,
// so an emphasis is a `{ e }` segment of a rich text, never a marker in the words.
import { describe, expect, it } from "vitest";
import WORDS from "./fr.json";

/**
 * Every string of the words, with the key path it is read under.
 *
 * @param node A subtree of `fr.json`.
 * @param path The key path down to it.
 * @returns The `[path, string]` pairs under it.
 */
function strings(node: unknown, path: string): [string, string][] {
  if (typeof node === "string") return [[path, node]];
  if (node === null || typeof node !== "object") return [];
  return Object.entries(node).flatMap(([key, child]) => strings(child, path ? `${path}.${key}` : key));
}

describe("the words", () => {
  it("carry no Markdown emphasis marker, which would be drawn as typed", () => {
    const marked = strings(WORDS, "").filter(([, text]) => text.includes("**")).map(([key]) => key);
    expect(marked).toEqual([]);
  });
});
