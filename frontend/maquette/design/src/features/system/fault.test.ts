// The simulated fault falls on a scheduler chosen by NAME, and carries that
// scheduler's own cadence.
//
// WHAT MAKES THIS NON-VACUOUS. It runs on the COMMITTED seed and the COMMITTED
// resources — the same two artefacts the page reads — rather than on a list
// this file invents, and it asserts the corpus before it asserts anything about
// it: a list of no schedulers, or a name matching no row, would make every
// claim below true of nothing.
//
// THE PROPERTY IT HOLDS, and it is one property in two halves. A late
// scheduler's sub-line names ITS OWN cadence, so the substitution and the
// sentence it substitutes must stay paired. Keyed by POSITION they do not: a
// reordering of the list the layer answers moves the fault onto another job and
// transplants the hourly cadence onto it. So the reorder is the measurement —
// the same row must go late, with the same words, whatever order it arrives in.
import { describe, expect, it } from "vitest";
import i18next from "i18next";
import FRENCH from "../../i18n/fr.json";
import SCHEDULERS from "../../mocks/seeds/schedulers.json";
import { toEngineShape } from "../../engine/engine-shape";
import { schedulersDown, type OverdueWords } from "./fault";
import type { Fact } from "../../lib/engine-drawing";

// The resources without the browser bootstrap: `src/i18n/index.ts` publishes
// its instance on `window`, which a runner does not have, and a test that
// cannot be collected without a browser is B-077 exactly.
await i18next.init({
  lng: "fr",
  resources: { fr: { translation: FRENCH } },
  interpolation: { escapeValue: false },
});

const words: OverdueWords = {
  label: i18next.t("screens.system.schedulerLateLabel"),
  value: i18next.t("screens.system.schedulerLateValue"),
  secondaryLine: i18next.t("screens.system.schedulerLateLine"),
};

// A sub-line is « <cadence> · <last pass> · <count> ». The cadence is what the
// fault must not move between rows, and it is the first segment.
const cadence = (fact: Fact) => (fact.s ?? "").split("·")[0].trim();

// THROUGH THE SAME CONVERSION THE PAGE USES. The seed is written in the
// CONTRACT's field names (`label`, `tone`, `value`, `secondaryLine`); what
// reaches the derivation is what `useSystemRead`'s queryFn cached, which is the
// engine's (`l`, `ton`, `v`, `s`). Asserting against the raw seed would have
// been asserting against a shape this code never meets — the first version of
// this file did, and every claim below was true of an empty list.
const healthy = toEngineShape<Fact[]>("SCHEDULERS", SCHEDULERS);
const reversed = [...healthy].reverse();

describe("the corpus these claims are made about", () => {
  it("holds more than one scheduler, so an ordering exists to get wrong", () => {
    expect(healthy.length).toBeGreaterThan(1);
  });

  it("holds exactly one row carrying the overdue name", () => {
    expect(healthy.filter((row) => row.l === words.label)).toHaveLength(1);
  });

  it("puts that row FIRST, which is what a positional key would also find", () => {
    expect(healthy[0].l).toBe(words.label);
  });
});

describe("the fault falls on the named row, in any order", () => {
  for (const [order, list] of [["as answered", healthy], ["reversed", reversed]] as const) {
    it(`draws exactly one row late — ${order}`, () => {
      const late = schedulersDown(list, words).filter((row) => row.ton === "alert");
      expect(late).toHaveLength(1);
      expect(late[0].l).toBe(words.label);
    });

    it(`gives the late row ITS OWN cadence, not another job's — ${order}`, () => {
      const drawn = schedulersDown(list, words);
      const late = drawn.find((row) => row.ton === "alert") as Fact;
      const same = list.find((row) => row.l === words.label) as Fact;
      expect(cadence(late)).toBe(cadence(same));
      expect(late.v).toBe(words.value);
    });

    it(`leaves every other row exactly as it arrived — ${order}`, () => {
      const drawn = schedulersDown(list, words);
      expect(drawn.filter((row) => row.l !== words.label))
        .toEqual(list.filter((row) => row.l !== words.label));
      expect(drawn.map((row) => row.l)).toEqual(list.map((row) => row.l));
    });
  }
});

describe("a name matching no row alters nothing", () => {
  it("returns the healthy list rather than drawing a plausible lie", () => {
    const drawn = schedulersDown(healthy, { ...words, label: "no such scheduler" });
    expect(drawn).toEqual(healthy);
    expect(drawn.filter((row) => row.ton === "alert")).toHaveLength(0);
  });
});
