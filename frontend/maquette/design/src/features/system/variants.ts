// What the machine's page draws with, where the shared primitives do not fit.
//
// A passage's row is the shared fact row (`ui/fact-rows.tsx`): its outcome is
// the chip at the row's end, and the row is the control that opens the passage.
import { cva } from "../../ui/cva";

/** A passage's head: how it ended, what started it, how long it took. */
export const runSummary = cva("flex flex-wrap items-baseline gap-3 text-3 text-muted-foreground");

/** One step of a passage: its name and status, then its counts and its reasons. */
export const runStep = cva("flex flex-col gap-2 py-4 px-5 border-b border-border last:border-b-0 bg-card");

/** A step's name beside its status. */
export const runStepHead = cva("flex items-baseline justify-between gap-3 text-3 text-foreground");

/** A step's counts, composed in words. */
export const runStepCounts = cva("text-2 text-foreground");

/** One recorded reason — data shown as it was written, and allowed to break. */
export const runReason = cva("text-1 font-mono text-muted-foreground break-all");

/** The error a failed passage recorded, drawn whole. */
export const runError = cva("text-2 font-mono text-danger break-all");

/**
 * The raw output, monospaced, its lines WRAPPED and broken anywhere: nothing on
 * a phone scrolls sideways, a log included (§ 12, the operator's ruling).
 */
export const runLog = cva(
  "mt-3 max-h-[60dvh] overflow-x-hidden overflow-y-auto whitespace-pre-wrap [overflow-wrap:anywhere] font-mono text-1 " +
    "text-foreground bg-muted rounded-2 p-4",
);
