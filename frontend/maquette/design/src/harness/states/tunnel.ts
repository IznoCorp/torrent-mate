// The named states of the acquisition tunnel: what a card is waiting on, and
// the candidates screen it opens.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";
import { openAbandonConfirm } from "../../features/acquisition/abandon-verb";

// How long after « À traiter » is asked for its fold is opened: the read has to
// answer and the tab draw before there is a fold to open.
const OPEN_AFTER = 300;

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
      "Carte — l'échelle de ce qui est en vol (crans atteints par des lignes réelles)",
      () =>
        applyState({ page: "acq", acqTab: "now", scen: "loaded", phase: "ready" }),
    ],
    [
      "acq-card-blocked",
      "Carte — arrêtée sur « identifié », sa raison en entier",
      () =>
        applyState({ page: "acq", acqTab: "todo", scen: "real", phase: "ready" }),
    ],
    [
      "acq-card-no-identity",
      "Carte — un dossier sans identité",
      () =>
        applyState({ page: "acq", acqTab: "todo", scen: "real", phase: "ready" }),
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
        applyState({ page: "acq", acqTab: "todo", scen: "real", phase: "ready" }),
    ],
    [
      "acq-todo-empty",
      "À traiter — rien n'attend votre main",
      () => {
        window.__mocks?.clearBlocked();
        // THE RESET ALREADY ASKED FOR THE QUEUE, before the layer was emptied:
        // the answer it holds is dropped, so the page asks again.
        window.__queries?.removeQueries({ queryKey: ["/api/acquisition/to-handle"] });
        applyState({ page: "acq", acqTab: "todo", scen: "real", phase: "ready" });
      },
    ],
    [
      "acq-todo-loaded",
      "À traiter — chargé",
      () =>
        applyState({ page: "acq", acqTab: "todo", scen: "real", phase: "ready" }),
    ],
    [
      "acq-card-set-aside",
      "À traiter — une carte mise de côté, « Mis de côté » déplié",
      () => {
        // A REAL BLOCKED ROW, set aside the way « Laisser tel quel » sets it:
        // the tie on « Lucky » is a real pending decision.
        window.__mocks?.setAside("Lucky");
        window.__queries?.removeQueries({ queryKey: ["/api/acquisition/to-handle"] });
        applyState({ page: "acq", acqTab: "todo", scen: "real", phase: "ready" });
        // THE FOLD OPENED THE WAY A FINGER OPENS IT, once the tab is drawn.
        window.setTimeout(() => {
          document.querySelector<HTMLElement>('[data-part="section/set-aside"] summary')?.click();
        }, OPEN_AFTER);
      },
    ],
    [
      "acq-abandon-confirm",
      "À traiter — confirmation avant d'abandonner",
      () => {
        applyState({ page: "acq", acqTab: "todo", scen: "real", phase: "ready" });
        openAbandonConfirm("Top Chef Le Concours Parallèle (2026)");
      },
    ],
  ];
}
