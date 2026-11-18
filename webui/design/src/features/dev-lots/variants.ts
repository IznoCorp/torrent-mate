// What the lots progress draws with, where the shared primitives do not fit.
//
// A LOT IS A CARD of the app's own frame — border, card ground, the card's
// radius — but not the media card: it has no poster and no panel, and its body
// is a list of phases. Every value below is a token of the scale.
import { cva } from "../../ui/cva";

/** The list of lots: one column, the cards spaced as a section's. */
export const lotList = cva("flex flex-col gap-5 m-0 p-0 list-none");

/** One lot: its head, what blocks it, then its phases. */
export const lotCard = cva("flex flex-col gap-3 rounded-3 border border-border bg-card p-5 min-w-0");

/** The lot's head: its name, and how many phases it has at the right. */
export const lotHead = cva("flex items-baseline justify-between gap-3 min-w-0");

/** The lot's name — never cut: it wraps and the card grows. */
export const lotName = cva("text-4 font-semibold text-foreground [overflow-wrap:anywhere] m-0");

/** How many phases the lot has. */
export const lotCount = cva("text-2 text-muted-foreground whitespace-nowrap");

/** What a lot or a phase waits on, in the definition's words. */
export const lotWaitsOn = cva("text-2 text-warning-text [overflow-wrap:anywhere]");

/** A lot's description or note: running text, wrapped, never cut. */
export const lotText = cva("text-3 text-foreground [overflow-wrap:anywhere] m-0");

/** The phases, one row each, separated by the border. */
export const phaseList = cva("flex flex-col m-0 p-0 list-none");

/** One phase: its id and title, then its state and its pull requests. */
export const phaseRow = cva("flex flex-col gap-2 py-3 border-t border-border first:border-t-0 min-w-0");

/** The phase's id beside its title. */
export const phaseHead = cva("flex items-baseline gap-3 min-w-0 text-3 text-foreground");

/** The phase's id, the plan's own. */
export const phaseId = cva("flex-none font-mono text-2 font-semibold text-muted-foreground");

/** The phase's title — never cut. */
export const phaseTitle = cva("min-w-0 [overflow-wrap:anywhere]");

/** The state chip, the dispatch word, the pull requests: one wrapping line. */
export const phaseFacts = cva("flex flex-wrap items-center gap-3 text-2 text-muted-foreground");

/** A pull request's link. */
export const pullRequestLink = cva("text-2 font-semibold text-primary underline underline-offset-2");

/** When the progress was generated, under the title. */
export const lotsStamp = cva("text-2 text-muted-foreground m-0");
