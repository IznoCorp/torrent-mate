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
