// A disclosure: one summary, and what it folds away until a finger asks.
//
// THE FOLD IS AN ADJUSTMENT, NEVER AN ARRIVAL. Opening it changes what one
// screen shows and writes nothing to the history: a back from an opened fold
// leaves the screen, as it would from a closed one. `<details>` does exactly
// that and nothing more, so this component adds no state of its own.
//
// IT KNOWS NO DOMAIN. What the summary says and what is folded are the
// caller's, and the parts a rule reads are written by the caller too, on the
// elements it hands in — so the name a rule selects is on the page that owns it.
import type { ReactElement, ReactNode } from "react";
import { disclosure } from "./variants";

/**
 * A native disclosure, closed until opened.
 *
 * @param props.summary What the closed disclosure says — the control itself.
 * @param props.children What it folds away.
 * @param props.open Whether it is drawn open.
 * @param props.kind An action folded in place, or a season.
 * @param props.data-part The fold's part, for the rules that read it — written at the
 *   call site under the attribute's own name, so the markup guard reads the value
 *   where it is chosen.
 * @returns The disclosure.
 */
export function Disclosure({ summary, children, open, kind, "data-part": part }: {
  /** What the closed disclosure says. */
  summary: ReactNode;
  /** What it folds away. */
  children: ReactNode;
  /** Whether it is drawn open — an address may open it; a finger still folds it. */
  open?: boolean;
  /** An action folded in place (the default), or a season of a series. */
  kind?: "plain" | "season";
  /** The name a rule reads the fold by — the caller's, as every part is. */
  "data-part"?: string;
}): ReactElement {
  return (
    <details className={disclosure({ kind })} data-part={part} open={open}>
      <summary>{summary}</summary>
      {children}
    </details>
  );
}
