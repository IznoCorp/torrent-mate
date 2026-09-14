// THE HARNESS MODULE — the named states, their driver, the notes toggle and the
// seams the rules read.
//
// The boot installs it behind `__MOCKS_BUILT_IN__`, so a build without the mock
// layer drops this whole directory: nothing here runs at module evaluation, and
// every table is built by a call. It dies at switchover with `harness.css`.
import { installDriver, type NamedState } from "./drive";
import { installHarnessPanel } from "./panel";
import { publishSeams } from "./publish";
import { accountStates } from "./states/account";
import { acquisitionStates } from "./states/acquisition";
import { arrivalsStates } from "./states/arrivals";
import { entryStates } from "./states/entry";
import { drawerStates, notFoundStates } from "./states/frame";
import { libraryStates } from "./states/library";
import { maintenanceStates } from "./states/maintenance";
import { mediaStates } from "./states/media";
import { relayStates } from "./states/relay";
import { settingsStates } from "./states/settings";
import { systemStates } from "./states/system";

/**
 * Every named state, in the order `__states()` has always listed them.
 *
 * The order is kept because a leak from one state into the next is read in
 * that order, and a measurement that moved would be a finding about the order
 * rather than about the interface.
 *
 * Returns:
 *     The table.
 */
function namedStates(): NamedState[] {
  return [
    ...entryStates(),
    ...acquisitionStates(),
    ...libraryStates(),
    ...arrivalsStates(),
    ...mediaStates(),
    ...drawerStates(),
    ...systemStates(),
    ...notFoundStates(),
    ...accountStates(),
    ...maintenanceStates(),
    ...settingsStates(),
    ...relayStates(),
  ];
}

/** Publishes the seams, then installs the driver, the harness bar's controls and the welcome hint. */
export function installHarness(): void {
  publishSeams();
  // EVERY STATE STARTS FROM A GOOD CONNECTION, and that is not a courtesy to
  // the three relay states — it is what keeps them from leaking into all the
  // others. A forced condition is a global, `__go` drives one state after
  // another in one document, and a state that had drawn a warning would leave
  // every later one drawing it too. Wrapping here rather than asking each state
  // to clean up is the same decision `__reset()` embodies: a state pins what it
  // means to show, and everything else starts from a known place.
  installDriver(
    namedStates().map(([id, label, run]): NamedState => [
      id,
      label,
      () => {
        window.__relay?.reset();
        run();
      },
    ]),
  );
  installHarnessPanel();
}
