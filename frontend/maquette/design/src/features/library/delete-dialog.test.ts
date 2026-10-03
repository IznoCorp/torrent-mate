// B-679: the delete flow says what production will say — never « simulation ».
//
// WHAT MAKES THIS NON-VACUOUS. The words are read from what the dialog is handed
// (`dialog.open`) and what the toast is handed (`toast.show`) after the confirming
// action RUNS, for the three confirmations (one title, a followed title, a
// selection); the removal itself is the layer's, asked with the titles.
import { beforeEach, describe, expect, it, vi } from "vitest";
import i18next from "../../lib/unit-words";
import type { DialogDescriptor } from "../../ui/dialog/contract";

const opened: DialogDescriptor[] = [];
const said: string[] = [];
const removed: string[][] = [];
// THE ROWS EACH IDENTITY NAMES, as the membership read would answer: two for
// the seed's duplicate, none for a title nothing identifies.
const ROWS: Record<string, number> = { "Doctor Who": 2 };
const UNIDENTIFIED = new Set(["Famille Pirate"]);
const stopped: string[] = [];
let followed: string[] = [];

vi.mock("../../lib/query-client", () => ({
  quietWhenCancelled: () => undefined,
  sharedQueryClient: {
    ensureQueryData: async () => undefined,
    getQueryData: (key: string[]) => (key[0] in ROWS ? { rows: ROWS[key[0]] } : undefined),
  },
}));
vi.mock("../../lib/membership", () => ({
  membershipQuery: (title: string) => ({ queryKey: [title] }),
  membershipByRefQuery: (ref: { providerId: string }) => ({ queryKey: ["ref", ref.providerId] }),
  identityOfTitle: async (title: string) => (UNIDENTIFIED.has(title) ? null : { provider: "tvdb", providerId: `id-${title}` }),
}));
vi.mock("../../lib/store-access", () => ({ store: { write: () => undefined } }));
vi.mock("./queries", () => ({
  libraryIncompleteQuery: { queryKey: ["incomplete"] },
  // The titles the layer was asked to delete, each with the identity it was drawn with.
  deleteLibraryItems: (doomed: { title: string; ref: { providerId: string } }[]) => {
    for (const one of doomed) expect(one.ref.providerId).toBe(`id-${one.title}`);
    removed.push(doomed.map((one) => one.title));
  },
}));
vi.mock("../../lib/shell-doors", () => ({
  redraw: () => undefined,
  dialog: { open: (descriptor: DialogDescriptor) => opened.push(descriptor) },
  toast: { show: ({ message }: { message: string }) => said.push(message) },
  get followedTitles() {
    return () => followed;
  },
  stopFollow: (title: string) => stopped.push(title),
}));

const { openDeleteDialog } = await import("./delete-dialog");

/** Every sentence a descriptor says, whatever the block. */
function wordsOf(descriptor: DialogDescriptor): string[] {
  const words = [descriptor.heading, ...descriptor.actions.map((action) => action.text)];
  for (const block of descriptor.body) {
    if (block.type === "paragraph") words.push(...block.runs.map((run) => run.text));
    else if (block.type === "manifest") words.push(...block.entries.flatMap((e) => [e.text, e.value]));
    else if (block.type === "warning") words.push(block.strong, block.text);
    else words.push(block.label);
  }
  return words;
}

const FORBIDDEN_WORDS = /simulation|0 fichier|aurait|serait/i;

describe("the library's delete flow", () => {
  beforeEach(() => {
    opened.length = 0;
    said.length = 0;
    removed.length = 0;
    stopped.length = 0;
    followed = [];
  });

  for (const [label, title, many, followedNow] of [
    ["one title", "Les Animaniacs", undefined, []],
    ["a followed title", "Silo", undefined, ["Silo"]],
    ["a selection", null, ["Les Animaniacs", "Silo"], ["Silo"]],
  ] as const) {
    it(`pretends nothing before or after the act — ${label}`, async () => {
      followed = [...followedNow];
      await openDeleteDialog(title, many ? [...many] : undefined);
      const descriptor = opened[0];
      expect(wordsOf(descriptor).filter((w) => /simulation/i.test(w))).toEqual([]);
      for (const action of descriptor.actions.filter((a) => a.run)) {
        said.length = 0;
        removed.length = 0;
        action.run?.();
        expect(removed).toEqual([many ? [...many] : [title]]);
        expect(said.length).toBeGreaterThan(0);
        for (const message of said) expect(message).not.toMatch(FORBIDDEN_WORDS);
      }
    });
  }

  // B-689: « Supprimer et arrêter le suivi » said the follow stopped and stopped
  // nothing — both confirmations removed the same titles and differed only in
  // the sentence, so the sheet went on reading « Suivi : actif ». The follow is
  // stopped under ITS title (« Silo »), which is not the row's (« Silo (2023) »).
  it("stops the follow it says it stops, and keeps the one it says it keeps", async () => {
    followed = ["Silo"];
    await openDeleteDialog("Silo (2023)");
    const [stop, keep] = opened[0].actions.filter((action) => action.run);
    expect(stop.text).toBe(i18next.t("verbs.library.delete.deleteAndStop"));
    stop.run?.();
    expect(stopped).toEqual(["Silo"]);
    expect(removed).toEqual([["Silo (2023)"]]);

    stopped.length = 0;
    keep.run?.();
    expect(stopped).toEqual([]);
  });

  it("stops every follow of a selection, and nothing that is not followed", async () => {
    followed = ["Silo", "Furious"];
    await openDeleteDialog(null, ["Silo (2023)", "Les Animaniacs", "Furious (2026)"]);
    opened[0].actions.find((action) => action.run)?.run?.();
    expect(stopped).toEqual(["Silo", "Furious"]);
  });

  it("names the title it removed", async () => {
    await openDeleteDialog("Les Animaniacs");
    opened[0].actions.find((a) => a.run)?.run?.();
    expect(said.at(-1)).toBe(i18next.t("verbs.library.delete.done", { title: "Les Animaniacs" }));
    expect(said.at(-1)).toContain("Les Animaniacs");
  });

  // O-5 B: an identity two library rows hold is not deleted until the duplicate
  // is settled — the dialog names it and offers nothing but to close.
  it("refuses a duplicated identity before anything is offered", async () => {
    await openDeleteDialog("Doctor Who");
    const descriptor = opened[0];
    expect(descriptor.heading).toBe(i18next.t("verbs.library.delete.blockedHeadingOne", { title: "Doctor Who" }));
    expect(descriptor.actions.filter((action) => action.run)).toEqual([]);
    expect(wordsOf(descriptor)).toContain(i18next.t("verbs.library.delete.heldByRows", { count: 2 }));
    expect(removed).toEqual([]);
  });

  it("refuses a selection holding a duplicate, naming only what cannot go", async () => {
    await openDeleteDialog(null, ["Les Animaniacs", "Doctor Who", "Famille Pirate"]);
    const entries = opened[0].body.flatMap((block) => (block.type === "manifest" ? block.entries.map((e) => e.text) : []));
    expect(entries).toEqual(["Doctor Who", "Famille Pirate"]);
    expect(opened[0].actions.filter((action) => action.run)).toEqual([]);
  });
});
