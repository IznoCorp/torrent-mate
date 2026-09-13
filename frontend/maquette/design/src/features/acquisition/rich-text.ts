// A text that carries emphasis, written as markup WITHOUT any caller supplying
// markup.
//
// A value is either a plain string, or a list of segments where a bare string is
// plain text, `{ e }` is emphasised and `{ m }` is a machine name — a release, a
// path, an identifier — set in the mono face. Everything is escaped; only what
// the data explicitly named comes out marked, at the position the data put it —
// nothing is matched back into the sentence afterwards, which is how the wrong
// « 4 » or the wrong title ends up emphasised.
import { escapeMarkup } from "../../ui/markup";

/** One segment of a text that carries emphasis. */
type Segment = string | { e?: string; m?: string };

/**
 * Writes a text that carries emphasis as markup.
 *
 * @param value A plain string, a list of segments, or nothing.
 * @returns The markup, empty for nothing.
 */
export function richTextMarkup(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return escapeMarkup(value);
  return (value as Segment[])
    .map((segment) => {
      if (typeof segment === "string") return escapeMarkup(segment);
      if (segment.m != null) return `<code>${escapeMarkup(segment.m)}</code>`;
      return `<b>${escapeMarkup(segment.e)}</b>`;
    })
    .join("");
}
