// ARRIVÉES' OWN VOCABULARY, as typed variants. Feature-local rather than in
// `ui/`: these describe the pipeline's pilot bar and its live strip, and `ui/`
// never learns about a feature (invariant 7).
//
// THE LIVE STRIP IS NOT HERE EITHER: the Acquisition page draws one too, so it
// belongs to `ui/` — two features never import each other (invariant 7), and
// the strip found its second wearer the only way it could, as 9.9px of oracle
// divergence on a page this phase never touched.
//
// WHAT IS NOT HERE IS THE RUN'S NINE STEPS: the list and its rows are the fact
// list other pages draw too, so they are `factList()` and `ui/fact-rows.tsx`.
import { cva } from "../../ui/cva";

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

/**
 * A resolution candidate's card, which IS the button that picks it.
 *
 * THE BUTTON'S OWN DEFAULTS ARE UNDONE HERE, because this prototype carries no
 * preflight: a `<button>` arrives with the browser's small control font, its
 * control text colour, a padding and centred text, while the card's box comes
 * from `card()`, worn beside this factory. Only what makes a button read as the
 * card it was is written here, and so it claims no anchor of its own.
 */
export const candidateCard = cva("text-left p-0 [font:inherit] text-inherit");

/** The « Choisir » pill at a candidate card's right edge: a finger's height, in
 *  the primary ground, and never a check mark — a mark on every card read as
 *  « already selected » (B-500). It is decorative: the card is the button. */
export const candidatePick = cva(
  "inline-flex items-center justify-center self-center flex-none min-h-[44px] px-6 mr-5 "
    + "rounded-full bg-primary text-primary-foreground text-3 font-semibold whitespace-nowrap",
);
