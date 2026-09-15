// Every named state starts the settings screen from the same place.
//
// The pending edits, the rubric one is in, the search and the two banners are
// all working state, and a measurement must not inherit the one before it. The
// restart the layer says is owed is reset with them, through the mock layer's
// own driving surface — which is why this lives with the driver and not in the
// feature: the product never resets itself to a measured start.
import { SETTINGS_STATE } from "../features/settings/state";

/** Puts the settings working state, and the layer's owed restart, back to rest. */
export function resetSettings(): void {
  SETTINGS_STATE.modifs.clear();
  SETTINGS_STATE.topic = null;
  SETTINGS_STATE.q = "";
  SETTINGS_STATE.readOnly = false;
  window.__mocks?.setRestartRequired(false);
  SETTINGS_STATE.conflict = false;
}
