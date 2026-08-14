/**
 * Chip — the maquette's dotted status chip (.chip): 11 px semibold, pill
 * radius, a 6 px dot of the tone colour, 16 % tinted background.
 *
 * One component so every surface that says a status says it with the same
 * anatomy — a chip without its dot or with another size is a drift, not a
 * variation. It sat under `acquisition/` although nothing about a status chip
 * belongs to acquisition; a shared primitive filed under one feature is one
 * that the next feature copies instead of importing.
 */

import { type ReactElement, type ReactNode } from "react";

import { TONE_CHIP_CLASS } from "@/components/acquisition/meta";

/** Props for {@link Chip}. */
export interface ChipProps {
  /** DS tone key — resolved through {@link TONE_CHIP_CLASS}. */
  readonly tone: string;
  /** Hover tooltip. */
  readonly title?: string | undefined;
  readonly children: ReactNode;
}

/**
 * Render one dotted status chip.
 *
 * Args:
 *   props: See {@link ChipProps}.
 *
 * Returns:
 *   The chip element.
 */
export function Chip({ tone, title, children }: ChipProps): ReactElement {
  return (
    <span
      data-slot="chip"
      {...(title != null ? { title } : {})}
      className={`inline-flex items-center gap-[5px] whitespace-nowrap rounded-full px-[7px] py-[2px] text-[11px] font-semibold leading-[15px] ${TONE_CHIP_CLASS[tone] ?? "bg-muted text-muted-foreground"}`}
    >
      <span aria-hidden="true" className="size-[6px] shrink-0 rounded-full bg-current" />
      {children}
    </span>
  );
}
