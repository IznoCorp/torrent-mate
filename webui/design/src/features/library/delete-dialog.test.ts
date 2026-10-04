// B-679: the delete flow says what production will say — never « simulation ».
//
// WHAT MAKES THIS NON-VACUOUS. The words are read from what the dialog is handed
// (`dialog.open`) and what the toast is handed (`toast.show`) after the confirming
// action RUNS, for the three confirmations (one title, a followed title, a
// selection); the removal itself is the layer's, asked with each row's identity.
import { beforeEach, describe, expect, it, vi } from "vitest";
import i18next from "../../lib/unit-words";
import type { DialogDescriptor } from "../../ui/dialog/contract";
import type { MediaRef } from "../../lib/membership";

const opened: DialogDescriptor[] = [];
const said: string[] = [];
const removed: string[][] = [];
const removedRefs: string[][] = [];
// THE ROWS EACH IDENTITY NAMES, as the membership read by ref would answer: two
// for the seed's duplicate, none for an identity the library no longer holds.
const ROWS: Record<string, number> = { "tvdb:78804": 2, "tvdb:gone": 0 };
const stopped: string[] = [];
let followed: string[] = [];

vi.mock("../../lib/query-client", () => ({
  quietWhenCancelled: () => undefined,
  sharedQueryClient: {
    ensureQueryData: async () => undefined,
    getQueryData: (key: string[]) =>
      key[0] === "ref" ? { rows: ROWS[key[1]] ?? 1, inLibrary: (ROWS[key[1]] ?? 1) > 0 } : undefined,
  },
}));
vi.mock("../../lib/membership", () => ({
  membershipByRefQuery: (ref: MediaRef) => ({ queryKey: ["ref", `${ref.provider}:${ref.providerId}`] }),
}));
vi.mock("../../lib/store-access", () => ({ store: { write: () => undefined } }));
vi.mock("./queries", () => ({
  libraryIncompleteQuery: { queryKey: ["incomplete"] },
  // The media the layer was asked to delete, each by the identity its row carried.
  deleteLibraryItems: (doomed: { title: string; ref: MediaRef }[]) => {
    removed.push(doomed.map((one) => one.title));
    removedRefs.push(doomed.map((one) => `${one.ref.provider}:${one.ref.providerId}`));
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

/** A medium a row was drawn with: its title and an identity of its own. */
function row(title: string, providerId = `id-${title}`, provider = "tvdb") {
  return { title, ref: { provider, providerId } as MediaRef };
}

/** The doomed media of a list of titles, each under its own identity. */
function rows(...titles: string[]) {
  return titles.map((title) => row(title));
}

/** Doctor Who, the seed's duplicate: two rows, one TVDB id. */
const DUPLICATE = row("Doctor Who", "78804");

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
    removedRefs.length = 0;
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
      await openDeleteDialog(rows(...(many ?? [title as string])));
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
    await openDeleteDialog(rows("Silo (2023)"));
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
    await openDeleteDialog(rows("Silo (2023)", "Les Animaniacs", "Furious (2026)"));
    opened[0].actions.find((action) => action.run)?.run?.();
    expect(stopped).toEqual(["Silo", "Furious"]);
  });

  it("names the title it removed", async () => {
    await openDeleteDialog(rows("Les Animaniacs"));
    opened[0].actions.find((a) => a.run)?.run?.();
    expect(said.at(-1)).toBe(i18next.t("verbs.library.delete.done", { title: "Les Animaniacs" }));
    expect(said.at(-1)).toContain("Les Animaniacs");
  });

  // O-5 B: an identity two library rows hold is not deleted until the duplicate
  // is settled — the dialog names it and offers nothing but to close.
  it("refuses a duplicated identity before anything is offered", async () => {
    await openDeleteDialog([DUPLICATE]);
    const descriptor = opened[0];
    expect(descriptor.heading).toBe(i18next.t("verbs.library.delete.blockedHeadingOne", { title: "Doctor Who" }));
    expect(descriptor.actions.filter((action) => action.run)).toEqual([]);
    expect(wordsOf(descriptor)).toContain(i18next.t("verbs.library.delete.heldByRows", { count: 2 }));
    expect(removed).toEqual([]);
  });

  it("refuses a selection holding a duplicate, naming only what cannot go", async () => {
    await openDeleteDialog([row("Les Animaniacs"), DUPLICATE, row("Silo")]);
    const entries = opened[0].body.flatMap((block) => (block.type === "manifest" ? block.entries.map((e) => e.text) : []));
    expect(entries).toEqual(["Doctor Who"]);
    expect(opened[0].actions.filter((action) => action.run)).toEqual([]);
  });

  // Every library entry is identified (the operator, 2026-10-03): an identity
  // the library no longer holds is said as the layer refuses it.
  it("says a medium the library no longer holds is unknown, and offers nothing", async () => {
    await openDeleteDialog([row("Gone Title", "gone")]);
    expect(opened).toEqual([]);
    expect(said).toEqual([i18next.t("refusals.media.not_found")]);
    expect(removed).toEqual([]);
  });

  // TWO MEDIA, ONE TITLE: « RoboCop » 1987 (TMDB 5548) and 2014 (TMDB 97020).
  // Each id is held by one row, so nothing is ambiguous — and the removal of
  // the 2014 row names TMDB 97020, never the medium the title found first.
  it("deletes the one of two media sharing a title that its row names", async () => {
    await openDeleteDialog([row("RoboCop", "97020", "tmdb")]);
    expect(opened[0].actions.filter((action) => action.run)).toHaveLength(1);
    opened[0].actions.find((action) => action.run)?.run?.();
    expect(removedRefs).toEqual([["tmdb:97020"]]);
  });

  it("deletes both of two media sharing a title when both rows are ticked, each by its own id", async () => {
    await openDeleteDialog([row("RoboCop", "5548", "tmdb"), row("RoboCop", "97020", "tmdb")]);
    expect(opened[0].heading).toBe(i18next.t("verbs.library.delete.headingMany", { media: 2 }));
    opened[0].actions.find((action) => action.run)?.run?.();
    expect(removedRefs).toEqual([["tmdb:5548", "tmdb:97020"]]);
  });
});
