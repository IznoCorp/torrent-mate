// The chip — a short state in a tinted pill, led by a dot in its own colour.
//
// IT KNOWS NO DOMAIN (invariant 10): it takes a tone and a label. Which tone a
// state earns is the caller's to say, from its own vocabulary.
import type { ReactElement, ReactNode } from "react";
import { chip, type ChipTone } from "./variants";

/**
 * One chip.
 *
 * @param properties The tone, the label, and an optional title.
 * @returns The chip.
 */
export function Chip({
  tone,
  label,
  title,
}: {
  tone: ChipTone | undefined;
  label: ReactNode;
  title?: string;
}): ReactElement {
  return (
    <span className={chip({ tone })} data-part="chip" data-tone={tone} title={title}>
      {label}
    </span>
  );
}
