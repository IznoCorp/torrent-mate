// design/src/settings-labels.ts
// HOW A SETTING IS NAMED — the one implementation, for both the page that
// lists the settings and the panel that edits one.
//
// There were two: the fragment's (`libelleReglage` / `sujetReglage` /
// `uniteDe`, over four literal tables) and the panel component's copy of it.
// Two implementations of the same naming is one defect waiting: a label
// curated on one side and not the other renames a row on the page and leaves
// the panel above it saying something else. The tables live in `fr.json`
// (`settings.labels` / `subjects` / `units`) and this module is what reads
// them, so the page, the panel and the fragment's own panel title all name a
// setting the same way, by construction.
//
// THE DICTIONARIES ARE READ FROM THE RESOURCE DIRECTLY, not through `t()`:
// these are plain functions, not components, so they cannot hold a hook; their
// keys are DATA (setting ids, path segments, unit suffixes) rather than
// translation keys; and a key absent from a table has a fallback of its own
// that `t()`'s missing-key behaviour would fight.
//
// THE DETECTOR IS PART OF THE NAMING, not a diagnostic beside it. A path
// segment nobody named falls through to its humanised machine word — a tracker
// added tomorrow shows up as a raw key — and the only way to see that from
// outside is to record it as it happens. The set is published for the rule
// that reads it (R60), and the rule's own POSITIVE CONTROL exists because a
// hold asserting an empty set is also satisfied by a detector that stopped
// recording: the wave that moved this code out of the fragment had first to
// bring the recording with it, or the hold would have gone green on nothing.
import fr from "../../i18n/fr.json";
import { type Setting } from "../../features/settings/reference";

// Keyed by the setting-name suffix the split below produces — a suffix is
// data, not French.
const UNITS: Record<string, string> = fr.settings.units;

// THE LABEL IS FRENCH, AND IT IS CURATED. The keys are setting ids: a leaf
// name (`staging_dir`), a full path where the leaf alone would name two
// different things (`scraper.language`), or a scheduler unit name. Those are
// data, never French. A key absent from it falls back to itself, humanised.
const SETTING_LABELS: Record<string, string> = fr.settings.labels;

// A leaf key alone does not identify a setting. `enabled` sits under every
// tracker, every torrent client, every metadata provider and the web server —
// the row is labelled by its SUBJECT (the instance it belongs to), then by
// what it does. Segments naming a COLLECTION rather than an instance carry
// nothing and are dropped.
const SETTING_CONTAINERS = new Set([
  "providers",
  "clients",
  "categories",
  "priorities",
  "defaults",
  "genre_mapping",
  "cadence",
]);

// The SUBJECT names, keyed by the path segment they name — a tracker, a
// client, a provider, a category — which is data. A segment absent from the
// table falls back to itself, underscores spaced out.
const SUBJECT_NAMES: Record<string, string> = fr.settings.subjects;

// Every segment that fell through to its machine word, recorded as it
// happens. It catches an ABSENT name, never a wrong one — a wrong one is only
// caught by reading the file the segment comes from.
const unnamedSubjects = new Set<string>();

export function settingSubject(setting: Setting): string {
  const segments = setting.c
    .split(".")
    .slice(0, -1)
    .filter((s) => s !== setting.f && !SETTING_CONTAINERS.has(s));
  return segments
    .map((s) => {
      if (!SUBJECT_NAMES[s]) unnamedSubjects.add(s);
      return SUBJECT_NAMES[s] ?? s.replace(/_/g, " ");
    })
    .join(" · ");
}

export function settingLabel(setting: Setting): string {
  // A full path wins over a leaf: `language` means the metadata language in
  // one file and the scrape language in another, and two rows reading
  // « Langue des métadonnées » would name the same thing twice.
  const clean =
    SETTING_LABELS[setting.c] ??
    SETTING_LABELS[setting.n] ??
    (/^\d+$/.test(setting.n)
      ? `${fr.settings.genre} ${setting.n}`
      : setting.n.replace(/_/g, " "));
  const subject = settingSubject(setting);
  return subject ? `${subject} — ${clean}` : clean;
}

export function unitOf(setting: Setting): string | null {
  const last = setting.n.split("_").pop();
  return last ? (UNITS[last] ?? null) : null;
}

declare global {
  interface Window {
    // The seam the fragment's own panel title and the rule that reads the
    // detector both go through. Published from the module that owns the
    // naming, so it exists for anyone who has imported it — and the fragment,
    // which calls it from a click, runs long after the shell has evaluated.
    __settingLabels: {
      label: (setting: Setting) => string;
      subject: (setting: Setting) => string;
      unit: (setting: Setting) => string | null;
      unnamedSubjects: Set<string>;
    };
  }
}

window.__settingLabels = {
  label: settingLabel,
  subject: settingSubject,
  unit: unitOf,
  unnamedSubjects,
};
