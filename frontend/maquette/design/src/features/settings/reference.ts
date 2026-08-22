// Configuration — every editable setting
//
// The slice of `window.__referentiel` this feature reads, and nothing else.
//
// The engine publishes ONE object; what it publishes is not one subject. A
// single 340-line declaration of all of it made every module that needed two
// members depend on all hundred and eight, and seventeen of twenty-five
// modules did. Each slice is declared where its subject lives instead, and the
// global's own type is their intersection (app/reference.d.ts) — so a
// reader imports nothing to be typed, and a member nobody's subject claims has
// nowhere to be written down.

import type { EngineDrawing } from "../../lib/engine-drawing";

// One secret: what it is called, its key, and whether it is SET. Never its
// value — a value shown once is a value read by everything looking at the
// screen.
export type Secret = { k: string; l: string; def?: boolean };

// One editable setting, as `allSettings()` flattens one — the legacy
// settings-panel row (see refonte.html's `SETTINGS`) merged with the
// enclosing rubric it belongs to. `brut` / `v` stay untyped: a setting's
// raw and current value can be a string, a number, or a nested structure
// (e.g. the `disks` array), and the source never declares which.
export type Setting = {
  f: string;
  c: string;
  type: string;
  brut: unknown;
  n: string;
  v: unknown;
  note?: string;
  topic: Record<string, unknown>;
};

// The settings screen's own mutable state, owned by the fragment and written by
// the document-level delegation: which rubric is open, the search text, the
// PENDING edits (a Map keyed by `settingId`), and the three banners. A component
// READS it — it never replaces it — and re-reads on every store bump.
export type SettingsState = {
  modifs: Map<string, unknown>;
  topic: string | null;
  q: string;
  readOnly: boolean;
  redemarrage: boolean;
  conflict: boolean;
};

// One settings RUBRIC — the heading one navigates BY WHAT ONE WANTS TO CHANGE,
// never by file, and the settings it holds.
export type SettingsTopic = {
  id: string;
  t: string;
  s: string;
  r: Setting[];
};

export type SettingsReference = EngineDrawing & {
  SETTINGS: SettingsTopic[];
  SETTINGS_STATE: SettingsState;
  SECRETS: Secret[];
  // Réglages (settings) panel actions — read the full setting list, derive
  // a setting's storage id, coerce a raw field input back to its stored
  // type, and apply/open a pending edit. See refonte.html's `SETTINGS`
  // neighbourhood for the file/rubric structure `Setting.rubrique` carries.
  allSettings: () => Setting[];
  settingId: (setting: Setting) => string;
  // The value a field must DRAW: the pending edit when there is one, the
  // file's `brut` otherwise. The pending-edit overlay itself stays private to
  // the engine — this returns the value, never the map.
  rawValue: (setting: Setting) => unknown;
  typedValue: (setting: Setting, text: string) => unknown;
  changeSetting: (id: string, value: unknown) => void;
  openSetting: (id: string) => void;
  displayedValue: (setting: Setting) => unknown;
  fileName: (file: string) => string;
  changedFiles: () => string[];
};

/**
 * Reads this feature's slice of the engine's published reference object.
 *
 * The object is read-only reference data the engine publishes ONCE, at
 * definition time, well before any component's module evaluates — so a plain
 * accessor is the right shape, not a subscription: there is nothing here for a
 * component to miss by reading it straight.
 *
 * Returns:
 *     The slice, typed. The global's own declaration (app/reference.d.ts) is the
 *     intersection of every slice, so no cast is needed here.
 */
export function useSettingsReference(): SettingsReference {
  return window.__referentiel;
}
