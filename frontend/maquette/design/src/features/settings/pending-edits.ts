// A setting's PENDING edit — what a field draws, and how a tap files one.
//
// Nothing is written until the save bar is used: a change is PENDING, marked on
// its row, counted in the bar, and filed here. The map it is filed in is still
// the engine's `SETTINGS_STATE.modifs`, read through the published reference
// until that object has a home of its own; what a field DRAWS and what a tap
// FILES are this feature's.
import { store } from "../../lib/store-access";
import { settingIdentifier } from "./catalog";
import { heldSettings } from "./queries";
import type { Setting } from "./types";
import { SETTINGS_STATE } from "./state";

/**
 * The value a field must draw.
 *
 * The pending edit when there is one, the file's `brut` otherwise — never `.v`,
 * the pre-formatted display string. A panel that drew `.brut` alone would show
 * a list one has just shortened at its old length, and the removal would look
 * like it did nothing.
 *
 * Args:
 *     setting: The setting the field edits.
 *
 * Returns:
 *     The value to draw.
 */
export function rawValue(setting: Setting): unknown {
  const pending = SETTINGS_STATE.modifs;
  const identifier = settingIdentifier(setting);
  return pending.has(identifier) ? pending.get(identifier) : setting.brut;
}

/**
 * Whether two setting values are the same value.
 *
 * Args:
 *     first: One value.
 *     second: The other.
 *
 * Returns:
 *     True when they are equal — lists compared by content.
 */
function sameValue(first: unknown, second: unknown): boolean {
  return Array.isArray(first) || Array.isArray(second)
    ? JSON.stringify(first) === JSON.stringify(second)
    : first === second;
}

/**
 * Files a pending edit, and has the interface draw it.
 *
 * A value equal to the file's is not a pending change: it is no change, and
 * leaving it in the map would make the save bar name a file it would write
 * identically.
 *
 * Args:
 *     identifier: `<file>:<key>`, as the row and the address spell it.
 *     value: The value to file.
 */
export function changeSetting(identifier: string, value: unknown): void {
  const setting = heldSettings().find((one) => settingIdentifier(one) === identifier);
  if (setting === undefined) return;
  const pending = SETTINGS_STATE.modifs;
  if (sameValue(value, setting.brut)) pending.delete(identifier);
  else pending.set(identifier, value);
  store.touch();
}
