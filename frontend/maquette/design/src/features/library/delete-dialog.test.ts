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
let followed: string[] = [];

vi.mock("../../lib/query-client", () => ({
  quietWhenCancelled: () => undefined,
  sharedQueryClient: { ensureQueryData: async () => undefined, getQueryData: () => undefined },
}));
vi.mock("../../lib/membership", () => ({ membershipQuery: (title: string) => ({ queryKey: [title] }) }));
vi.mock("../../lib/store-access", () => ({ store: { write: () => undefined } }));
vi.mock("./queries", () => ({
  libraryIncompleteQuery: { queryKey: ["incomplete"] },
  deleteLibraryItems: (titles: string[]) => removed.push(titles),
}));
vi.mock("../../lib/shell-doors", () => ({
  redraw: () => undefined,
  dialog: { open: (descriptor: DialogDescriptor) => opened.push(descriptor) },
  toast: { show: ({ message }: { message: string }) => said.push(message) },
  get followedTitles() {
    return () => followed;
  },
}));

const { openDeleteDialog } = await import("./delete-dialog");

/** Every sentence a descriptor says, whatever the block. */
function wordsOf(descriptor: DialogDescriptor): string[] {
  const words = [descriptor.heading, ...descriptor.actions.map((action) => action.text)];
  for (const block of descriptor.body) {
    if (block.type === "paragraph") words.push(...block.runs.map((run) => run.text));
    else if (block.type === "manifest") words.push(...block.entries.flatMap((e) => [e.text, e.value]));
    else if (block.type === "warning") words.push(block.strong, block.text);
    else if (block.type === "dryRun") words.push(block.text);
    else words.push(block.label);
  }
  return words;
}

const PRETENCE = /simulation|0 fichier|aurait|serait/i;

describe("the library's delete flow", () => {
  beforeEach(() => {
    opened.length = 0;
    said.length = 0;
    removed.length = 0;
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
      expect(descriptor.body.some((block) => block.type === "dryRun")).toBe(false);
      expect(wordsOf(descriptor).filter((w) => /simulation/i.test(w))).toEqual([]);
      for (const action of descriptor.actions.filter((a) => a.run)) {
        said.length = 0;
        removed.length = 0;
        action.run?.();
        expect(removed).toEqual([many ? [...many] : [title]]);
        expect(said.length).toBeGreaterThan(0);
        for (const message of said) expect(message).not.toMatch(PRETENCE);
      }
    });
  }

  it("names the title it removed", async () => {
    await openDeleteDialog("Les Animaniacs");
    opened[0].actions.find((a) => a.run)?.run?.();
    expect(said.at(-1)).toBe(i18next.t("verbs.library.delete.done", { title: "Les Animaniacs" }));
    expect(said.at(-1)).toContain("Les Animaniacs");
  });
});
