// The named states of the lots progress, a development page.
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
//
// THE PROGRESS IS NO OPERATION OF THE CONTRACT: the mock layer does not answer
// it, so a state poses the read's outcome in the query cache itself — the
// document, a read held in flight, or a read failed — and opens the screen.
import { applyState, type NamedState } from "../drive";
import { lotsKey, type LotsDocument } from "../../features/dev-lots/queries";
import { GENERATED_AT, SAMPLE_LOTS } from "./dev-lots-sample";

/** Long enough that a read held in flight is still in flight when the state is measured. */
const HELD = () => new Promise<never>(() => undefined);

/**
 * Poses the progress read's outcome, then opens the screen on it.
 *
 * @param pose What the read answers: the document, or a read that never lands or fails.
 */
function lotsWith(pose: { document: LotsDocument } | { read: () => Promise<never> }): void {
  applyState({ page: "sys", phase: "ready" });
  const queries = window.__queries;
  queries?.removeQueries({ queryKey: lotsKey });
  if ("document" in pose) {
    queries?.setQueryData(lotsKey, pose.document);
  } else {
    void queries?.prefetchQuery({ queryKey: lotsKey, queryFn: pose.read });
  }
  window.__screens.devLots();
}

export function devLotsStates(): NamedState[] {
  return [
    [
      "dev-lots",
      "Avancement des lots — un lot fini, un lot en cours dans chaque état, un lot bloqué",
      () => lotsWith({ document: SAMPLE_LOTS }),
    ],
    [
      "dev-lots-loading",
      "Avancement des lots — pendant la lecture",
      () => lotsWith({ read: HELD }),
    ],
    [
      "dev-lots-error",
      "Avancement des lots — la lecture en échec",
      () => lotsWith({ read: () => Promise.reject(new Error("/dev/lots.json answered 500")) }),
    ],
    [
      "dev-lots-unavailable",
      "Avancement des lots — rien n'est publié sur cet hôte",
      () => lotsWith({ document: { available: false } }),
    ],
    [
      "dev-lots-none",
      "Avancement des lots — aucun lot défini",
      () => lotsWith({ document: { available: true, generatedAt: GENERATED_AT, lots: [] } }),
    ],
  ];
}
