// The named states of « À traiter » holding every block (Q7, Q8, Q9) — the
// maquette-blocked lot's own file (its DESIGN § 0.1 item 11: `tunnel.ts` is
// near its ceiling).
//
// Each entry is `[id, label, run]`, as every state file's. A block is a
// DERIVATION, SHOWN AS ONE: no real card is stopped by an external cause, so
// the cause is posed (`poseBlock`) on a real acquisition, and the backend
// serves it (BK1).
import { applyState, type NamedState } from "../drive";
import type { BlockDetails } from "../../mocks/handlers/posed-block";

// The one acquisition in flight of the dense world that has not arrived: the
// subject of every deferral since R265.
const SUBJECT = "This City Is Ours";

/**
 * The queue's reads dropped, so the next draw reads what was just posed.
 */
function dropQueue(): void {
  window.__queries?.removeQueries({ queryKey: ["/api/acquisition/to-handle"] });
  window.__queries?.removeQueries({ queryKey: ["/api/staging/media"] });
}

/**
 * One state: a block posed on one acquisition, « À traiter » drawn.
 *
 * @param id The state's id.
 * @param label What it shows, in words.
 * @param poses The blocks it poses: title, cause, details.
 * @returns The named state.
 */
function posed(id: string, label: string, poses: [string, string, BlockDetails?][]): NamedState {
  return [id, label, () => {
    window.__mocks?.reset();
    for (const [title, cause, details] of poses) window.__mocks?.poseBlock(title, cause, details);
    dropQueue();
    applyState({ page: "acq", acqTab: "todo", scen: "loaded", phase: "ready" });
  }];
}

export function blockedStates(): NamedState[] {
  return [
    // MOVED (Q7): the deferred card leaves « En cours » for « À traiter », ids kept.
    posed("acq-card-deferred-ratio",
      "À traiter — un torrent terminé différé pour ratio sous le seuil de c411, POSÉ sur This City Is Ours (le back-end servira la cause — BK1)",
      [[SUBJECT, "ratio_below_threshold", { tracker: "c411" }]]),
    posed("acq-card-deferred-space",
      "À traiter — un torrent terminé différé faute d'espace sur le disque de staging, POSÉ sur This City Is Ours",
      [[SUBJECT, "insufficient_space"]]),
    posed("acq-card-deferred-missing",
      "À traiter — un torrent terminé différé, le disque où qBittorrent l'a téléchargé illisible, POSÉ sur This City Is Ours",
      [[SUBJECT, "content_missing"]]),
  ];
}
