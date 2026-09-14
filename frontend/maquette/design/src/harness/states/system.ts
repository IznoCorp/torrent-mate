// The named states of the machine's page, « Système ».
//
// Each entry is `[id, label, run]`: the id is what `window.__go(id)` takes and
// what the oracle's reference names, the label says the state in words, and
// `run` builds the state. The driver resets the interface before every state,
// so an entry pins only what its state means to show.
import { applyState, type NamedState } from "../drive";

// THE PIPELINE'S STATES JOIN THIS TABLE ONE SURFACE AT A TIME. The global
// levers, the veille, the locks, the passages and a passage's detail add their
// named states here in the commit that draws the surface behind each id —
// never earlier, because `harness/states.py` fails an id that renders nothing.
export function systemStates(): NamedState[] {
  return [
    [
      "system",
      "Système — la santé de la machine",
      () => applyState({ page: "sys", phase: "ready", fault: false }),
    ],
    [
      "system-outage",
      "Système — une panne (simulée)",
      () => applyState({ page: "sys", phase: "ready", fault: true }),
    ],
    [
      "system-loading",
      "Système — chargement",
      () => applyState({ page: "sys", phase: "loading", fault: false }),
    ],
    [
      "system-error",
      "Système — erreur",
      () => applyState({ page: "sys", phase: "error", fault: false }),
    ],
    [
      "locks-free",
      "Verrous — tout est libre",
      () => {
        // THE RESET FIRST, always: a lock left held by whatever state was
        // driven before would make this one show the opposite of its name.
        window.__mocks?.reset();
        window.__mocks?.setTmpOrphans(false);
        applyState({ page: "sys", phase: "ready", fault: false });
      },
    ],
    [
      "locks-held",
      "Verrous — le pipeline tient le verrou",
      () => {
        window.__mocks?.reset();
        window.__mocks?.setPipelineState("running");
        window.__mocks?.setTmpOrphans(false);
        applyState({ page: "sys", phase: "ready", fault: false });
      },
    ],
    [
      "locks-stale",
      "Verrous — verrou obsolète",
      () => {
        // THE FILE OUTLIVED ITS PROCESS, which no verb of the layer produces:
        // it is what a crash leaves, so it is turned on as a fact rather than
        // asked for as an operation.
        window.__mocks?.reset();
        window.__mocks?.setLockStale(true);
        window.__mocks?.setTmpOrphans(false);
        applyState({ page: "sys", phase: "ready", fault: false });
      },
    ],
    [
      "locks-sweep-pending",
      "Verrous — le balayage n'a pas fini",
      () => {
        window.__mocks?.reset();
        window.__mocks?.setSweepFinished(false);
        applyState({ page: "sys", phase: "ready", fault: false });
      },
    ],
    [
      "locks-orphans",
      "Verrous — des entrées temporaires restent",
      () => {
        window.__mocks?.reset();
        window.__mocks?.setTmpOrphans(true);
        applyState({ page: "sys", phase: "ready", fault: false });
      },
    ],
  ];
}
