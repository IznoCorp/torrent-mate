// The settings' own words, held against the 159 the engine rendered.
//
// WHAT MAKES THIS NON-VACUOUS. The expected values are the `displayedValue`
// strings COMMITTED IN THE SEED — extracted from `legacy.js` by a declared
// projection and held byte for byte against it by
// `scripts/check-mock-seeds.py --arm correspondence`. So this asserts against
// the engine's own rendering, one artefact removed, rather than against
// something this file decided.
//
// AND IT COUNTS WHAT IT COMPARED. « Every field matches » is what a test over an
// empty list also reports, so the corpus is asserted first.
import { describe, expect, it } from "vitest";
import SETTINGS from "../../mocks/seeds/settings.json";
import i18next from "i18next";
import FRENCH from "../../i18n/fr.json";
import { scheduleInWords, settingInWords } from "./format";

// THE RESOURCES, WITHOUT THE BROWSER BOOTSTRAP. `src/i18n/index.ts` publishes
// the instance on `window`, which does not exist in a runner — and a test that
// cannot be collected without a browser is B-077 exactly. It is initialised
// from the same resource file the application loads, which is what the
// assertions are about.
await i18next.init({
  lng: "fr",
  resources: { fr: { translation: FRENCH } },
  interpolation: { escapeValue: false },
});

type Setting = {
  key: string;
  type: string;
  raw: unknown;
  displayedValue: string;
  precision?: number;
};

const FIELDS: Setting[] = (SETTINGS as { settings: Setting[] }[])
  .flatMap((topic) => topic.settings);

// The seven fields whose rendering carries a decimal the value does not. JSON
// holds one number for `4` and `4.0`; the contract's `precision` is what the
// backend is asked for, and until it answers these are named rather than
// silently wrong.
const WITHOUT_PRECISION = new Set([
  "library.video.max_size_movie_gb",
  "library.video.max_size_episode_gb",
  "tracker.providers.c411.economy.target_ratio",
  "tracker.providers.c411.economy.min_ratio",
  "ingest.min_ratio",
  "fuzzy_match.short_title_threshold",
  "fuzzy_match.long_title_threshold",
]);

describe("settingInWords", () => {
  it("has a corpus to compare", () => {
    expect(FIELDS.length).toBe(159);
  });

  it("says every field exactly as the engine did", () => {
    const wrong: string[] = [];
    for (const field of FIELDS) {
      if (WITHOUT_PRECISION.has(field.key)) continue;
      const kind = field.type === "text" && /^[\d*]/.test(String(field.raw))
        && String(field.raw).split(/\s+/).length === 5 ? "schedule" : field.type;
      const said = settingInWords(kind, field.raw, field.precision);
      if (said !== field.displayedValue) {
        wrong.push(`${field.key}: « ${said} » !== « ${field.displayedValue} »`);
      }
    }
    expect(wrong).toEqual([]);
  });

  it("recovers what the rendered form had lost", () => {
    // « multi, vf, vostfr +1 » — the fourth element was unrecoverable from the
    // contract. It is in `raw`, and reading `raw` is recovery, not the
    // re-derivation B-087 forbids.
    const lossy = FIELDS.find((field) => field.key === "library.audio.profile_priority");
    expect(lossy).toBeDefined();
    expect(lossy!.raw).toEqual(["multi", "vf", "vostfr", "vo"]);
    expect(settingInWords("list", lossy!.raw)).toBe("multi, vf, vostfr +1");  // french-ok: rendered output
  });

  it("names the seven fields whose precision the value cannot carry", () => {
    for (const key of WITHOUT_PRECISION) {
      const field = FIELDS.find((one) => one.key === key);
      expect(field).toBeDefined();
      // Without the contract's precision the number says itself, which is why
      // the demand exists; with it, it says what the screen said.
      expect(settingInWords("number", field!.raw)).toBe(String(field!.raw));
      expect(settingInWords("number", field!.raw, 1)).toBe(field!.displayedValue);
    }
  });
});

describe("scheduleInWords", () => {
  it("says the four shapes the data holds", () => {
    expect(scheduleInWords("15 * * * *")).toBe("toutes les heures, à la 15ᵉ minute");  // french-ok: the app's rendered output
    expect(scheduleInWords("0 3 * * *")).toBe("chaque jour à 03 h 00");  // french-ok: the app's rendered output
    expect(scheduleInWords("10 3,15 * * *")).toBe("à 03 h 10 et 15 h 10");  // french-ok: the app's rendered output
    expect(scheduleInWords("30 4 * * 0")).toBe("le dimanche à 04 h 30");  // french-ok: the app's rendered output
  });

  it("answers with the expression itself when it cannot read one", () => {
    // A schedule nobody can read is not a schedule that runs at midnight.
    for (const unreadable of ["*/5 * * * *", "0 3 1 * *", "not a cron", "0 3 * *"]) {
      expect(scheduleInWords(unreadable)).toBe(unreadable);
    }
  });
});
