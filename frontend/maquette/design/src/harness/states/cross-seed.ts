// The named states of the cross-seed (L17), on the « Trackers » page.
//
// Each entry is `[id, label, run]`, as every states file writes them. The seed
// is INVENTED (L17 DESIGN § 2.3) and its default is the live states: every
// switch on. A state that needs another scenario turns a dial and says so.
import { applyState, type NamedState } from "../drive";

// The page's reads, and the settings the switches are kept in: dropped before a
// state so the page asks the layer again rather than drawing a state before's.
const READS = ["/api/trackers", "/api/acquisition/downloads", "/api/acquisition/obligations", "/api/config/schema"];

/** Resets the layer and forgets the page's reads. */
function fresh(): void {
  window.__mocks?.reset();
  for (const address of READS) window.__queries?.removeQueries({ queryKey: [address] });
}

/**
 * The « Trackers » tab, under the scenario a dial set before.
 *
 * @param pose What the state poses on the layer before the page reads it.
 */
function roster(pose: () => void = () => undefined): void {
  fresh();
  pose();
  applyState({ page: "trackers", trackersTab: "trackers", phase: "ready" });
}

/**
 * Every cross-seed state.
 *
 * @returns The table.
 */
export function crossSeedStates(): NamedState[] {
  return [
    [
      "trackers-cross-seed",
      "Trackers — la ligne cross-seed de chaque tracker (INVENTÉ, L17 § 2.3)",
      () => roster(),
    ],
    [
      "trackers-cross-seed-engine-off",
      "Trackers — le moteur entier est coupé, l'interrupteur de chaque tracker dit ensuite (INVENTÉ)",
      () => roster(() => window.__mocks?.poseCrossSeedEngineOff()),
    ],
  ];
}
