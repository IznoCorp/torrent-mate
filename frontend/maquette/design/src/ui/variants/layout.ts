// THE SHELL OF A SURFACE — what holds a page, a screen or a sheet, and the
// chrome around it.
//
// ONE OF THE THREE FILES `ui/variants.ts` RE-EXPORTS. They were one module
// until it reached 518 lines against a ceiling of 400 (invariant 6). The split
// follows a SUBJECT, and the barrel keeps every call site unchanged.
import { cva } from "../cva";

/** The page body: the column every surface's sections stack in. */
export const body = cva("body flex flex-col gap-7 pt-5 px-7 pb-8");

/** One section of a page. */
export const section = cva("sec flex flex-col gap-4");

/** A section's header row: a title, an optional status dot, a count pushed right. */
export const sectionHead = cva(
  "sechead flex items-center gap-4 w-full [border:0] bg-transparent py-1 px-0 text-left",
);

/** The section title. */
export const sectionTitle = cva("t text-3 font-bold tracking-[0.01em]");

/** The count at the end of a section header. */
export const sectionCount = cva("k ml-auto text-2 font-bold text-muted-foreground");

/** A screen: the layer that slides in over a page. */
export const screen = cva(
  "screen absolute inset-0 bg-background z-[45] flex flex-col " +
    "[transform:translateX(100%)] transition-[transform] duration-300 ease-standard invisible",
);

/**
 * A screen's top bar.
 *
 * ONE back control for every page. A floating variant over the image created a
 * second design — white — which on screens without an image OVERLAPPED the
 * title instead of pushing it. A bar in the flow can cover nothing, and it
 * reads the same everywhere.
 */
export const screenBar = cva("screenbar flex-none flex items-center gap-3 py-5 px-6 bg-background");

/** The back control itself. */
export const backAction = cva(
  "fback flex items-center gap-2 [border:0] bg-transparent text-primary text-4 font-semibold py-2 px-1",
);

/**
 * A scrollport — the element a surface scrolls inside.
 *
 * FIVE SCREENS WEAR THIS BESIDE THE SHELL, and that is what made converting it
 * as « the shell's `<main>` » wrong: the class was a shared primitive all
 * along. Its utilities went onto one element in phase 5, and the five screens
 * silently stopped scrolling — the oracle could not see it, because a screen's
 * viewport is not one of the 33 measured regions, and it surfaced as a lost
 * scroll POSITION two rules away.
 *
 * It ESTABLISHES the container the gallery's three `@container port` queries
 * ask. A component asks the width it HAS, never the window's (invariant 12).
 */
export const scrollport = cva(
  "port @container/port flex-auto min-h-0 overflow-y-auto overflow-x-clip " +
    "overscroll-y-none [-webkit-overflow-scrolling:touch] " +
    "pb-[calc(var(--tm-bottom-bar-h,0px)+var(--spacing-7))]",
);

/** The scrim behind a sheet. */
/* THE EXIT IS SEEN, and it was not (B-249). `visibility` is not an animatable
   property in the way `opacity` is: declared in the transition list it SWAPS at
   one end of the duration rather than interpolating, and left OUT of it — which
   it was — it swaps on the first frame. So the scrim went `hidden` immediately
   while its opacity spent 200 ms fading behind a curtain nobody could see: the
   dimmed page snapped to full brightness in ONE frame, and the producers that
   wait 260 ms for the layer to « finish leaving » were waiting for something
   already over. Measured frame by frame, on the operator's own path.

   The idiom is the standard one and it reads oddly until it is said out loud:
   `visibility` transitions with a DELAY equal to the fade, so it holds
   `visible` for the whole exit and flips at the end; entering, the delay is
   zero so it flips at once. Nothing at REST changes — closed is still
   `hidden` at `opacity: 0` — which is why the oracle, which settles, has
   nothing to say about it. */
export const sheetScrim = cva(
  "scrim absolute inset-0 bg-scrim z-[46] transition-[opacity,visibility] "
    + "duration-200 ease-standard",
  { variants: { open: { true: "open opacity-100 visible [transition-delay:0s,0s]",
                        false: "opacity-0 invisible [transition-delay:0s,200ms]" } },
    defaultVariants: { open: false } },
);

/**
 * The bottom sheet.
 *
 * THE TAB BAR DOES NOT SIT ABOVE THIS LAYER ANY MORE (B-248, dictated by the
 * operator on 2026-08-30 from a screenshot). It used to: the sheet was z-47
 * under the bar's z-50, so it rose BEHIND the chrome and reserved the bar's
 * height in its own body so its last action stayed reachable. The sheet paints
 * OVER the bar now — while a bottom layer is open the bar is not seen.
 *
 * THE ANCHORING IS UNCHANGED and that is the correction the operator made to
 * the first reading of this entry: the sheet still rises from the screen's
 * bottom edge (`bottom-0`), NOT from the bar's top edge. What moves is the
 * RANK; what goes is the padding that compensated the overlap. The
 * confirmation at 56 is the precedent, and the ranked list in
 * `ui/variants/frame.ts` is where both are written down.
 *
 * INTERACTION IS UNCHANGED: `app/focus.ts` already marks the background
 * `inert` while a layer is open, `#nav` among the thirteen elements it names,
 * and `inert` takes an element out of hit-testing as well as out of the focus
 * order. The bar was never tappable under a layer. It was VISIBLE.
 */
export const bottomSheet = cva(
  "sheet absolute left-0 right-0 bottom-0 z-[52] bg-popover border-t border-border " +
    "rounded-t-4 rounded-b-none max-h-[78%] flex flex-col " +
    // The transition lives in the base because the state that CANCELS it is
    // not a prop: the drag handler writes `dragging` straight to the DOM
    // through a ref, exactly as the legacy one did, so `.sheet.dragging`
    // stays a rule in the residue. A variant here would never be told.
    // `visibility` joins the transition for B-249's reason — see `sheetScrim`
    // above: left out of it, it swaps on the first frame and the slide-out
    // plays behind a curtain. The delay is the slide's own duration.
    "transition-[transform,visibility] duration-300 ease-standard",
  {
    variants: {
      open: {
        true: "open [transform:none] visible [transition-delay:0s,0s]",
        false: "[transform:translateY(100%)] invisible [transition-delay:0s,300ms]",
      },
    },
    defaultVariants: { open: false },
  },
);

/**
 * The grab handle.
 *
 * `touch-none` is COMPOSITOR-FACING and held by `check-compositor-css.py`: a
 * drag on the handle is never a scroll.
 */
export const sheetGrab = cva(
  "sheetgrab h-[22px] grid place-items-center flex-none touch-none cursor-grab " +
    "before:content-[''] before:w-[36px] before:h-[4px] before:rounded-full before:bg-border",
);

/**
 * The sheet's DRAG BAND — the grip zone the operator asked to be four times the
 * handle (E-003).
 *
 * IT OVERLAYS AND DOES NOT PUSH. `#sheetin` is the sibling immediately after
 * the handle and holds the poster, the title and the seasons; an 88px band in
 * FLOW would take 88px from a sheet already capped at `max-h-[78%]`, either
 * pushing the content down or stopping the poster scrolling. So it is absolute
 * over the top of the content, and what it costs was MEASURED rather than
 * assumed: across all five sheet states, nothing interactive sits in the top
 * 88px, so no tap is swallowed.
 *
 * IT STOPS AT THE SHEET'S EDGE. The operator arbitrated the 12px overhang away
 * on 2026-08-29: those pixels are the scrim, the scrim closes on TAP, and a tap
 * that becomes a failed drag closes nothing.
 *
 * `88px` is an arbitrary value on purpose — a grip zone is not a spacing step,
 * and the scale stops at 24px (`styles/theme.css`).
 *
 * THE CONDITION IS THE WHOLE ARBITRATION. At the top of the content a downward
 * drag is a dismissal; anywhere else it is a scroll. A sheet that opens is
 * always at the top, so the first gesture is always a dismissal and the content
 * keeps its scrolling. One condition, not a gesture engine — the full
 * press/drag/scroll arbitration is L12's.
 */
export const sheetDragBand = cva(
  "absolute top-0 left-0 right-0 h-[88px] z-[1]",
  {
    variants: {
      // `touch-none` claims the gesture from the compositor; without it a real
      // finger is cancelled mid-drag. It may only be claimed where a drag is
      // what the gesture MEANS, which is why it rides this variant and not the
      // base — a permanent `touch-none` here would kill scrolling from the top
      // 88px of every sheet.
      atTop: {
        true: "touch-none cursor-grab",
        false: "pointer-events-none touch-auto",
      },
    },
    defaultVariants: { atTop: true },
  },
);

/** The sheet's scrolling viewport. */
export const sheetViewport = cva(
  // NO BAR HEIGHT RESERVED SINCE B-248: the sheet paints over the tab bar, so
  // there is nothing underneath for its last action to be stuck behind. The
  // bottom padding is the sheet's own, and the safe area is the frame's.
  "sheetin overflow-y-auto pt-1 px-7 pb-8",
);

/** The sheet's title. */
export const sheetTitle = cva("sheettitle text-6 font-bold tracking-[-0.01em] mt-0 mx-0 mb-1");

/** The line under it. */
export const sheetMeta = cva("sheetmeta text-3 text-muted-foreground mb-7");

/**
 * The sheet's head.
 *
 * A head carrying a POSTER aligns to the TOP: an 84px picture next to two short
 * lines centred against it leaves the title floating in the middle of nothing.
 * It also breathes below rather than inside — against an 84px picture the same
 * 4px reads as nothing at all.
 */
export const sheetHead = cva(
  "sheethead flex gap-6 [&_.sheetmeta]:mb-3 " +
    "[&_.sheetsub]:block [&_.sheetsub]:mt-1 [&_.sheetsub]:text-3 [&_.sheetsub]:text-muted-foreground",
  {
    variants: {
      withPoster: {
        true: "withposter items-start pb-0 mb-6",
        false: "items-center pb-2",
      },
    },
    defaultVariants: { withPoster: false },
  },
);

/** The identity block inside the head. */
export const sheetIdentity = cva("sheetid min-w-0 flex-1");

/** The avatar, at the size a sheet gives it. */
export const sheetAvatar = cva("big w-[42px] h-[42px] text-6");

/**
 * The image INSIDE an avatar, and it is a variant because nothing constrained
 * it.
 *
 * An `<img>` with no rule of its own renders at its natural size — 128 px for
 * the seeded avatar — whatever box its host declares. The oracle could not see
 * it: its named region measures the CONTAINER's box and nineteen computed
 * properties OF THAT ELEMENT, and a child three times too large changes none of
 * them (B-138, and the same limit B-061 writes into D8 for pseudo-elements).
 *
 * `block` is not decoration here. An `<img>` is inline by default, which gives
 * it a baseline gap under it and makes `height: 100%` resolve against a line
 * box rather than the host.
 */
export const avatarImage = cva(
  "w-full h-full object-cover rounded-[inherit] block",
);

/**
 * An entry that is COMING says so instead of being absent: a menu that grows an
 * item later teaches its shape twice.
 */
export const comingSoon = cva(
  "soon ml-auto text-1 font-bold tracking-[0.03em] py-1 px-3 rounded-full bg-muted text-muted-foreground",
);

/** The sheet's actions. `secondary` separates what is not the main path. */
export const sheetActions = cva("sheetacts flex flex-col gap-3 mt-2 mx-0 mb-7", {
  variants: { secondary: { true: "secondary mt-8 pt-7 border-t border-border", false: "" } },
  defaultVariants: { secondary: false },
});

/**
 * A paragraph that GUIDES the reader of the application, not of the design.
 *
 * IT EXISTS BECAUSE `.note` DID NOT DISTINGUISH THE TWO, and the distinction is
 * load-bearing: `.note` is the prototype's annotation, styled in the harness
 * sheet and hidden until the reader asks for it — so a paragraph wearing it is
 * invisible by default. Four paragraphs wearing it were not annotations at all.
 * They tell the operator what a control does, what a displayed value means, or
 * what an action is about to do, and one of them is the only sentence saying
 * that a maintenance rubric DELETES.
 *
 * THE TEST, applied to all twenty-seven: a paragraph is an annotation if it
 * addresses the reader of the MAQUETTE — what changed, what was drawn anew,
 * which section of the constitution it serves. It is guidance if it addresses
 * the operator USING the application. Twenty-three were annotations and stay
 * `.note`; four are guidance and wear this.
 *
 * It carries the annotation's own shape deliberately — the reader has learnt
 * that a left-bordered tinted paragraph is an explanation — in the muted tone
 * rather than the accent, because guidance is part of the page and an
 * annotation is a layer over it.
 */
export const guidance = cva(
  "guidance border-l-[3px] border-border bg-muted rounded-r-2 py-4 px-5 " +
    "text-2 leading-[1.5] text-foreground",
);

/** A note stating a rule, set off by a rule of its own. */
export const ruleNote = cva(
  "rulenote mt-0 mx-0 mb-7 text-3 leading-[1.45] text-muted-foreground " +
    "border-l-2 border-border pt-1 pr-0 pb-1 pl-5",
);

/**
 * The header's connection indicator — the dot and its word.
 *
 * `ps-dot` IS KEPT AT THE FRONT, emptied of style, because it is an identity
 * anchor (D4) and `harness.css` still selects `.ps-dot__label` to hide the word
 * at phone width. The utilities are what the static markup already carried, so
 * the connected rendering is byte-identical to the one the oracle recorded.
 */
export const connectionMark = cva(
  "ps-dot inline-flex items-center gap-3 text-3 text-muted-foreground",
);

/**
 * The dot itself — its colour IS the message.
 *
 * The colour lives in every branch and never in the base: a property a variant
 * may change does not belong in the base, or which utility wins is decided by
 * the generator's sort order rather than by the author (`ui/cva.ts`).
 */
export const connectionDot = cva(
  "ps-dot__d relative w-[8px] h-[8px] rounded-full flex-none",
  {
    variants: {
      condition: {
        connecting: "bg-muted-foreground",
        connected: "bg-success",
        // THE ONE CONDITION THAT MOVES, and it moves because it is the one
        // that is TEMPORARY: a pulse says « wait », which is exactly what
        // reconnecting asks of a reader. `lost` and `refused` are settled
        // states and a pulsing settled state would say something false.
        // `motion-safe:` and never a bare `animate-*`: under a reduced-motion
        // preference the dot is the same dot in the same warning colour, which
        // is a drawn state rather than an absence (invariant 14).
        reconnecting: "bg-warning motion-safe:animate-connection-pulse",
        lost: "bg-danger",
        refused: "bg-danger",
      },
    },
    defaultVariants: { condition: "connected" },
  },
);

/**
 * The notice below the header: what is wrong, since when, what to do.
 *
 * IT IS IN THE FLOW, never floating. A bar over the content would cover the
 * first row of whatever the reader was looking at, which is the one thing a
 * message about staleness must not do — and `screenBar`'s own comment records
 * the same lesson from the other end.
 */
export const connectionNotice = cva(
  "flex-none flex items-center gap-4 py-3 px-6 text-2",
  {
    variants: {
      condition: {
        connecting: "bg-muted text-muted-foreground",
        connected: "bg-muted text-muted-foreground",
        reconnecting: "bg-muted text-muted-foreground",
        lost: "bg-danger/12 text-danger",
        refused: "bg-danger/12 text-danger",
      },
    },
    defaultVariants: { condition: "lost" },
  },
);

