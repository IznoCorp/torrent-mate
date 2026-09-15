// The settings screen's own working state, and the three small answers read
// off it.
//
// It is INTERFACE state, never server state: which rubric is open, what the
// search says, the edits not yet saved, and the two banners the screen raises
// itself. The page and the panels READ it and the verbs WRITE it in place; the
// store's version bump is what makes a component read it again.
import type { Setting, SettingsState } from "./types";

/** The one settings working state. Mutated in place; never replaced. */
export const SETTINGS_STATE: SettingsState = {
  modifs: new Map(),
  topic: null,
  q: "",
  readOnly: false,
  conflict: false,
};

/**
 * The file a setting really lives in, as the save bar names it.
 *
 * Most settings live in a JSON5 overlay named by its concern, and one family
 * does not: the schedules belong to PM2 and live in `ecosystem.config.js`.
 * Appending « .json5 » to every name would make the save bar promise a file
 * that does not exist.
 *
 * @param file The setting's file, as the catalogue names it.
 * @returns The file's name, with its extension.
 */
export function fileName(file: string): string {
  return file.includes(".") ? file : file + ".json5";
}

/**
 * The files the pending edits would write, each once.
 *
 * @returns The files, in the order their first edit was made.
 */
export function changedFiles(): string[] {
  return [...new Set([...SETTINGS_STATE.modifs.keys()].map((identifier) => identifier.split(":")[0]))];
}

/**
 * What a field's text BECOMES, in the type the setting came from.
 *
 * A number field hands back a string; stored as one it would compare unequal to
 * the file's number for ever, so it goes back as a number — or as the file's
 * own value when the text is not one, and as nothing when it is empty.
 *
 * @param setting The setting edited.
 * @param text What the field holds.
 * @returns The value to store, or null for an emptied field.
 */
export function typedValue(setting: Setting, text: string): unknown {
  if (setting.type === "number") {
    const number = Number(text);
    return text.trim() === "" ? null : Number.isNaN(number) ? setting.raw : number;
  }
  return text === "" ? null : text;
}
