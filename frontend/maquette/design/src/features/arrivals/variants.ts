// ARRIVÉES' OWN VOCABULARY, as typed variants. Feature-local rather than in
// `ui/`: these describe the pipeline's pilot bar and its live strip, and `ui/`
// never learns about a feature (invariant 7).
//
// THE LIVE STRIP IS NOT HERE EITHER: the Acquisition page draws one too, so it
// belongs to `ui/` — two features never import each other (invariant 7), and
// the strip found its second wearer the only way it could, as 9.9px of oracle
// divergence on a page this phase never touched.
//
// WHAT IS NOT HERE IS THE RUN'S NINE STEPS. `.flux` and everything under it —
// the row, its name, its result, its reason, its key — is written by the
// engine, so its rules are in `src/styles/legacy.css` with their date of death
// rather than half-converted here.
import { cva } from "class-variance-authority";

/**
 * The pilot's bar — the pipeline's state and the one control it takes.
 *
 * It sits where the pipeline is OBSERVED (DOIT-3): the stalled step and the
 * button to run it again are one glance apart, so nothing sends the operator
 * to another page to act on what they are reading.
 */
export const pilotBar = cva(
  "pipeline border border-border rounded-3 bg-card p-6 flex flex-col gap-5",
);

/** The bar's header row. */
export const pilotHead = cva("ph flex items-center gap-4 min-w-0");

/** The bar's title. */
export const pilotTitle = cva("pt text-4 font-semibold");

/**
 * The qualifier at the end of the header.
 *
 * `min-w-0` with the ellipsis, so a long qualifier SHORTENS instead of
 * widening the row past the frame.
 */
export const pilotQualifier = cva(
  "pq min-w-0 flex-1 overflow-hidden text-ellipsis whitespace-nowrap " +
    "text-right text-2 text-muted-foreground",
);

/** The progress gauge. */
export const pilotGauge = cva("gauge h-[4px] rounded-full bg-border overflow-hidden");

/**
 * The bar's actions.
 *
 * `minmax(0, 1fr)`, never `1fr`: an auto track's floor is its item's intrinsic
 * size, so the longer label would size its column to max-content (R7).
 */
export const pilotActions = cva(
  "pacts grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-4",
);
