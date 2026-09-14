// What the machine's page draws with, where the shared primitives do not fit.
//
// A PASSAGE'S ROW IS A STACK, not a row of columns. It carries four things —
// when, what triggered it, how it ended, what it did — and four columns at
// 390 px is a line that spills sideways, which is the one thing the page may
// never do (DOIT-9). So they stack, and the row stays a button across the whole
// width: the row IS the control that opens the passage.
import { cva } from "class-variance-authority";

/** One passage, as a row that leads to its own screen. */
export const runRow = cva(
  "w-full text-left flex flex-col gap-1 py-4 px-5 border-b border-border last:border-b-0 bg-card",
);

/** What a row says first: when it ran, and what triggered it. */
export const runHead = cva("flex flex-wrap items-baseline gap-2 text-2 text-muted-foreground");

/** What the passage did, composed from its counts. */
export const runLine = cva("text-2 text-foreground");

/** A passage's head: how it ended, what started it, how long it took. */
export const runSummary = cva("flex flex-wrap items-baseline gap-3 text-3 text-muted-foreground");

/** How a passage ended, in its tone — a failure is LOUD. */
export const runOutcome = cva("text-4 font-semibold", {
  variants: {
    tone: { success: "text-success", danger: "text-danger", neutral: "text-foreground" },
  },
  defaultVariants: { tone: "neutral" },
});

/** One step of a passage: its name and status, then its counts and its reasons. */
export const runStep = cva("flex flex-col gap-2 py-4 px-5 border-b border-border last:border-b-0 bg-card");

/** A step's name beside its status. */
export const runStepHead = cva("flex items-baseline justify-between gap-3 text-3 text-foreground");

/** A step's status, or « — » for a step not yet reached. */
export const runStepStatus = cva("text-2 text-muted-foreground");

/** A step's counts, composed in words. */
export const runStepCounts = cva("text-2 text-foreground");

/** One recorded reason — data shown as it was written, and allowed to break. */
export const runReason = cva("text-1 font-mono text-muted-foreground break-all");

/** The error a failed passage recorded, drawn whole. */
export const runError = cva("text-2 font-mono text-danger break-all");

/**
 * The raw output: monospaced, and the ONE block that scrolls sideways.
 *
 * A raw line is wider than a phone; wrapping it would change what it says, so
 * it keeps its lines and scrolls inside its own container — and the page never
 * does (DOIT-9).
 */
export const runLog = cva(
  "mt-3 max-h-[60dvh] overflow-x-auto overflow-y-auto whitespace-pre font-mono text-1 " +
    "text-foreground bg-muted rounded-2 p-4",
);
