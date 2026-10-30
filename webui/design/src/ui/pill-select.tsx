// The one-pill selector — what filters or sorts a list, in the filter zone every
// list draws above itself.
//
// ONE COMPONENT, ADAPTED FROM THE TORRENTS TAB'S TRACKER SELECTOR (DECIDED 1 of
// maquette-blocked, the operator's « J'aime beaucoup le composant filtre des
// trackers […] qu'on remplace les autres filtres […] par ce nouveau composant ! »):
// Trackers › « Torrents », « À traiter », the Médiathèque and Suivis draw their
// filter and their sort with it, and none draws its own.
//
// THE PILL SAYS THE CHOICE IN FORCE, pressed when the list is not whole, and —
// for a filter — the number of entries shown. A tap opens the bottom panel with
// the choices, because pills scrolling sideways hide what is off-screen. The
// panel's choices are the panel builder's own `choices` block.
import type { ReactElement } from "react";
import { panel } from "../lib/shell-doors";
import type { Choice, PanelDescriptor } from "./panel/contract";
import { filterPill, filterPillCount } from "./variants";

/** What one pill draws. */
export type PillSelectProps = {
  /** The choice in force, in words. */
  label: string;
  /** For a filter, the number of entries it shows; nothing for a sort. */
  count?: number;
  /** Whether the list is narrowed or reordered from its default. */
  pressed: boolean;
  /** The verb a tap raises, as the delegation reads it: `{ "data-<verb>": "" }`. */
  attributes: Record<string, string>;
};

/**
 * One pill.
 *
 * @param props What it says and what a tap raises.
 * @returns The pill.
 */
export function PillSelect({ label, count, pressed, attributes }: PillSelectProps): ReactElement {
  return (
    <button
      className={filterPill()}
      data-part="pill/select"
      aria-pressed={pressed}
      aria-haspopup="dialog"
      {...attributes}
    >
      {label}
      {count === undefined ? null : (
        <span className={filterPillCount()} data-part="pill/select-count">{count}</span>
      )}
    </button>
  );
}

/**
 * The panel a pill raises: its title, the note saying what the hints are, and
 * the choices — the one in force checked.
 *
 * @param title The panel's title.
 * @param meta What the choices' hints are.
 * @param choices The choices, in the order offered.
 * @returns The descriptor.
 */
export function choicesDescriptor(title: string, meta: string, choices: Choice[]): PanelDescriptor {
  return { title, meta, blocs: [{ type: "choices", options: choices }] };
}

/**
 * Closes the panel, then applies the choice — ONCE THE PANEL'S ENTRY HAS LEFT,
 * so a choice that writes the address replaces the page's own entry, never the
 * panel's, and nothing is pushed.
 *
 * @param apply What the choice does to the list.
 */
export function closeThenApply(apply: () => void): void {
  if (history.state?.layer === "sheet") {
    window.addEventListener("popstate", () => window.setTimeout(apply), { once: true });
    panel.close();
    return;
  }
  panel.close();
  apply();
}
