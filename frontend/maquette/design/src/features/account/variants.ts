// « Comptes »' own drawing: the creation form and its fields.
//
// The fields take the settings editor's shape — a bordered box at the type
// scale's 16px, so a focused field never zooms iOS — without importing that
// feature (invariant 7).
import { cva } from "../../ui/cva";

/** The creation form: its labels stacked, one field under each. */
export const accountForm = cva("flex flex-col gap-5 mt-6 [&_label]:flex [&_label]:flex-col [&_label]:gap-2 [&_label]:text-3 [&_label]:text-muted-foreground");

/** One field of the form. */
export const accountField = cva(
  "w-full min-w-0 rounded-3 border border-border bg-background text-foreground text-6 py-4 px-5 "
    + "[font-family:inherit] outline-none focus-visible:outline-2 focus-visible:outline-primary",
);
