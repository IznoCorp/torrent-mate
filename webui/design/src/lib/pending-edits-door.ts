// The door the pending edits of the settings are asked through.
//
// A SETTING CAN BE EDITED FROM MORE THAN ONE PAGE — the settings page, and the
// page that shows what the setting governs — and the frame draws the one save
// bar over every page that holds such edits (C1, `app/bottom-slot.tsx`). The
// feature that owns the pending edits fills this door; a page that offers a
// setting, and the frame that asks before a page with edits waiting is left
// (`app/leave-confirm.ts`), read it and name no feature.

// WHO HEARS A SAVE: a page drawing what a setting governs re-reads it once the
// setting is written, whichever page wrote it — the door names no feature.
const saveListeners: (() => void)[] = [];

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

/** What another page — and the frame — may ask of the pending edits, through the feature that owns them. */
export type PendingEditsDoor = {
  /** The value a setting will be written as, when an edit of it is pending. */
  pending: (identifier: string) => { value: unknown } | undefined;
  /** Files an edit of one setting — the same edit Réglages files. */
  file: (identifier: string, value: unknown) => void;
  /** The failure the last write of a setting earned — its status and the layer's
   * words — until it is written again. */
  refusal: (identifier: string) => { status: number; detail: string } | undefined;
  /** How many edits wait — the one answer the bar and the leave confirmation read. */
  waiting: () => number;
  /** Writes every waiting edit, as « Enregistrer » on the bar does. */
  save: () => Promise<void>;
  /** Drops every waiting edit, writing nothing. */
  drop: () => void;
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
