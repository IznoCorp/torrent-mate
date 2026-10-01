// The named states of the media screen.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";

/** Opens a medium's sheet the way a tap on its card does: with what the card knew. */
const open = (title: string) => window.__screens.mediaSheet(title, window.__carriedFor(title) ?? undefined);

// How long « Corriger » is waited for once the sheet is asked: past it the act is
// not tapped and the state shows the sheet it reached.
const CORRECT_WAIT = 3000;

/**
 * Taps « Corriger » on the frame its decision block is drawn, the way a finger
 * taps it once it is there.
 *
 * AT THE FRAME, NOT AFTER A DELAY. A fixed 900ms let the sheet's own arrival
 * finish and the page fall still BEFORE the tap, so a reading taken in that
 * quiet gap took the half-built state for the state, and the tap's navigation
 * then ran its view transition over a page already judged settled — during
 * which the platform routes every hit to the document, so the way back read
 * as covered (desktop_frame.py, run 36796058216). Tapped as soon as it exists
 * (~50–90ms, inside the sheet's own transition), the second navigation follows
 * the first with no still frame between them.
 */
function correctWhenDrawn(): void {
  const started = performance.now();
  const look = () => {
    const act = document.querySelector<HTMLElement>('[data-part="decision/correct"]');
    if (act !== null) act.click();
    else if (performance.now() - started < CORRECT_WAIT) window.requestAnimationFrame(look);
  };
  look();
}

export function mediaStates(): NamedState[] {
  return [
    [
      "media-sheet-decision-corrected",
      "Fiche — « Corriger » sur un média rangé : l'arbitrage rouvert",
      () => {
        window.__mocks?.reset();
        applyState({ page: "lib", phase: "ready" });
        open("The Bombing of Pan Am 103");
        correctWhenDrawn();
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
