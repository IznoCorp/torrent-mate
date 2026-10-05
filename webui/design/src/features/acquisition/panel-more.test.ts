// The « ⋮ » sheet says what it does (BUGS.md, operator report 20261005-133241-89).
//
// WHAT MAKES THIS NON-VACUOUS. The operator could not tell what « Veille » was nor what its
// button did. The sheet's words are read through the descriptor the producer builds, so a key
// re-aimed at the old copy, or the old copy put back, fails here by the sentence it says; and
// the catalogue is walked whole, so a leaf elsewhere that still calls this pass « veille »
// fails too — in both languages, since the English one is held to the same words.
import { describe, expect, it } from "vitest";
import i18next from "../../lib/unit-words";
import { producerFor } from "../../ui/panel/contract";
import "./panel-more";

/** The one leaf allowed to say « veille »: the downloads watcher daemon, not the detection pass. */
const OTHER_THING_KEYS = new Set(["screens.system.serviceDownLabel"]);

/**
 * Every string leaf of a catalogue, keyed by its dotted path.
 *
 * @param node A subtree of a catalogue.
 * @param path The key path down to it.
 * @returns The `[path, value]` pairs under it.
 */
function strings(node: unknown, path: string): [string, string][] {
  if (typeof node === "string") return [[path, node]];
  if (node === null || typeof node !== "object") return [];
  return Object.entries(node).flatMap(([key, child]) => strings(child, path ? `${path}.${key}` : key));
}

/** The sheet's descriptor, asked the way the panel engine asks for it. */
function sheet() {
  const descriptor = producerFor("more")?.("", {} as never);
  if (!descriptor) throw new Error("the « more » sheet has no descriptor");
  return descriptor;
}

/** The sheet's text, as a person reads it: title, explanation, facts and buttons. */
function sheetText(): string[] {
  const descriptor = sheet();
  const words: string[] = [descriptor.title ?? "", String(descriptor.meta ?? "")];
  for (const bloc of descriptor.blocs as { lignes?: { c: string }[]; actions?: { text: string }[] }[]) {
    words.push(...(bloc.lignes ?? []).map((ligne) => ligne.c), ...(bloc.actions ?? []).map((action) => action.text));
  }
  return words;
}

describe("the « ⋮ » sheet", () => {
  it("is titled, explained and offered in the decided words", () => {
    const descriptor = sheet();
    expect(descriptor.title).toBe("Détection des nouveautés"); // french-ok: the engine's own output, asserted
    expect(descriptor.meta).toBe(
      "Vérifie si vos suivis ont du nouveau — un épisode diffusé, un film sorti — pour qu'il soit cherché. Se fait automatiquement à intervalles réguliers.", // french-ok: the engine's own output, asserted
    );
    expect(sheetText()).toEqual(
      expect.arrayContaining(["Dernière vérification", "Prochaine vérification", "Vérifier maintenant"]), // french-ok: the engine's own output, asserted
    );
  });

  it("keeps no « veille » and no « Second rang » on the sheet", () => {
    for (const words of sheetText()) {
      expect(words).not.toMatch(/veille|second rang|lancer/i);
    }
  });
});

describe("the catalogue", () => {
  it.each(["fr", "en"])("does not call the detection pass a watch in %s", (language) => {
    const catalogue = i18next.getResourceBundle(language, "translation");
    const offenders = strings(catalogue, "")
      .filter(([key, value]) => !OTHER_THING_KEYS.has(key) && /veille|\bwatch(?!ed|ing)\b/i.test(value))
      .map(([key]) => key);
    // `screens.*.watch` names the pipeline's « watch » STEP (« Surveillance »), another thing.
    expect(offenders.filter((key) => !/(^|\.)steps?\.|\.watch$/.test(key))).toEqual([]);
  });
});
