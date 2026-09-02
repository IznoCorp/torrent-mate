// WHAT A SURFACE SAYS ABOUT ITSELF — its state, its facts, its emptiness, its
// failure to load.
//
// ONE OF THE THREE FILES `ui/variants.ts` RE-EXPORTS. They were one module
// until it reached 518 lines against a ceiling of 400 (invariant 6). The split
// follows a SUBJECT, and the barrel keeps every call site unchanged.
import { cva } from "../cva";

/**
 * The status dot — it qualifies what follows it.
 *
 * The tone class is kept beside the utility on purpose: it is the name the
 * interface uses for that state, and several readers still spell it that way.
 *
 * NAMED `statusDot` RATHER THAN AFTER ITS CLASS: the class is `pip`, and that
 * word is on the engine's declared French-debt list, reserved to the file that
 * dies at L13. A class name in markup is one thing; an exported identifier is
 * another, and the guard is right to keep them apart.
 */
export const statusDot = cva("pip w-[8px] h-[8px] rounded-full flex-none", {
  variants: {
    tone: {
      warning: "warning bg-warning",
      danger: "danger bg-danger",
      info: "info bg-info",
      waiting: "waiting bg-waiting",
      success: "success bg-success",
      neutral: "neutral bg-neutral-signal",
    },
  },
  // A DEFAULT, BECAUSE `VariantProps` MAKES THE PROP OPTIONAL. Without one,
  // `statusDot()` type-checks and emits no `bg-*` at all — a dot with a size
  // and no colour, which renders as nothing and compiles as correct. Neutral
  // is the honest default: a state nobody named is not a warning.
  defaultVariants: { tone: "neutral" },
});

/** An empty surface: it says WHY, and offers a way out. */
export const emptyNote = cva(
  "empty border border-dashed border-border rounded-3 py-8 px-7 text-center " +
    "text-3 text-muted-foreground leading-[1.5]",
);

/**
 * One line of a skeleton, standing where a sentence will go while its read is
 * in flight. The BOX is the variant's — a width that says roughly how long the
 * sentence will be, and a height that is the LINE's rather than the box's:
 * `--spacing-8` is 18 px, which is `--text-3` at the 1.55 the body sets, so the
 * blocks below a skeleton do not move when the sentence lands. The first
 * version stood 8 px tall and every block under it rose ten when the read
 * arrived — a layout shift a placeholder exists to prevent. The shimmer is the residue's `sk`,
 * with its reduced-motion guard, worn as a literal class beside this exactly
 * as `Skeletons` wears `sk tile`: the anchor is deliberately NOT in this
 * string, because a variant wearing a residue anchor owes the residue's every
 * term (R80), and the shimmer moves here the day the residue dies.
 */
export const skeletonLine = cva("block h-8 rounded-2", {
  variants: {
    width: { full: "w-full", wide: "w-4/5", half: "w-1/2", short: "w-1/3" },
  },
  defaultVariants: { width: "wide" },
});

/** A surface in error: it names the cause and offers a retry. */
export const surfaceError = cva(
  "surferr [border:1px_solid_color-mix(in_oklab,var(--color-danger)_45%,transparent)] " +
    "[background:color-mix(in_oklab,var(--color-danger)_8%,transparent)] " +
    "rounded-3 p-7 text-3 leading-[1.5]",
);

/**
 * The live strip: a pulsing dot and a sentence about what is happening now.
 *
 * Shared — Arrivées and Acquisition both draw one.
 */
export const liveStrip = cva(
  "live flex items-center gap-4 border border-border rounded-3 py-4 px-5 " +
    "text-2 text-muted-foreground bg-card",
);

/**
 * The strip's dot. Its pulse is declared in the base layer under a
 * reduced-motion guard — motion is a designed state, not a fallback.
 */
export const liveDot = cva("d w-[7px] h-[7px] rounded-full bg-info flex-none");

/** The emphasis inside a live strip. */
export const liveEmphasis = cva("text-foreground font-semibold");

/**
 * The cross-reference note: « this medium is also … », with a link.
 *
 * A WRAPPING SENTENCE MUST NOT BE LAID OUT AS FLEX SIBLINGS. Each fragment
 * became its own column and the line read as three broken stacks. It is one
 * paragraph, `display: block`, with the link on its own row.
 */
export const crossReference = cva(
  "crossref block w-full leading-[1.45] border border-dashed border-border " +
    "bg-transparent text-muted-foreground text-3 text-left p-5 rounded-3",
);

/** The emphasis inside a cross-reference. */
export const crossReferenceStrong = cva("text-foreground font-semibold");

/** The cross-reference's link, on its own row. */
export const crossReferenceLink = cva("block mt-3 text-primary font-semibold whitespace-nowrap");

/** A panel of facts. */
export const factsPanel = cva("panel border border-border bg-card rounded-3 py-1 px-5");

/**
 * One key/value row.
 *
 * `withPip` — a row whose DOT qualifies the STEP rather than the figure. The
 * two are different statements and both exist, so the descriptor names which.
 * The child combinator inside is not decoration: `span:first-child` also
 * matches the dot itself, which is the caption's own first child.
 *
 * `upcoming` — a value that has not happened yet is not a value: it reads as
 * an announcement, not as a measurement.
 */
export const keyValueRow = cva(
  "kv flex justify-between gap-6 py-4 px-0 border-b border-border text-3 last:border-b-0 " +
    "[&_span:first-child]:text-muted-foreground " +
    "[&_span:last-child]:flex [&_span:last-child]:items-center [&_span:last-child]:gap-3",
  {
    variants: {
      withPip: {
        true: "withpip [&>span:first-child]:flex [&>span:first-child]:items-center [&>span:first-child]:gap-4",
        false: "",
      },
      upcoming: {
        // The weight and the colour live in both branches: a value that has
        // not happened yet reads as an announcement, and the one that has
        // reads as a measurement. Neither may be left to the generator.
        true: "upcoming [&_span:last-child]:font-normal [&_span:last-child]:text-muted-foreground",
        false: "[&_span:last-child]:font-semibold",
      },
    },
    defaultVariants: { withPip: false, upcoming: false },
  },
);

/** A block of facts inside a panel keeps its distance from what follows. */
export const sheetFacts = cva("sheetfacts mb-7");

/** A section heading. */
export const sectionHeading = cva("h2 text-3 font-bold m-0");

/** The foot of an infinite list: the skeletons, the sentinel, the end mark. */
export const loadFooter = cva("loadfoot flex flex-col gap-5 pt-2 pr-0 pb-1 pl-0");

/** The end of a list, said once and quietly. */
export const endMark = cva(
  "endmark text-center text-2 text-muted-foreground pt-7 pr-0 pb-2 pl-0 " +
    "before:content-[''] before:block before:w-[34px] before:h-[1px] before:bg-border " +
    "before:mt-0 before:mx-auto before:mb-4",
);

/** A list that failed to load: it names the cause and offers a retry. */
export const loadError = cva(
  "loaderr [border:1px_solid_color-mix(in_oklab,var(--color-danger)_45%,transparent)] " +
    "[background:color-mix(in_oklab,var(--color-danger)_8%,transparent)] " +
    "rounded-3 p-5 text-3 leading-[1.45] [&_b]:text-danger-text",
);

/** Its retry. */
export const loadErrorAction = cva(
  "mt-4 w-full border border-border bg-transparent text-foreground text-3 font-semibold p-4 rounded-2",
);

/**
 * A topic — a rubric of settings, or of maintenance actions, or a jump from
 * Système into either.
 *
 * IN `ui/` AND NOT IN A FEATURE: three surfaces draw one, and two features
 * never import each other (invariant 7). It was written feature-local because
 * Configuration is where it is documented, and the boundary guard found the
 * other two the same day.
 *
 * (was: A topic: a rubric of settings, or of maintenance actions.) */
export const topicRow = cva(
  "topic flex items-center gap-6 w-full text-left border border-border " +
    "rounded-3 bg-card p-6 mb-4 text-foreground " +
    "[&_.rt]:block [&_.rt]:text-5 [&_.rt]:font-semibold " +
    "[&_.rs]:block [&_.rs]:mt-1 [&_.rs]:text-3 [&_.rs]:text-muted-foreground [&_.rs]:leading-[1.4] " +
    "[&_.rn]:flex-none [&_.rn]:text-3 [&_.rn]:font-semibold [&_.rn]:text-muted-foreground",
);

/**
 * The « N results » line.
 *
 * IN `ui/` because two surfaces count: the add screen's search and the release
 * screen's candidates. Two features never import each other (invariant 7).
 */
export const resultCount = cva("rescount pt-6 px-7 pb-0 text-2 text-muted-foreground");
