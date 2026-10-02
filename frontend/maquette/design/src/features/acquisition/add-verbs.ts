// THE ADD SCREEN'S VERBS: a search result's act, and the replacement it may
// ask to confirm.
//
// THE ACT CARRIES THE LIST POSITION, not the title: a search can return the
// same title twice — « Star Wars : The Clone Wars » is both a film and a series
// — so the title does not identify the result.
import i18next from "i18next";
import { registerVerb } from "../../lib/verbs";
import { queueActions } from "../../lib/queue";
import { bridge, dialog, panel, toast, redraw } from "../../lib/shell-doors";
import { store } from "../../lib/store-access";
import { addressSeam } from "../../lib/addresses";
import { entriesAbovePage } from "../../lib/navigation-entry";
import { baseTitle } from "../../lib/titles";
import { followVerbs } from "./follow-verbs";
import { searchResults } from "./search-queries";
import { identifying, markAdded, forgetAdded } from "./add-visit";
import { answerMatch, heldMatch } from "./plex-verbs";
import { idQuery, type IdProvider } from "./id-examples";
import { read } from "../../lib/query-client";
import type { SearchResult, SearchResults } from "./types";


/**
 * Associates the folder the screen was opened for with the result tapped.
 *
 * The stuck folder becomes this medium and the pipeline resumes; no follow is
 * created, because that was not the request.
 *
 * ONE SETTLEMENT FOR THE ENTRIES THIS JOURNEY STACKED — the result's panel,
 * `/add` itself and the arbitration it was opened over: everything above the
 * page is given back, so the list comes back as a pick in the arbitration
 * brings it back (09-15 Q4). The count is read BEFORE the panel is closed, and
 * the panel is closed without unwinding (`close(true)`):
 * its unwind plus a second back were two backs racing in one task, and the
 * surplus pop was read as the operator's own back gesture.
 *
 * Args:
 *     result: The search result tapped.
 */
function identify(result: SearchResult): void {
  const title = result.title;
  const target = (store.read().state.resolveTarget as string | null) ?? "";
  markAdded(result);
  store.touch();
  const entries = entriesAbovePage(addressSeam.homePage, String(store.read().state.page));
  panel.close(true);
  bridge.rewind(entries);
  // A PLEX MATCH IS CORRECTED by the identity found here, sent with it.
  if (heldMatch(target) !== null) {
    void answerMatch("correct", target, { title, ids: result.ids ?? null });
    return;
  }
  queueActions?.resolve(target, title);
  redraw();
  toast?.show({ message: i18next.t("verbs.acquisition.resolved", { choice: title }) });
  toast?.show({
    message: i18next.t("verbs.acquisition.identified", { target: baseTitle(target), title }),
  });
}

/**
 * Asks before an acquisition replaces a medium already in the library.
 *
 * Args:
 *     index: The result's position, carried by the confirmation's own act.
 *     title: The result's title.
 *     isMovie: Whether the result is a film, which names it in the question.
 */
function askBeforeReplace(index: number, title: string, isMovie: boolean): void {
  const say = (key: string, options?: Record<string, string>) =>
    i18next.t(`verbs.acquisition.${key}`, options);
  dialog?.open({
    heading: say("replaceHeading", { title }),
    body: [
      {
        type: "paragraph",
        runs: [
          { text: say(isMovie ? "replaceMovieOwned" : "replaceMediumOwned") },
          { text: say("replaceEmphasis"), strong: true },
          { text: say("replaceAfter") },
        ],
      },
    ],
    actions: [
      { text: say("replace"), tone: "danger", target: { "data-confirmadd": String(index) } },
      { text: say("replaceCancel"), tone: "ghost", dismiss: true },
    ],
  });
}

/**
 * Follows a result, marking it added before the layer answers and taking the
 * mark back if the layer refuses.
 *
 * Args:
 *     result: The result to follow.
 */
function followResult(result: SearchResult): void {
  // The screen stays open and redraws itself from this same store bump,
  // with the result marked added and, once it is the first, the footer.
  //
  // AND THE MARK IS TAKEN BACK IF THE LAYER REFUSES. It is written here, before
  // anything is known, which is what the optimistic list beside it does; what
  // was missing is the other half — a row left wearing « ✓ Suivi » over a
  // create the layer rejected, which is a claim the interface has no right to
  // make. The act answers whether it stood, and the visit learns from it.
  markAdded(result);
  store.touch();
  void followVerbs.follow(result.title, result.kind, result.ids)
    .then((stood) => {
      if (stood) return;
      forgetAdded(result);
      store.touch();
    });
}

/** What an identifier typed came to: added, known to no source, or already owned. */
export type IdOutcome = { kind: "added" } | { kind: "missing" } | { kind: "owned"; title: string };

/**
 * Adds the medium a source knows under an identifier (B-691).
 *
 * The provider search is asked for the identifier; the medium it answers is followed
 * as a tapped result is — or identifies the folder, when the screen was opened
 * for one. A medium already owned is not replaced from here: a replacement is
 * confirmed on its own row, which a search by its title draws.
 *
 * Args:
 *     provider: The source chosen.
 *     id: The identifier typed, in that source's format.
 *
 * Returns:
 *     What the identifier came to.
 */
export async function addById(provider: IdProvider, id: string): Promise<IdOutcome> {
  const answer = await read<SearchResults>("/api/acquisition/search/by-id", idQuery(provider, id));
  const result = answer.results[0];
  if (result === undefined) return { kind: "missing" };
  if (identifying()) {
    identify(result);
    return { kind: "added" };
  }
  if (result.owned) return { kind: "owned", title: result.title };
  followResult(result);
  return { kind: "added" };
}

// THE DECLARATION RUNS AT MODULE EVALUATION, named once in
// `app/panel-contributions.ts`.
registerVerb("add", (value) => {
  const index = Number(value);
  const result = searchResults?.().results[index];
  if (result === undefined) return;
  if (identifying()) {
    identify(result);
    return;
  }
  // The act lives in the result's panel, which must not stay open behind
  // what comes next — the confirmation, or the list redrawn in place.
  panel.close();
  if (result.owned) {
    askBeforeReplace(index, result.title, result.kind === "Film"); // french-ok: a data VALUE — the kind the search serves
    return;
  }
  followResult(result);
});
registerVerb("confirmadd", (value) => {
  const result = searchResults?.().results[Number(value)];
  if (result !== undefined) markAdded(result);
  store.touch();
  dialog?.close();
  toast?.show({ message: i18next.t("verbs.acquisition.replacementQueued") });
});
