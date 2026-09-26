// The named states of the acquisition tunnel: what a card is waiting on, and
// the candidates screen it opens.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";

export function tunnelStates(): NamedState[] {
  return [
    [
      "acq-resolution-none",
      "Arrivées — résolution, aucun candidat",
      () => {
        applyState({ page: "arr", phase: "ready", pipe: "idle" });
        window.__screens.resolution();
      },
    ],
    [
      "acq-resolution-tie",
      "Arrivées — résolution, candidats à égalité",
      () => {
        applyState({
          page: "arr",
          scen: "loaded",
          phase: "ready",
          pipe: "idle",
        });
        window.__screens.resolution("Lucky");
      },
    ],
    [
      "acq-card-rungs",
      "Carte — l'échelle de chaque famille (six crans atteints par des lignes réelles)",
      () =>
        applyState({ page: "acq", acqTab: "now", scen: "loaded", phase: "ready" }),
    ],
    [
      "acq-card-blocked",
      "Carte — arrêtée sur « identifié », sa raison en entier",
      () =>
        applyState({ page: "acq", acqTab: "now", scen: "real", phase: "ready" }),
    ],
    [
      "acq-card-no-identity",
      "Carte — un dossier sans identité",
      () =>
        applyState({ page: "acq", acqTab: "now", scen: "real", phase: "ready" }),
    ],
    [
      "acq-card-waiting",
      "Carte — en file derrière une maintenance",
      () =>
        applyState({ page: "acq", acqTab: "now", scen: "loaded", phase: "ready", pipe: "queued" }),
    ],
    [
      "acq-card-requester",
      "Carte — ajouté par Izno, dans qBittorrent",
      () =>
        applyState({ page: "acq", acqTab: "now", scen: "real", phase: "ready" }),
    ],
    [
      "acq-todo-empty",
      "À traiter — rien n'attend votre main",
      () =>
        applyState({ page: "acq", acqTab: "todo", scen: "real", phase: "ready" }),
    ],
  ];
}
