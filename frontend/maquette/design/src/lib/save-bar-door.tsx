// The door a page draws the pending-edits save bar through.
//
// A SETTING CAN BE EDITED FROM MORE THAN ONE PAGE — the settings page, and the
// page that shows what the setting governs — and an edit filed on a page with
// no way to save it is an edit left waiting where nobody can see it. The
// feature that owns the pending edits fills this door with its bar; a page that
// offers a setting draws the door, and names no feature to do it.
import type { ComponentType, ReactElement } from "react";

let bar: ComponentType | undefined;

/**
 * Fills the door, from the feature that owns the pending edits.
 *
 * @param component The save bar, which draws nothing while no edit waits.
 */
export function fillSaveBarDoor(component: ComponentType): void {
  bar = component;
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
