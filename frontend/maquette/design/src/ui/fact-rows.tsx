// The rows of a fact list — a named fact, its value, and a sub-line.
//
// ONE DRAWING FOR THE SHAPE « a named fact, its value, and a sub-line ». The
// pipeline's steps, the services, the schedulers, the disks, the index, the
// account: lists that look alike because they ARE alike, and a drawing per list
// is how they start to disagree. Each row is a DESCRIPTOR — a label, a value, a
// sub-line, an optional state and an optional mono key — and a caller wanting
// something outside it adds a field rather than passing markup.
//
// THE ROWS ALONE, without the `<ol class="flux">` around them: the page draws
// that element, so the list keeps the one frame every page gives it.
//
// IT KNOWS NO DOMAIN (invariant 10): a row is a label, a value and a tone word.
import type { ReactElement } from "react";
import { Chip } from "./chip";
import {
  factDetail,
  factKey,
  factName,
  factRow,
  factRowBody,
  factValue,
  type ChipTone,
} from "./variants";

/**
 * One row of a fact list.
 *
 * `ton` is the operator's word for the value's state; `target` becomes the
 * row's `data-*` attributes, which is what turns the row into the control.
 */
export type FactRow = {
  l: string;
  v?: string;
  s?: string;
  k?: string;
  ton?: string;
  state?: string;
  target?: Record<string, string>;
};

// Four tones, and each answers a different question: success — it works;
// alert — it does not, act now; warning — important, not critical; info — a
// piece of information that is not a success. `alert` is the operator's word
// and `danger` is the chip's; the mapping lives HERE, once, so nobody writing a
// row has to know the second vocabulary.
const CHIP_TONE: Record<string, ChipTone> = {
  success: "success",
  alert: "danger",
  warning: "warning",
  info: "info",
};

/**
 * The rows of one fact list.
 *
 * A row whose value is a STATE wears it as a chip carrying the word, and its
 * tone is DERIVED from `ton`, never passed as a colour, so a row cannot show a
 * green chip saying offline. A row whose value is a QUANTITY does not:
 * badging every line teaches the eye to stop seeing badges. No value is what
 * greys a row — a sub-line explaining why there is nothing to report does not
 * make the line a report. A row that leads somewhere IS the control, a button
 * across its whole width.
 *
 * @param properties The rows.
 * @returns The `<li>` of every row.
 */
export function FactRows({ rows }: { rows: FactRow[] }): ReactElement {
  return (
    <>
      {rows.map((row, index) => {
        const empty = !row.v;
        const blocked = row.state === "danger";
        const withTarget = Boolean(row.target);
        const attributes = Object.fromEntries(
          Object.entries(row.target ?? {}).map(([name, value]) => [`data-${name}`, String(value)]),
        ) as Record<`data-${string}`, string>;
        const Body = withTarget ? "button" : "span";
        const value = row.v || "—";
        return (
          <li
            key={index}
            className={factRow({ empty, blocked, withTarget })}
            data-part="flux/row"
            data-empty={empty ? "" : undefined}
            data-blocked={blocked ? "" : undefined}
          >
            <Body className={factRowBody({ withTarget })} data-part="flux/row-body" {...attributes}>
              <span className={factName({ empty })} data-part="flux/name">{row.l}</span>
              <span className={factValue({ blocked })} data-part="flux/value">
                {row.ton ? <Chip tone={CHIP_TONE[row.ton]} label={value} /> : value}
              </span>
              <span className={factDetail()} data-part="flux/detail">
                {row.k ? <span className={factKey()} data-part="flux/key">{row.k}</span> : null}
                {row.k && row.s ? " · " : null}
                {row.s || null}
              </span>
            </Body>
          </li>
        );
      })}
    </>
  );
}
