// B-614: a torrent's panel says each fact once — its label, then its value, never the label again.
import { describe, expect, it } from "vitest";
import "../../lib/unit-words";
import DOWNLOADS from "../../mocks/seeds/downloads.json";
import { factsOf } from "./panel-torrent";
import type { Download } from "./queries";

const entries = DOWNLOADS as unknown as Download[];

describe("a torrent's facts", () => {
  it("never repeat their label in their value (« Ajouté le · Ajouté le 1 octobre »)", () => {
    // THE SEED DATES NO ENTRY; a published one is dated at its publication (L23), so one is dated here.
    const [entry] = entries;
    for (const one of [{ ...entry, addedAt: 1790812800 }, { ...entry, addedAt: null }]) {
      for (const line of factsOf(one, undefined)) {
        expect(line.v.toLowerCase().startsWith(line.c.toLowerCase()), `${line.c} · ${line.v}`).toBe(false);
      }
    }
  });
});
