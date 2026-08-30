// THE FRAME'S OWN VARIANTS — the chrome, and what sits above the bar.
//
// They arrived with L15, when the tab bar, the action button, the selection
// bar and the message stopped being markup the engine wrote into. Their
// declarations are the ones `styles/legacy.css` and `index.html` carried, term
// for term, and the oracle's `shell/bottom-bar`, `shell/action-button` and
// `shell/toast` regions are what say so.
//
// A FILE OF THEIR OWN because `variants/layout.ts` reached invariant 6's
// ceiling when they landed in it, and because they are one family: everything
// here is drawn by `app/frame.tsx` or into the slot it offers.
//
// THE IDENTITY CLASS STAYS AT THE FRONT of every string — `bottombar`, `fab`,
// `selbar`, `toast`, `show`, `ic`, `lb`, `navbadge`, `danger`. Rules select on
// them and `app/bar-height.ts` finds the bar by one; a name removed here would
// break a reader while the styling moved cleanly.
import { cva } from "../cva";

/* ── The tab bar ─────────────────────────────────────────────────────
   The bottom bar was an empty `<nav>` the engine filled on every render, and
   its styling was seven rules of `styles/legacy.css`. Both moved here with the
   component (L15): the rules are the same declarations written as utilities,
   term for term, and the oracle's `shell/bottom-bar` region is what says so.

   THE IDENTITY CLASSES STAY AT THE FRONT — `bottombar`, `ic`, `lb`,
   `navbadge`. `app/bar-height.ts` finds the bar by `.bottombar` (R84's one
   publisher) and rules select the badge by `.navbadge`; a name removed here
   would break a reader while the styling moved cleanly. */
export const tabBar = cva(
  "bottombar fixed inset-x-0 bottom-0 z-50 flex border-t border-border "
    + "bg-sidebar pb-[env(safe-area-inset-bottom)] md:hidden",
  {
    variants: {
      // SELECTION MODE HIDES THE BAR, and it is read from the store rather
      // than from `html.selecting` — the class the engine used to toggle for
      // this one rule. A mode is state, and state lives in one place (D-L15-3).
      selecting: { true: "hidden", false: "" },
    },
    defaultVariants: { selecting: false },
  },
);

export const tabBarButton = cva(
  "flex min-h-[44px] min-w-0 flex-1 basis-0 flex-col items-center justify-center "
    + "gap-2 py-4 text-3 [border:0] bg-transparent text-muted-foreground "
    + "transition-[color] duration-150 ease-standard",
  {
    variants: { current: { true: "text-primary-text", false: "" } },
    defaultVariants: { current: false },
  },
);

/* The icon's box, and it is `position: relative` for ONE reason: the badge is a
   CORNER SUPERSCRIPT on it, never a third flow child, which would make the tab
   taller. */
export const tabBarIcon = cva("ic relative inline-flex");

export const tabBarIconDrawing = cva("w-[20px] h-[20px] flex-none");

export const tabBarLabel = cva("lb overflow-hidden text-ellipsis whitespace-nowrap max-w-full");

/* PRIMARY, not danger: red is reserved for the « ? » of an unavailable
   counter. The outline is the sidebar's colour so the badge reads as lifted off
   the bar rather than punched into it. */
export const tabBarBadge = cva(
  "navbadge absolute right-[-10px] top-[-6px] inline-flex h-[18px] min-w-[18px] "
    + "items-center justify-center px-2 rounded-full bg-primary text-primary-foreground "
    + "text-2 font-semibold leading-none [font-variant-numeric:tabular-nums] "
    + "[box-shadow:var(--mq-shadow-badge)] [outline:2px_solid_var(--color-sidebar)]",
);

/* ── The action button ───────────────────────────────────────────────
   Anchored to the frame's bottom-right corner, ABOVE the published bar height
   and never at a distance to an edge. Its classes came verbatim from
   `index.html`, where the button was static markup the engine toggled.

   NAMED FOR ITS `data-part`, `shell/add-action`, because `actionButton` was
   already taken in `ui/variants/controls.ts` by the panel's own full-width
   button — two different things, and the barrel re-exports both. */
export const addAction = cva(
  "fab absolute right-[16px] bottom-[calc(var(--tm-bottom-bar-h,0px)+16px)] "
    + "w-[52px] h-[52px] rounded-full [border:0] bg-primary text-primary-foreground "
    + "grid place-items-center [box-shadow:var(--mq-shadow-fab)] z-30",
);

export const addActionDrawing = cva("w-[23px] h-[23px]");

/* ── The bottom slot's first occupant: the library's selection bar ───
   Its five rules came from `styles/legacy.css`, where they lived because the
   engine created the node. It is `position: absolute` against the phone frame
   and z-51 — ABOVE the tab bar, which is z-50, because it replaces it for the
   duration of a selection. */
export const selectionBar = cva(
  "selbar absolute left-0 right-0 bottom-0 z-[51] flex items-center gap-5 "
    + "pt-5 px-7 pb-[calc(env(safe-area-inset-bottom)+var(--spacing-5))] "
    + "bg-popover border-t border-border",
);

export const selectionCaption = cva("n text-3 font-semibold");

export const selectionAction = cva(
  "border border-border bg-transparent text-foreground text-3 font-semibold "
    + "py-4 px-6 rounded-3",
  {
    variants: {
      tone: {
        // `danger` is the identity class the residue used and rules select on.
        danger: "danger bg-danger-fill border-danger-fill text-white ml-auto "
          + "disabled:opacity-45",
        neutral: "",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

/* ── The message ─────────────────────────────────────────────────────
   Its box came verbatim from `index.html`, where the element was static markup
   the engine wrote into. `show` is the identity class the residue's one rule
   used and rules still select; what it MEANT — opaque, visible, at rest — is
   here now, so the residue keeps nothing. */
export const messageHost = cva(
  "toast absolute left-[14px] right-[14px] "
    + "bottom-[calc(var(--tm-bottom-bar-h,0px)+16px)] z-[49] flex items-center gap-5 "
    + "bg-popover border border-border rounded-3 py-5 px-6 text-3 "
    + "[box-shadow:var(--mq-shadow-toast)] transition-[opacity,transform] "
    + "duration-200 ease-standard",
  {
    variants: {
      shown: {
        true: "show opacity-100 visible [transform:none]",
        false: "opacity-0 invisible [transform:translateY(14px)]",
      },
    },
    defaultVariants: { shown: false },
  },
);

export const messageClose = cva(
  "ml-auto [border:0] bg-transparent text-muted-foreground w-[24px] h-[24px] "
    + "grid place-items-center flex-none",
);

/* THE UNDO WAS AN INLINE STYLE inside an `innerHTML` string — the one write of
   the nineteen a formatter could have hidden from the inventory command. Its
   five declarations are here, and the control is a real child. */
export const messageUndo = cva(
  "[border:0] bg-transparent text-primary font-bold pt-0 pr-0 pb-0 pl-[10px]",
);

/* ── The drawer ──────────────────────────────────────────────────────
   Eleven rules of `styles/legacy.css` and the `<aside>`'s own utilities from
   `index.html`, together at last: the engine wrote the drawer's children and
   the document declared its box, so its styling stood in two places. */
export const drawer = cva(
  "drawer absolute inset-y-0 left-0 right-auto w-[288px] max-w-[86%] z-[55] "
    + "bg-sidebar border-r border-border flex flex-col transition-[transform] "
    + "duration-300 ease-standard touch-pan-y "
    + "[&_a]:select-none [&_a]:[-webkit-user-drag:none]",
  {
    variants: {
      open: {
        true: "open [transform:none] visible",
        false: "[transform:translateX(-100%)] invisible",
      },
    },
    defaultVariants: { open: false },
  },
);

export const drawerHead = cva(
  "dh flex items-center gap-4 "
    + "pt-[calc(env(safe-area-inset-top)+var(--spacing-7))] px-7 pb-7 "
    + "border-b border-border text-5 font-semibold tracking-[-0.01em]",
);

export const drawerNavigation = cva(
  "flex-1 min-h-0 overflow-y-auto flex flex-col gap-2 p-4",
);

/* THE SEPARATOR IS A SIBLING RULE, and it stays one. `.grp + .grp` is what
   draws the line between two groups; expressing it per element would mean the
   FIRST group carrying a line it must not have. */
export const drawerGroup = cva(
  "grp [.grp+&]:border-t [.grp+&]:border-border [.grp+&]:mt-3 [.grp+&]:pt-5",
);

export const drawerGroupTitle = cva(
  "sect pt-5 px-6 pb-2 text-1 font-medium uppercase tracking-[0.08em] "
    + "text-muted-foreground",
);

export const drawerEntry = cva(
  "flex items-center gap-6 min-h-[44px] py-4 px-6 rounded-3 text-4 text-foreground",
  {
    variants: {
      current: {
        // « YOU ARE HERE » IS THE BRAND COLOUR ON THE LABEL — the same mark the
        // bottom bar uses, so one interface has one way of saying it. The row
        // also carries a surface, because a list is scanned and its current row
        // has to be found without reading five labels; that surface is a TINT
        // of the mark, never the mark itself. Painting the mark as the
        // background left the label exactly the colour of what it sat on:
        // contrast 1.00, a label written in invisible ink.
        true: "[background:color-mix(in_oklab,var(--color-primary)_14%,transparent)] "
          + "text-primary-text font-semibold",
        false: "",
      },
    },
    defaultVariants: { current: false },
  },
);

export const drawerEntryDrawing = cva("w-[20px] h-[20px] flex-none");

export const drawerEntryCount = cva(
  "count ml-auto inline-flex h-[18px] min-w-[18px] items-center justify-center "
    + "px-2 rounded-full bg-primary text-primary-foreground text-2 font-semibold "
    + "[font-variant-numeric:tabular-nums]",
);

export const drawerIdentity = cva(
  "ver border-t border-border pt-6 px-7 "
    + "pb-[calc(env(safe-area-inset-bottom)+var(--spacing-6))]",
);

export const drawerIdentityLabel = cva(
  "vt text-2 text-muted-foreground uppercase tracking-[0.06em] font-semibold",
);

export const drawerIdentityPrimary = cva("vv text-7 font-bold mt-1");

export const drawerIdentitySecondary = cva(
  "vc [font-family:ui-monospace,Menlo,monospace] text-2 text-muted-foreground mt-1",
);

/* ── The confirmation dialog ─────────────────────────────────────────
   Its rules were `styles/legacy.css`'s because the engine wrote its markup:
   the box, the two typographic rules, the action row, the three button tones,
   the simulation notice, the manifest and the warning. They are here now.

   THE RANK IS PART OF THE MOVE AND IS NOT CHANGED HERE. `z-48` is what it was,
   under the tab bar's `z-50` — which is B-237, and B-237 lands in a commit of
   its own with a rule that hit-tests rather than reads a number. */
export const dialog = cva(
  "dlg absolute left-[16px] right-[16px] top-1/2 z-[48] bg-popover "
    + "border border-border rounded-4 p-7 [box-shadow:var(--mq-shadow-dlg)] "
    + "transition-[opacity,transform] duration-200 ease-standard",
  {
    variants: {
      open: {
        true: "open opacity-100 visible [transform:translateY(-50%)_scale(1)]",
        false: "opacity-0 invisible [transform:translateY(-50%)_scale(0.96)]",
      },
    },
    defaultVariants: { open: false },
  },
);

export const dialogHeading = cva("mt-0 mx-0 mb-4 text-5 font-bold");

export const dialogParagraph = cva("mt-0 mx-0 mb-5 text-3 leading-[1.45]");

export const dialogDryRun = cva(
  "dryrun flex items-center gap-3 text-2 font-semibold text-info "
    + "[border:1px_solid_color-mix(in_oklab,var(--color-info)_40%,transparent)] "
    + "rounded-2 py-4 px-5 mb-5",
);

export const dialogDryRunDrawing = cva("w-[14px] h-[14px] flex-none");

export const dialogManifest = cva(
  "manifest list-none mt-0 mx-0 mb-5 p-0 text-3",
);

export const dialogManifestEntry = cva(
  "flex gap-4 py-2 px-0 border-b border-border text-muted-foreground last:border-b-0",
);

export const dialogManifestValue = cva(
  "text-foreground font-semibold ml-auto whitespace-nowrap",
);

export const dialogWarning = cva(
  "warnbox "
    + "[border:1px_solid_color-mix(in_oklab,var(--color-warning)_45%,transparent)] "
    + "[background:color-mix(in_oklab,var(--color-warning)_8%,transparent)] "
    + "rounded-2 py-4 px-5 text-3 leading-[1.45] mb-5 [&_b]:text-warning",
);

export const dialogActions = cva("dlgacts flex flex-col gap-3");

/* THE UNION OF TWO RESIDUE RULES, resolved the way the cascade resolved them.
   `.dlgbtn` was declared twice in `styles/legacy.css`: once on its own and once
   as the fifth name of the action-button system the engine emits. Both were
   unlayered, so the LATER rule won property by property — which is why the
   padding here is `py-5 px-6` and not the `p-5` the first rule asked for. A
   variant carrying only one of the two would have rendered identically (the
   residue wins over utilities) and disagreed with it, which is exactly the
   drift R80 exists to catch, and did. */
export const dialogButton = cva(
  "dlgbtn flex items-center justify-center gap-4 w-full min-h-[44px] py-5 px-6 "
    + "rounded-3 text-4 font-semibold text-center border border-border "
    + "bg-transparent text-foreground",
  {
    variants: {
      tone: {
        danger: "danger bg-danger-fill border-danger-fill text-white",
        ghost: "ghost text-muted-foreground border-transparent",
        neutral: "",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);
