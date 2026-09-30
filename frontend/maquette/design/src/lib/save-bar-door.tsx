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

/** What another page may ask of the pending edits, through the feature that owns them. */
export type PendingEditsDoor = {
  /** The value a setting will be written as, when an edit of it is pending. */
  pending: (identifier: string) => { value: unknown } | undefined;
  /** Files an edit of one setting — the same edit Réglages files. */
  file: (identifier: string, value: unknown) => void;
  /** The failure the last write of a setting earned — its status and the layer's
   * words — until it is written again. */
  refusal: (identifier: string) => { status: number; detail: string } | undefined;
};

let edits: PendingEditsDoor | undefined;

/**
 * Fills the pending edits' door, from the feature that owns them.
 *
 * @param door What the pending edits answer.
 */
export function fillPendingEditsDoor(door: PendingEditsDoor): void {
  edits = door;
}

/**
 * The pending edits, as another page asks them — ONE table of edits whichever
 * door files into it, so a setting offered on two pages is written once.
 *
 * @returns The door, or undefined before the owning feature has filled it.
 */
export function pendingEdits(): PendingEditsDoor | undefined {
  return edits;
}
