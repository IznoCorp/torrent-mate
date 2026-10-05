// The English catalogue is the French one in another language: the same keys, the same
// shape, the same interpolation, the same plural forms — and its own words, not the French
// ones copied. `en.json` is what an account whose language is English reads, and what the
// sign-in page shows a browser that is not French; this test keeps a missing, extra, mangled
// or untranslated leaf from reaching that reader as a raw key, a literal `{{name}}` or French.
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

// THE LEAVES THAT READ THE SAME IN BOTH LANGUAGES, each family for its reason. Anything else equal
// to its French is a French value copied into the English catalogue — an English reader would meet
// it as French. A leaf that has since been translated must leave the list.
const IDENTICAL_IN_BOTH_LANGUAGES: ReadonlySet<string> = new Set([
  // Names: brands, services, trackers, the genres as the providers name them, a file and an
  // address shown as they are, a cron expression, and each language's own name in itself.
  "settings.labels.cross_seed", "settings.labels.tmdb", "settings.labels.tvdb", "settings.labels.omdb",
  "settings.labels.trakt", "settings.subjects.c411", "settings.subjects.tr4ker", "settings.subjects.lacale",
  "settings.subjects.qbittorrent", "settings.subjects.transmission", "settings.subjects.tmdb",
  "settings.subjects.tvdb", "settings.subjects.omdb", "settings.subjects.trakt", "settings.subjects.telegram",
  "settings.subjects.healthchecks", "settings.subjects.spotlight", "settings.subjects.cross_seed",
  "settings.subjects.audio", "screens.trackers.tabTorrents", "screens.trackers.tabTrackers",
  "screens.media.genreNames.action", "screens.media.genreNames.action_adventure",
  "screens.media.genreNames.animation", "screens.media.genreNames.crime", "screens.media.genreNames.kids",
  "screens.media.genreNames.reality", "screens.media.genreNames.romance", "screens.media.genreNames.thriller",
  "screens.media.genreNames.war_politics", "screens.media.genreNames.western", "screens.library.mediaNoteRoute",
  "screens.library.loadingNoteDatabase", "screens.acquisition.cadenceNoteInner",
  "screens.accountPage.language.names.fr", "screens.accountPage.language.names.en", "navigation.pages.acq",
  "navigation.pages.trackers", "navigation.pages.maint", "roles.seed.admin", "push.generic.title",
  // Notation: symbols, units and placeholders, no word of either language.
  "screens.ranking.threshold", "screens.trackers.panel.stateWithReason", "screens.torrents.size",
  "screens.torrents.rate", "screens.torrents.volumes", "screens.torrents.downloadRate",
  "screens.torrents.uploadRate", "screens.torrents.selectorCountOff", "screens.media.minutesShort",
  "screens.system.arrow", "screens.system.runSeconds_one", "screens.system.runSeconds_other",
  "screens.system.runMinutes_one", "screens.system.runMinutes_other", "screens.system.runMinutesSeconds_one",
  "screens.system.runMinutesSeconds_other", "screens.run.stepStatus.unknown", "screens.library.incompleteUnknown",
  "screens.library.incompleteInvented", "screens.library.countCategory", "screens.library.emptySearchDot",
  "screens.library.rowLine", "screens.acquisition.followSort.az", "screens.acquisition.followSort.za",
  "screens.acquisition.emptyNoFollowsBodyPlus", "screens.maintenance.arrow", "screens.settings.arrow",
  "surfaces.ladder.step", "surfaces.ladder.subStep", "settingValue.andMore", "panels.sort.ways.az.normal",
  "panels.sort.ways.az.inverse", "verbs.library.delete.videoFilesValue", "verbs.acquisition.searchAgain",
  "verbs.trackers.remove.bodyFiles", "verbs.library.delete.keptSeparator",
  // Words both languages spell alike.
  "settings.units.minutes", "settings.units.m", "settings.units.ratio", "settings.genre",
  "settings.field.structureWord", "screens.ranking.previewScore", "screens.trackers.ratio",
  "screens.trackers.trends.stable", "screens.trackers.panel.ratio", "screens.trackers.panel.volumes",
  "screens.torrents.sources_one", "screens.torrents.sources_other", "screens.torrents.panel.tracker",
  "screens.torrents.panel.obligation", "screens.torrents.selectorCount_one", "screens.torrents.selectorCount_other",
  "screens.releases.sourcesUnit", "screens.releases.scoreLabel", "screens.media.synopsis", "screens.media.catalogue",
  "screens.system.services", "screens.system.toAcquisitionLink", "screens.system.toMaintenanceLink",
  "screens.system.pauseSentinel", "screens.run.step.scrape", "screens.run.options", "screens.library.lenses.anim",
  "screens.library.lenses.standup", "screens.library.lenses.anime", "screens.acquisition.swipePause",
  "screens.accountPage.transport", "screens.accountPage.notifications.heading", "screens.notFound.menuLink",
  "surfaces.decision.heading", "surfaces.card.automatic", "navigation.groups.supervision",
  "navigation.groups.configuration", "navigation.drawerLabel", "panels.add.meta", "verbs.library.delete.itemOne",
  "verbs.library.delete.itemMany",
]);

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

  it("is translated, not copied: no leaf equals its French one but the named exceptions", () => {
    const copied = FR_LEAVES.filter(([key, fr]) => {
      const en = EN_LEAVES.get(key);
      return en !== undefined && texts(fr).join("\u0000").trim() !== "" && texts(fr).join("\u0000") === texts(en).join("\u0000")
        && !IDENTICAL_IN_BOTH_LANGUAGES.has(key);
    }).map(([key]) => key);
    expect(copied).toEqual([]);
  });

  it("names as identical only leaves that still are", () => {
    const drifted = [...IDENTICAL_IN_BOTH_LANGUAGES].filter((key) => {
      const fr = FR_LEAVES.find(([one]) => one === key)?.[1];
      const en = EN_LEAVES.get(key);
      return fr === undefined || en === undefined || texts(fr).join("\u0000") !== texts(en).join("\u0000");
    });
    expect(drifted).toEqual([]);
  });

  it("carries no Markdown emphasis marker, which would be drawn as typed", () => {
    const marked = [...EN_LEAVES].filter(([, leaf]) => texts(leaf).some((text) => text.includes("**"))).map(([key]) => key);
    expect(marked).toEqual([]);
  });
});
