// A topic row: a subject one taps to go to it — its title, what it holds, a
// value at its end.
//
// ONE COMPONENT FOR SIX HAND COMPOSITIONS. Système, Réglages and Maintenance
// each re-typed the same inner layout around `topicRow()`, with bare classes
// and an inline style; the layout is this file's, the subject the caller's.
//
// IT KNOWS NO DOMAIN. Where a tap leads is the `data-*` attributes the caller
// hands in, read by the page's own verb.
import type { ReactElement, ReactNode } from "react";
import { topicRow } from "./variants";

/**
 * A topic row, the whole row being the control.
 *
 * @param props.title What the topic is.
 * @param props.subtitle What it holds, in a sentence.
 * @param props.value What sits at its end — a count, an arrow.
 * @param props.target The `data-*` attributes a tap carries.
 * @returns The row.
 */
export function TopicRow({ title, subtitle, value, target }: {
  /** What the topic is. */
  title: string;
  /** What it holds. */
  subtitle?: string;
  /** What sits at its end. */
  value?: ReactNode;
  /** The `data-*` attributes a tap carries. */
  target: Record<`data-${string}`, string>;
}): ReactElement {
  return (
    <button className={topicRow()} data-part="topic" {...target}>
      <span className="min-w-0 flex-1">
        <span className="rt" data-part="topic/title">{title}</span>
        {subtitle ? <span className="rs" data-part="topic/subtitle">{subtitle}</span> : null}
      </span>
      {value !== undefined ? <span className="rn" data-part="topic/count">{value}</span> : null}
    </button>
  );
}
