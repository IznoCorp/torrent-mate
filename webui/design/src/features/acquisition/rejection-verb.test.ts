// « Rejeter » and its « Annuler » are two writes, and what the view shows follows their answers.
//
// WHAT MAKES THIS NON-VACUOUS. Each case runs the act, then reads what left the interface (the
// method and the address), which positions the deck holds as spent and what was said. A card the
// server refused to reject must be back; an undone card the reserve no longer holds must be asked
// for again.
import { beforeEach, describe, expect, it, vi } from "vitest";
import i18next from "i18next";
import FRENCH from "../../i18n/fr.json";
import type { VerbOutcome } from "./verb-outcome";

await i18next.init({
  lng: "fr",
  resources: { fr: { translation: FRENCH } },
  interpolation: { escapeValue: false },
});

const sent: string[] = [];
const toasts: { message: string; undo?: () => void }[] = [];
const invalidated: unknown[] = [];
let answers: VerbOutcome<unknown>[] = [];
let reserve: { id: string; title: string }[] = [];
const state = { sugGone: new Set<number>() };

vi.mock("./verb-outcome", () => ({
  sendVerb: async (method: string, path: string) => {
    sent.push(`${method} ${path}`);
    return answers.shift() ?? { kind: "done", answer: { ok: true } };
  },
}));
vi.mock("../../lib/shell-doors", () => ({
  toast: { show: (shown: { message: string; undo?: () => void }) => toasts.push(shown) },
}));
vi.mock("../../lib/store-access", () => ({ store: { read: () => ({ state }), touch: () => undefined } }));
vi.mock("../../lib/query-client", () => ({
  sharedQueryClient: { invalidateQueries: async (filter: unknown) => void invalidated.push(filter) },
}));
vi.mock("./queries", () => ({
  suggestions: () => reserve,
  suggestionsQuery: { queryKey: ["/api/v1/acquisition/suggestions"] },
}));

const { rejectSuggestion } = await import("./rejection-verb");

const settle = () => new Promise((done) => setTimeout(done, 10));
const ADDRESS = "/api/v1/acquisition/suggestions/movie%3Atmdb%3A2/rejection";
const refusal = (code: string): VerbOutcome<unknown> =>
  ({ kind: "refused", failure: { status: 404, title: "t", detail: "d", code: code as never } });
let redrawn = 0;
const redraw = () => void (redrawn += 1);

beforeEach(() => {
  sent.length = 0;
  toasts.length = 0;
  invalidated.length = 0;
  answers = [];
  redrawn = 0;
  state.sugGone = new Set();
  reserve = [{ id: "movie:tmdb:1", title: "Un" }, { id: "movie:tmdb:2", title: "Deux" }];
});

describe("« Rejeter »", () => {
  it("spends the card in the tap's own task, writes the rejection and offers « Annuler »", async () => {
    const asked = rejectSuggestion(1, redraw);
    expect([...state.sugGone]).toEqual([1]);
    await asked;
    expect(sent).toEqual([`POST ${ADDRESS}`]);
    expect(toasts.map((one) => one.message)).toEqual(["« Deux » écarté."]); // french-ok: the rendered words this test asserts
    expect(toasts[0].undo).toBeTypeOf("function");
  });

  it("says the same of a rejection the outbox holds", async () => {
    answers = [{ kind: "held" }];
    await rejectSuggestion(1, redraw);
    expect(toasts.map((one) => one.message)).toEqual(["« Deux » écarté."]); // french-ok: the rendered words this test asserts
    expect([...state.sugGone]).toEqual([1]);
  });

  it("puts the card back and says why when the server refuses", async () => {
    answers = [refusal("suggestion.not_found")];
    await rejectSuggestion(1, redraw);
    expect([...state.sugGone]).toEqual([]);
    expect(redrawn).toBe(1);
    expect(toasts).toEqual([{ message: FRENCH.refusals.suggestion.not_found }]);
  });

  it("puts the card back when nothing could keep the write", async () => {
    answers = [{ kind: "failed" }];
    await rejectSuggestion(1, redraw);
    expect([...state.sugGone]).toEqual([]);
    expect(toasts).toEqual([{ message: FRENCH.verbs.acquisition.failed }]);
  });

  it("puts back the card of that id when the reserve moved while the server was answering", async () => {
    answers = [refusal("suggestion.not_found")];
    const asked = rejectSuggestion(1, redraw);
    reserve = [reserve[1]];
    state.sugGone = new Set([0]);
    await asked;
    expect([...state.sugGone]).toEqual([]);
  });
});

describe("« Annuler »", () => {
  it("brings the card back at once and deletes the rejection", async () => {
    await rejectSuggestion(1, redraw);
    toasts[0].undo?.();
    expect([...state.sugGone]).toEqual([]);
    // THE REDRAW IS WHAT PUTS THE CARD BACK ON SCREEN.
    expect(redrawn).toBe(1);
    await settle();
    expect(sent).toEqual([`POST ${ADDRESS}`, `DELETE ${ADDRESS}`]);
    expect(invalidated).toEqual([]);
  });

  it("finds the card by its id after the reserve moved", async () => {
    await rejectSuggestion(1, redraw);
    reserve = [reserve[1]];
    state.sugGone = new Set([0]);
    toasts[0].undo?.();
    expect([...state.sugGone]).toEqual([]);
  });

  it("asks for the deck again when the reserve no longer holds the card", async () => {
    await rejectSuggestion(1, redraw);
    reserve = [reserve[0]];
    state.sugGone = new Set();
    toasts[0].undo?.();
    await settle();
    expect(invalidated).toEqual([{ queryKey: ["/api/v1/acquisition/suggestions"] }]);
  });

  it("rejects the card again and says so when the undo is refused", async () => {
    await rejectSuggestion(1, redraw);
    answers = [refusal("suggestion.not_found")];
    toasts[0].undo?.();
    await settle();
    expect([...state.sugGone]).toEqual([1]);
    // Once to put the card back, once to take it away again.
    expect(redrawn).toBe(2);
    expect(toasts.at(-1)?.message).toBe(FRENCH.refusals.suggestion.not_found);
  });

  it("says a held undo of a card the reserve no longer holds", async () => {
    await rejectSuggestion(1, redraw);
    reserve = [reserve[0]];
    state.sugGone = new Set();
    answers = [{ kind: "held" }];
    toasts[0].undo?.();
    await settle();
    expect(toasts.at(-1)?.message).toBe(FRENCH.verbs.acquisition.held);
  });
});
