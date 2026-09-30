// An empty place of the media sheet: the app's one empty note.
//
// ONE NEED, ONE DRAWING. « Nothing here » was drawn three ways — the shared
// empty note, a dashed box this sheet redrew, and a line of guidance — and the
// sheet's places now draw the first. The place keeps its own part, `no-info`,
// the name the rules read an answer-that-is-an-absence by; the note inside it
// carries `empty-state`, the part every empty note carries. A place still
// WAITING for its read is not empty: it keeps its skeleton, drawn by the caller.
import type { ReactElement, ReactNode } from "react";
import { emptyNote } from "../../ui/variants";
import { noInfoPlace } from "./variants";

/**
 * One empty place of the sheet.
 *
 * @param props.children What the place says is not there.
 * @returns The place, holding the empty note.
 */
export function NoInfo({ children }: {
  /** What the place says is not there. */
  children: ReactNode;
}): ReactElement {
  return (
    <div className={noInfoPlace()} data-part="no-info">
      <p className={emptyNote()} data-part="empty-state">{children}</p>
    </div>
  );
}
