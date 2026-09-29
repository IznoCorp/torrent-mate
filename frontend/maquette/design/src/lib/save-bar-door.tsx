// The door a page draws the pending-edits save bar through.
//
// A SETTING CAN BE EDITED FROM MORE THAN ONE PAGE — the settings page, and the
// page that shows what the setting governs — and an edit filed on a page with
// no way to save it is an edit left waiting where nobody can see it. The
// feature that owns the pending edits fills this door with its bar; a page that
// offers a setting draws the door, and names no feature to do it.
import type { ComponentType, ReactElement } from "react";

let bar: ComponentType | undefined;
// WHO HEARS A SAVE: a page drawing what a setting governs re-reads it once the
// setting is written, whichever page wrote it — the door names no feature.
const saveListeners: (() => void)[] = [];

/**
 * Fills the door, from the feature that owns the pending edits.
 *
 * @param component The save bar, which draws nothing while no edit waits.
 */
export function fillSaveBarDoor(component: ComponentType): void {
  bar = component;
}

/**
 * Asks to hear every save of the pending edits.
 *
 * @param listener Called once a save has landed.
 */
export function onEditsWritten(listener: () => void): void {
  saveListeners.push(listener);
}

/** Says a save of the pending edits has landed, from the feature that saved them. */
export function editsWritten(): void {
  for (const listener of saveListeners) listener();
}

/**
 * The save bar, drawn by the page that offers a setting.
 *
 * @returns The bar the door was filled with, or nothing when it was not.
 */
export function PendingEditsBar(): ReactElement | null {
  const Bar = bar;
  return Bar === undefined ? null : <Bar />;
}
