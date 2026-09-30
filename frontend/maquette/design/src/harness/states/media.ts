// The named states of the media screen.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";

/** Opens a medium's sheet the way a tap on its card does: with what the card knew. */
const open = (title: string) => window.__screens.mediaSheet(title, window.__carriedFor(title) ?? undefined);

// How long after the sheet is asked for « Corriger » is tapped: the sheet and its
// decision read have to answer first.
const CORRECT_AFTER = 900;

export function mediaStates(): NamedState[] {
  return [
    [
      "media-sheet-decision-corrected",
      "Fiche — « Corriger » sur un média rangé : l'arbitrage rouvert",
      () => {
        window.__mocks?.reset();
        applyState({ page: "lib", phase: "ready" });
        open("The Bombing of Pan Am 103");
        window.setTimeout(() => {
          document.querySelector<HTMLElement>('[data-part="decision/correct"]')?.click();
        }, CORRECT_AFTER);
      },
    ],
    [
      "media-sheet-decision",
      "Fiche — l'identification réglée d'un média rangé",
      () => {
        window.__mocks?.reset();
        applyState({ page: "lib", phase: "ready" });
        open("The Bombing of Pan Am 103");
      },
    ],
    [
      "mediasheet-suggestion-series",
      "Fiche — suggestion NON possédée (série)",
      () => {
        applyState({ page: "discover", phase: "ready" });
        open("The Venture Bros");
      },
    ],
    [
      "mediasheet-suggestion-movie",
      "Fiche — suggestion NON possédée (film)",
      () => {
        applyState({ page: "discover", phase: "ready" });
        open("Superman : L'Homme de demain");
      },
    ],
    [
      "mediasheet-series",
      "Fiche — série avec épisodes datés",
      () => {
        applyState({ page: "lib", phase: "ready" });
        open("Silo (2023)");
      },
    ],
    [
      "mediasheet-movie",
      "Fiche — film",
      () => {
        applyState({ page: "lib", phase: "ready" });
        open("Marjorie Prime");
      },
    ],
    [
      "mediasheet-no-trailer",
      "Fiche — sans bande-annonce",
      () => {
        applyState({ page: "lib", phase: "ready" });
        open("Broadchurch");
      },
    ],
    [
      "mediasheet-no-poster",
      "Fiche — sans affiche",
      () => {
        applyState({ page: "lib", phase: "ready" });
        open("Widow's Bay");
      },
    ],
  ];
}
