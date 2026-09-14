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
