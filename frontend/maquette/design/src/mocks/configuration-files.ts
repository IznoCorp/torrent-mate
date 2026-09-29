// What the layer holds of the configuration files' own content — mutable, so
// the write that saves one moves what the next read answers.
//
// HELD BESIDE THE LAYER'S STATE, AND RENEWED WITH IT: keyed on the object
// `mockState()` answers, which `reset()` replaces.
import FILES from "./seeds/configuration-files.json";
import { mockState } from "./state";
import type { components } from "../contract/types";

type FileContent = components["schemas"]["ConfigurationFileContent"];

const held = new WeakMap<object, FileContent[]>();

/**
 * Every configuration file whose content the layer holds, seeded on first read.
 *
 * @returns The files, as the layer holds them.
 */
export function configurationFiles(): FileContent[] {
  const owner = mockState();
  let files = held.get(owner);
  if (files === undefined) {
    files = structuredClone(FILES) as FileContent[];
    held.set(owner, files);
  }
  return files;
}

/**
 * A digest the written content answers from now on.
 *
 * NOT THE SHA-256 THE ENGINE COMPUTES, and it need not be: what the layer owes
 * a write is that the digest read before it no longer matches after it, so a
 * second editor holding the old one is refused. A short FNV-1a, spread to the
 * field's width.
 *
 * @param values The file's new content.
 * @returns Its digest.
 */
function contentDigest(values: unknown): string {
  const text = JSON.stringify(values);
  let hash = 0x811c9dc5;
  for (let index = 0; index < text.length; index += 1) {
    hash = Math.imul(hash ^ text.charCodeAt(index), 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, "0").repeat(8);
}

/**
 * Writes one file WHOLE, under the digest its editor read it at.
 *
 * @param name The file.
 * @param values Its new content.
 * @param digest The digest the editor read — the precondition.
 * @returns True when it was written; false when the file moved under the editor.
 */
export function writeFileContent(name: string, values: Record<string, unknown>, digest: string): boolean {
  const file = configurationFiles().find((one) => one.name === name);
  if (file === undefined || file.digest !== digest) return false;
  file.values = values;
  file.digest = contentDigest(values);
  return true;
}
