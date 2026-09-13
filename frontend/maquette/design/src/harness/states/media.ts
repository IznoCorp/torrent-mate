// The named states of the media screen.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label is what the ≡ panel shows, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";

/** Opens a medium's sheet the way a tap on its card does: with what the card knew. */
const open = (title: string) => window.__screens.mediaSheet(title, window.__carriedFor(title) ?? undefined);

export function mediaStates(): NamedState[] {
  return [
    [
      "mediasheet-suggestion-series",
      "Fiche — suggestion NON possédée (série)",
      () => {
        applyState({ page: "acq", acqTab: "discover", phase: "ready" });
        open("The Venture Bros");
      },
    ],
    [
      "mediasheet-suggestion-movie",
      "Fiche — suggestion NON possédée (film)",
      () => {
        applyState({ page: "acq", acqTab: "discover", phase: "ready" });
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
