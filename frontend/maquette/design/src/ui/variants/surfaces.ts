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

/** A tone a status dot may carry. */
export type StatusTone = NonNullable<NonNullable<Parameters<typeof statusDot>[0]>["tone"]>;

/**
 * The chip — a short state in a tinted pill, led by a dot in its own colour.
 *
 * EXACT anatomy of the shipped Chip component: 11px semibold, pill radius, a 6px
 * dot in the tone colour, the ground tinted at 20%. A chip without its dot, or
 * at another size, is drift — not a variant.
 *
 * THE COLOURS GO THROUGH TWO CUSTOM PROPERTIES WITH A FALLBACK, and that is not
 * decoration. A tone must override the neutral tint, and Tailwind orders two
 * utilities setting the same property by their NAME: a danger ground sorts
 * before the muted one and would lose to it. A tone therefore sets
 * `--chip-background` and `--chip-foreground`, which nothing else sets, and the
 * base reads them with the neutral colours as the fallback — so the base alone
 * is the neutral chip, and a tone always wins.
 *
 * EVERY TONE IS ONE STRING LITERAL, however long: `harness/factories.py` reads
 * a factory's base through its literals, and its branches one per literal, so a
 * tone split in two is read as two branches.
 */
export const chip = cva(
  "chip inline-flex items-center gap-2 whitespace-nowrap rounded-full py-1 px-3 text-2 font-semibold " +
    "leading-[15px] [background:var(--chip-background,var(--color-muted))] " +
    "[color:var(--chip-foreground,var(--color-muted-foreground))] " +
    "before:content-[''] before:flex-none before:w-[6px] before:h-[6px] before:rounded-full before:bg-current",
  {
    variants: {
      tone: {
        warning:
          "warning [--chip-background:color-mix(in_oklab,var(--color-warning)_20%,transparent)] [--chip-foreground:var(--color-warning-text)]",
        success:
          "success [--chip-background:color-mix(in_oklab,var(--color-success)_20%,transparent)] [--chip-foreground:var(--color-success-text)]",
        danger:
          "danger [--chip-background:color-mix(in_oklab,var(--color-danger)_20%,transparent)] [--chip-foreground:var(--color-danger-text)]",
        info:
          "info [--chip-background:color-mix(in_oklab,var(--color-info)_20%,transparent)] [--chip-foreground:var(--color-info-text)]",
        waiting:
          "waiting [--chip-background:color-mix(in_oklab,var(--color-waiting)_20%,transparent)] [--chip-foreground:var(--color-waiting)]",
        neutral: "neutral",
      },
    },
  },
);

/** A tone a chip may carry. */
export type ChipTone = NonNullable<NonNullable<Parameters<typeof chip>[0]>["tone"]>;

/**
 * A card's poster frame: out of flow, its artwork fills it and contributes no
 * width, so the card's height decides it through the poster's ratio.
 *
 * IT LEADS WITH A UTILITY, AND THE CALL SITE WRITES `poster` BESIDE IT, which is
 * the one departure from « the class name at the front ». The residue's poster
 * rule is grouped with the long-press refusal, whose `-webkit-touch-callout`
 * Chrome does not compute: an anchored pair would read nothing on either side
 * and could only ever fail. The declarations below are the rules' own.
 *
 * The long press is refused here and nowhere wider: held on a picture, a phone
 * offers to copy or save it, and that menu REPLACES ours.
 */
export const posterFrame = cva(
  "self-stretch relative w-[84px] bg-muted overflow-hidden text-5 p-0 [border:0] " +
    "select-none [-webkit-touch-callout:none] " +
    "[&>img]:absolute [&>img]:inset-0 [&>img]:grid [&>img]:place-items-center [&>img]:w-full " +
    "[&>img]:h-full [&>img]:object-cover [&>img]:overflow-hidden " +
    "[&>img]:[background:linear-gradient(to_bottom_right,color-mix(in_oklab,var(--color-primary)_50%,transparent),var(--color-card),var(--color-muted))] " +
    "[&>img]:[-webkit-user-drag:none] [&>img]:[-webkit-touch-callout:none] " +
    "[&>.pfall]:absolute [&>.pfall]:inset-0",
);

/** A poster with no picture: an icon, faint, and the title's initial. */
export const posterFallback = cva(
  "pfall relative grid place-items-center w-full h-full object-cover overflow-hidden " +
    "[background:linear-gradient(to_bottom_right,color-mix(in_oklab,var(--color-primary)_50%,transparent),var(--color-card),var(--color-muted))] " +
    "[&_svg]:absolute [&_svg]:bottom-[-14%] [&_svg]:right-[-11%] [&_svg]:w-[66%] [&_svg]:h-[66%] " +
    "[&_svg]:text-foreground [&_svg]:opacity-5 " +
    "[&_b]:relative [&_b]:[font-family:ui-monospace,SFMono-Regular,Menlo,monospace] [&_b]:text-[1em] " +
    "[&_b]:font-semibold [&_b]:tracking-[-0.02em] " +
    "[&_b]:[color:color-mix(in_oklab,var(--color-muted-foreground)_90%,transparent)]",
);

/** The poster in a panel's head: its own ratio, beside the title. */
export const sheetPoster = cva(
  "sheetposter flex-none w-[84px] aspect-[2/3] rounded-2 overflow-hidden text-8 bg-muted " +
    "select-none [-webkit-touch-callout:none] " +
    "[&_img]:w-full [&_img]:h-full [&_img]:object-cover [&_img]:block " +
    "[&_img]:[-webkit-user-drag:none] [&_img]:[-webkit-touch-callout:none]",
);

/** An empty surface: it says WHY, and offers a way out. */
export const emptyNote = cva(
  "empty border border-dashed border-border rounded-3 py-8 px-7 text-center " +
    "text-3 text-muted-foreground leading-[1.5] " +
    // ITS BOLD IS ITS LEAD, WHEREVER IT SITS: every `b` inside the note — the
    // title, and a figure a sentence emphasises — is a block of its own.
    "[&_b]:block [&_b]:text-foreground [&_b]:text-4 [&_b]:mb-2",
);

/**
 * One line of a skeleton, standing where a sentence will go while its read is
 * in flight. The BOX is the variant's — a width that says roughly how long the
 * sentence will be, and a height that is the LINE's rather than the box's:
 * `--spacing-8` is 18 px, which is `--text-3` at the 1.55 the body sets, so the
 * blocks below a skeleton do not move when the sentence lands. The first
 * version stood 8 px tall and every block under it rose ten when the read
 * arrived — a layout shift a placeholder exists to prevent. The shimmer is
 * `skeleton()`'s, worn beside this.
 */
export const skeletonLine = cva("block h-8 rounded-2", {
  variants: {
    width: { full: "w-full", wide: "w-4/5", half: "w-1/2", short: "w-1/3" },
  },
  defaultVariants: { width: "wide" },
});

/**
 * A placeholder standing where content will land while its read is in flight.
 *
 * The SHIMMER is a designed motion, so it runs under `motion-safe:` (invariant
 * 14): a gradient four boxes wide, walked across the box. The SHAPE is the box
 * — a list card, a gallery cell, a row of a list, or the line `skeletonLine`
 * sizes — and each shape keeps the name the grids and the harness read.
 */
export const skeleton = cva(
  "sk [background-image:linear-gradient(90deg,var(--color-card)_25%,var(--color-muted)_50%,var(--color-card)_75%)] " +
    "[background-size:400%_100%] motion-safe:animate-shimmer",
  {
    variants: {
      shape: {
        card: "skcard h-[62px] rounded-2",
        tile: "tile aspect-[2/3] rounded-2",
        row: "row h-[62px] rounded-3",
        line: "rounded-2",
      },
    },
    defaultVariants: { shape: "line" },
  },
);

/** A surface in error: it names the cause and offers a retry. */
export const surfaceError = cva(
  "surferr [border:1px_solid_color-mix(in_oklab,var(--color-danger)_45%,transparent)] " +
    "[background:color-mix(in_oklab,var(--color-danger)_8%,transparent)] " +
    "rounded-3 p-7 text-3 leading-[1.5] " +
    // THE CAUSE LEADS AND THE RETRY SPANS, wherever the surface draws them.
    "[&_b]:block [&_b]:text-danger-text [&_b]:mb-2 " +
    "[&_button]:mt-5 [&_button]:w-full [&_button]:[border:1px_solid_var(--color-border)] " +
    "[&_button]:bg-transparent [&_button]:text-foreground [&_button]:text-3 " +
    "[&_button]:font-semibold [&_button]:p-4 [&_button]:rounded-2",
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

/** A fact list's frame: its rows share one border, one ground and one radius. */
export const factList = cva("flux list-none m-0 p-0 border border-border rounded-3 bg-card overflow-hidden");

/**
 * One row of a fact list. A row follows another with a rule between them.
 *
 * The three qualifiers draw nothing on the row itself — its parts read them —
 * and they stay as the names the interface gives those states.
 */
export const factRow = cva("fx [.fx+&]:border-t [.fx+&]:border-t-border", {
  variants: {
    empty: { true: "fempty", false: "" },
    blocked: { true: "fblocked", false: "" },
    withTarget: { true: "fclick", false: "" },
  },
  defaultVariants: { empty: false, blocked: false, withTarget: false },
});

/**
 * A fact row's body: the name and the value on one line, the sub-line under.
 *
 * `minmax(0, …)` on both tracks: an untruncated name would otherwise size its
 * track to its content and push the row past a 390px frame (R7). A row that
 * leads somewhere is a real button, inheriting nothing from the browser's own,
 * and the whole row answers a thumb, so it carries the 44px floor a target needs.
 */
export const factRowBody = cva(
  "fw grid grid-cols-[minmax(0,1fr)_minmax(0,auto)] items-baseline gap-x-5 gap-y-1 py-4 px-5 w-full " +
    "text-left [border:0] bg-transparent",
  {
    variants: { withTarget: { true: "min-h-[44px] cursor-pointer", false: "" } },
    defaultVariants: { withTarget: false },
  },
);

/** A fact's name. With no value to report, it reads as absent. */
export const factName = cva("fn text-3", {
  variants: { empty: { true: "text-muted-foreground font-medium", false: "font-semibold" } },
  defaultVariants: { empty: false },
});

/** A fact's value. A step that stopped the run says so in the danger tone. */
export const factValue = cva("fr text-3 text-right", {
  variants: { blocked: { true: "text-danger font-semibold", false: "text-muted-foreground" } },
  defaultVariants: { blocked: false },
});

/** A fact's sub-line. A reason never truncates (§12, R48): it wraps and the row grows. */
export const factDetail = cva("fs col-span-full text-2 text-muted-foreground [overflow-wrap:anywhere]");

/** A fact's key, in the mono face: what one needs reading a log or a diff. */
export const factKey = cva(
  "fk [font-family:ui-monospace,SFMono-Regular,Menlo,monospace] text-1 text-muted-foreground",
);

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
 * The footer's own action — what a spent list offers to load more.
 *
 * A CONTROL AT THE FOOT OF A LIST IS SECONDARY TO THE LIST: it is offered
 * after the reading rather than competing with it, so it takes the button
 * system's `footer` size rather than the `screen` size a primary action
 * carries. What is left here is its MOOD — an outline, a transparent ground —
 * and the mood is all this factory spells.
 *
 * ITS SIZE IS NOT WRITTEN HERE, AND THAT IS THE POINT. It used to be, and the
 * duplicate spelling was held equal to the retry's by a test because the size
 * lived in two places. It now lives in one: the call site asks
 * `actionButton({ size: "footer" })` for it, so a size this catalogue does not
 * offer cannot be given to a button at all — the operator's ruling, enforced
 * by the type rather than by a reviewer.
 *
 * The icon it carries is sized by that same branch. Left to itself an `<svg>`
 * takes the replaced-element default and the flex box stretches it: measured
 * at 227 px, in a button 245 px tall.
 */
export const loadFooterAction = cva(
  "border border-border bg-transparent text-foreground",
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
