/**
 * JourneyStrip — the §14.3 journey, on its own full-width line.
 *
 * Anti-overlap is GEOMETRIC, not typographic: each station is a `flex-1 min-w-0`
 * track whose label is a full-width truncating block. A label therefore cannot
 * spill onto its neighbour at any width — tuning a font-size would have broken
 * again at the next longer label.
 *
 * `blocked` is a state of its own: neither "now" (it is not moving) nor pending
 * (it was reached and stayed). §14.3 forbids painting an unreached step as if
 * nothing had happened.
 */

import { type ReactElement } from "react";

/* eslint-disable react-refresh/only-export-components */

/** One stage of the acquisition journey. */
export type Stage = "pris" | "telech" | "ingere" | "scrape" | "range";

/**
 * The stages in walking order, with their French labels.
 *
 * The keys MUST match the return values of {@link _stage_of} in
 * ``personalscraper/web/acquisition/to_handle.py`` — a divergence here would
 * render a blank strip in production while every test passes.
 */
export const STAGES: readonly { readonly key: Stage; readonly label: string }[] = [
  { key: "pris", label: "pris" },
  { key: "telech", label: "téléch." },
  { key: "ingere", label: "ingéré" },
  { key: "scrape", label: "scrapé" },
  { key: "range", label: "rangé" },
];

/**
 * Render the journey strip.
 *
 * Args:
 *   stage: The stage actually reached.
 *   blocked: Whether the journey is stopped at that stage.
 *
 * Returns:
 *   The strip element.
 */
export function JourneyStrip({
  stage,
  blocked = false,
}: {
  readonly stage: Stage;
  readonly blocked?: boolean;
}): ReactElement {
  const current = STAGES.findIndex((s) => s.key === stage);

  return (
    <div className="mt-[10px] flex w-full border-t border-border pt-[10px]">
      {STAGES.map((s, i) => {
        const done = i < current;
        const here = i === current;
        const said = done ? "franchie" : here ? (blocked ? "bloquée" : "en cours") : "à venir";
        const dot = done
          ? "bg-success border-success"
          : here
            ? blocked
              ? "bg-danger border-danger ring-[3px] ring-danger/25"
              : "bg-info border-info ring-[3px] ring-info/25"
            : "bg-muted border-border";
        const text = here ? (blocked ? "text-danger font-semibold" : "text-info font-semibold") : "text-muted-foreground";

        return (
          <div
            key={s.key}
            data-station={s.key}
            className="relative flex min-w-0 flex-1 flex-col items-center gap-[5px]"
          >
            <span
              aria-hidden="true"
              className={`z-[1] size-[9px] shrink-0 rounded-full border-[1.5px] ${dot}`}
            />
            <span
              data-station-label
              className={`block w-full truncate px-0.5 text-center text-[9.5px] leading-tight ${text}`}
            >
              {s.label}
            </span>
            <span className="sr-only">{`${s.label} — ${said}`}</span>
            {i < STAGES.length - 1 && (
              <span
                aria-hidden="true"
                className={`absolute left-1/2 top-[5px] h-[1.5px] w-full ${done ? "bg-success" : "bg-border"}`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
