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
import { baseTitle } from "../../lib/titles";
import { followVerbs } from "./follow-verbs";
import { searchResults } from "./search-queries";

/** The positions of the results this screen has already acted on. */
function added(): Set<number> {
  return store.read().state.added as Set<number>;
}

/**
 * Associates the folder the screen was opened for with the result tapped.
 *
 * The stuck folder becomes this medium and the pipeline resumes; no follow is
 * created, because that was not the request.
 *
 * ONE SETTLEMENT FOR THE TWO ENTRIES THIS JOURNEY STACKED — the result's panel
 * and `/add` itself. The panel is ASKED before it is closed, because its own
 * entry decides the count, and it is closed without unwinding (`close(true)`):
 * its unwind plus a second back were two backs racing in one task, and the
 * surplus pop was read as the operator's own back gesture.
 *
 * Args:
 *     index: The result's position in the list.
 *     title: The result's title.
 */
function identify(index: number, title: string): void {
  const target = (store.read().state.resolveTarget as string | null) ?? "";
  added().add(index);
  store.touch();
  const entries = (panel.isOpen() ? 1 : 0) + 1;
  panel.close(true);
  bridge.rewind(entries);
  queueActions?.resolve(target, title);
  redraw();
  toast?.show({ message: i18next.t("verbs.arrivals.resolved", { choice: title }) });
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

// THE DECLARATION RUNS AT MODULE EVALUATION, named once in
// `app/panel-contributions.ts`.
registerVerb("add", (value) => {
  const index = Number(value);
  const result = searchResults?.().results[index];
  if (result === undefined) return;
  if (store.read().state.addMode === "identify") {
    identify(index, result.title);
    return;
  }
  // The act lives in the result's panel, which must not stay open behind
  // what comes next — the confirmation, or the list redrawn in place.
  panel.close();
  if (result.owned) {
    askBeforeReplace(index, result.title, result.kind === "Film"); // french-ok: a data VALUE — the kind the search serves
    return;
  }
  // The screen stays open and redraws itself from this same store bump,
  // with the result marked added and, once it is the first, the footer.
  added().add(index);
  store.touch();
  followVerbs.follow(result.title, result.kind);
});
registerVerb("confirmadd", (value) => {
  added().add(Number(value));
  store.touch();
  dialog?.close();
  toast?.show({ message: i18next.t("verbs.acquisition.replacementQueued") });
});
