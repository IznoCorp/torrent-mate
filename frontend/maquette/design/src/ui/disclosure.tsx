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
 * @returns The disclosure.
 */
export function Disclosure({ summary, children }: {
  /** What the closed disclosure says. */
  summary: ReactNode;
  /** What it folds away. */
  children: ReactNode;
}): ReactElement {
  return (
    <details className={disclosure()}>
      <summary>{summary}</summary>
      {children}
    </details>
  );
}
