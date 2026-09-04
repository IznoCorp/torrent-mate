// The settings CATALOGUE — how a setting is identified, listed and read.
//
// Three derivations, and each was the engine's until L19 moved the settings
// panels into this feature. They live here and the engine IMPORTS THEM BACK,
// which is `app/icons.ts`'s arrangement and its reasoning word for word: one
// copy of every answer, read by both worlds, and the day the engine goes this
// file loses an importer rather than a subject.
//
// WHY NOT LEAVE THEM IN THE ENGINE AND READ THEM THROUGH THE REFERENCE. Because
// a producer reads the query cache (invariant 10), so the panel would flatten
// the LAYER's answer while the engine's own verbs flattened the FIXTURE — and
// « what is this setting's identity » would have two derivations that agree
// today. §13 is the clause, and the second copy is the one that goes wrong
// silently.
//
// WHAT DOES NOT LIVE HERE: `SETTINGS_STATE`, the mutable object the click
// delegation writes. It is not server state and it is not this feature's yet —
// it moves with the last delegation verb that writes it, which is L13's. The
// functions below take the pending edits as an ARGUMENT rather than reaching
// for that object, so nothing here depends on where it lives.
import type { Setting, SettingsTopic } from "./reference";

/**
 * How a setting is named, everywhere: by its file and its key.
 *
 * Args:
 *     setting: The setting.
 *
 * Returns:
 *     `<file>:<key>` — the form the address `setting:<id>` carries, which is
 *     why it is split on the FIRST colon and never the last.
 */
export function settingIdentifier(setting: Setting): string {
  return `${setting.f}:${setting.c}`;
}

/**
 * Every setting, flattened out of its rubric and carrying it.
 *
 * Args:
 *     topics: The rubrics, as the layer answers them.
 *
 * Returns:
 *     One entry per setting, each with the rubric it belongs to.
 */
export function flattenSettings(topics: readonly SettingsTopic[]): Setting[] {
  return topics.flatMap((topic) =>
    topic.r.map((setting) => ({ ...setting, topic })),
  );
}

/**
 * What a setting's value READS as right now — the pending edit, or the file's.
 *
 * The pending edits arrive as an argument rather than being read off the
 * engine's mutable state, so this answer does not depend on where that state
 * lives; the day it moves, this file does not.
 *
 * Args:
 *     setting: The setting.
 *     pending: The edits made and not yet written, keyed by identifier.
 *
 * Returns:
 *     The value to show.
 */
export function valueShown(
  setting: Setting,
  pending: ReadonlyMap<string, unknown>,
): unknown {
  const edit = pending.get(settingIdentifier(setting));
  return edit === undefined ? setting.v : edit;
}
