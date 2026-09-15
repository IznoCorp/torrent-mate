// Configuration — every editable setting
//
// The shapes this feature's reads answer, declared where the subject lives.

import type { Schemas } from "../../lib/contract-schemas";

// One secret: what it is called, its key, and whether it is SET. Never its
// value — a value shown once is a value read by everything looking at the
// screen.
export type Secret = Schemas["Secret"];

// One editable setting, as `allSettings()` flattens one — the legacy
// settings-panel row (see refonte.html@60530dbd8's `SETTINGS`) merged with the
// enclosing rubric it belongs to (`topic`, once flattened). `raw` stays untyped: a setting's
// raw and current value can be a string, a number, or a nested structure
// (e.g. the `disks` array), and the source never declares which.
export type Setting = Schemas["Setting"] & { topic?: Record<string, unknown> };

// The settings screen's own mutable state, owned by the fragment and written by
// the document-level delegation: which rubric is open, the search text, the
// PENDING edits (a Map keyed by `settingId`), and the banners it still carries.
// A component READS it — it never replaces it — and re-reads on every store bump.
//
// `redemarrage` LEFT THIS OBJECT at B-343. A restart owed is a fact of the
// LAYER, answered by `/api/config/status`, and the banner is a reader of that
// query: raised here it was raised on something nothing re-renders, so the
// operator saved, was told « Enregistré », and saw no banner at all.
export type SettingsState = {
  modifs: Map<string, unknown>;
  topic: string | null;
  q: string;
  readOnly: boolean;
  conflict: boolean;
};

// One settings RUBRIC — the heading one navigates BY WHAT ONE WANTS TO CHANGE,
// never by file, and the settings it holds.
export type SettingsTopic = Schemas["SettingsTopic"];
