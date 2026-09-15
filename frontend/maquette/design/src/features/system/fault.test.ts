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
import { withOneRowDown, type OverdueWords } from "./fault";
import type { Schemas } from "../../lib/contract-schemas";

type Fact = Schemas["Fact"];

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
const cadence = (fact: Fact) => (fact.secondaryLine ?? "").split("·")[0].trim();

// THE SHAPE THE PAGE MEETS. The seed is written in the contract's field names
// (`label`, `tone`, `value`, `secondaryLine`), and what `useSystemRead`'s
// queryFn caches is the answer as served, in those same names — so the seed IS
// what reaches the derivation. The first version of this file asserted against
// a shape the code never met, and every claim below was true of an empty list.
const healthy = SCHEDULERS as Fact[];
const reversed = [...healthy].reverse();

describe("the corpus these claims are made about", () => {
  it("holds more than one scheduler, so an ordering exists to get wrong", () => {
    expect(healthy.length).toBeGreaterThan(1);
  });

  it("holds exactly one row carrying the overdue name", () => {
    expect(healthy.filter((row) => row.label === words.label)).toHaveLength(1);
  });

  it("puts that row FIRST, which is what a positional key would also find", () => {
    expect(healthy[0].label).toBe(words.label);
  });
});

describe("the fault falls on the named row, in any order", () => {
  for (const [order, list] of [["as answered", healthy], ["reversed", reversed]] as const) {
    it(`draws exactly one row late — ${order}`, () => {
      const late = withOneRowDown(list, words).filter((row) => row.tone === "alert");
      expect(late).toHaveLength(1);
      expect(late[0].label).toBe(words.label);
    });

    // THE ROW IT COMPARES AGAINST IS THE ONE THAT WAS ALTERED, never the one
    // that was NAMED, and the difference is the whole of this hold. The
    // substituted sentence IS the named row's cadence, so comparing it with
    // that row's own cadence is true by construction whichever row received
    // it — the first version of this assertion did exactly that and stayed
    // GREEN under the mutation it was written to catch. Reading the altered
    // row's own healthy cadence is what sees a cadence transplanted.
    it(`gives the late row ITS OWN cadence, not another job's — ${order}`, () => {
      const drawn = withOneRowDown(list, words);
      const late = drawn.find((row) => row.tone === "alert") as Fact;
      const healthyRow = list.find((row) => row.label === late.label) as Fact;
      expect(cadence(late)).toBe(cadence(healthyRow));
      expect(late.value).toBe(words.value);
    });

    it(`leaves every other row exactly as it arrived — ${order}`, () => {
      const drawn = withOneRowDown(list, words);
      expect(drawn.filter((row) => row.label !== words.label))
        .toEqual(list.filter((row) => row.label !== words.label));
      expect(drawn.map((row) => row.label)).toEqual(list.map((row) => row.label));
    });
  }
});

describe("a name matching no row alters nothing", () => {
  it("returns the healthy list rather than drawing a plausible lie", () => {
    const drawn = withOneRowDown(healthy, { ...words, label: "no such scheduler" });
    expect(drawn).toEqual(healthy);
    expect(drawn.filter((row) => row.tone === "alert")).toHaveLength(0);
  });
});
