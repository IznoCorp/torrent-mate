// The named states of the media screen.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label is what the ≡ panel shows, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";

export function mediaStates(): NamedState[] {
  return [
    [
      "mediasheet-suggestion-series",
      "Fiche — suggestion NON possédée (série)",
      () => {
        applyState({ page: "acq", acqTab: "discover", phase: "ready" });
        window.__screens.mediaSheet("The Venture Bros");
      },
    ],
    [
      "mediasheet-suggestion-movie",
      "Fiche — suggestion NON possédée (film)",
      () => {
        applyState({ page: "acq", acqTab: "discover", phase: "ready" });
        window.__screens.mediaSheet("Superman : L'Homme de demain");
      },
    ],
    [
      "mediasheet-series",
      "Fiche — série avec épisodes datés",
      () => {
        applyState({ page: "lib", phase: "ready" });
        window.__screens.mediaSheet("Silo (2023)");
      },
    ],
    [
      "mediasheet-movie",
      "Fiche — film",
      () => {
        applyState({ page: "lib", phase: "ready" });
        window.__screens.mediaSheet("Marjorie Prime");
      },
    ],
    [
      "mediasheet-no-trailer",
      "Fiche — sans bande-annonce",
      () => {
        applyState({ page: "lib", phase: "ready" });
        window.__screens.mediaSheet("Broadchurch");
      },
    ],
    [
      "mediasheet-no-poster",
      "Fiche — sans affiche",
      () => {
        applyState({ page: "lib", phase: "ready" });
        window.__screens.mediaSheet("Widow's Bay");
      },
    ],
  ];
}
