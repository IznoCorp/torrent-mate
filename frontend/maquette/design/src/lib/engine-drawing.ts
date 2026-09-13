// the engine's DRAWING surface — what emits markup or formats a value
//
// The slice of `window.__referentiel` this layer reads, and nothing else.
//
// The engine publishes ONE object; what it publishes is not one subject. A
// single 340-line declaration of all of it made every module that needed two
// members depend on all hundred and eight, and seventeen of twenty-five
// modules did. Each slice is declared where its subject lives instead, and the
// global's own type is their intersection (app/reference.d.ts) — so a
// reader imports nothing to be typed, and a member nobody's subject claims has
// nowhere to be written down.

import type { QueueCard } from "./engine-queue";

// The card builder's own descriptor — a small, typed slice of what
// `cardHTML` accepts, limited to the fields a search-result row actually
// fills. `cardHTML` itself stays untyped JS (defined in refonte.html); this
// type exists only so a migrated screen calls it with the right shape.
export type CardDescriptor = {
  t: string;
  k: "movie" | "show";
  s?: string;
  overview?: string;
  chip?: [string, string] | null;
  panel?: string;
};

// A card's FOOT, the only options `cardHTML` takes. `footAct` becomes the
// `data-act` attribute the document-level delegation reads, which is why it is
// a string and not a handler.
export type CardFoot = {
  foot?: string;
  footAct?: string;
  footSolid?: boolean;
  footTone?: string;
  footDone?: boolean;
};

// Read-only reference data + pure rendering helpers the engine's own script
// publishes once, at definition time — well before any component's module
// evaluates (see shell.tsx's boot-order comment). None of it is ever
// mutated after that publish, so a plain accessor is the right shape here,
// not a subscription: there is nothing for a component to miss by reading
// it straight, and useSyncExternalStore would just add a subscription with
// no writer ever calling it.
//
// `cardHTML` / `addVerb` are reused VERBATIM rather than re-implemented in
// JSX: a search-result card carries `data-panel="add:N"` / `data-mediasheet`
// attributes that the legacy document-level click delegation still reads
// to open the panel or the media sheet (the strangler seam a migrated
// screen leans on rather than replaces) — re-deriving that markup by hand
// would risk drifting the one thing that seam depends on being byte-exact.
// `render` is the legacy page redraw (`#view`, nav, deck, loaders, search
// bar) — exposed so a screen leaving a router-owned route back onto legacy
// ground (see `add.tsx`'s "Voir mes suivis") can bring that ground up to
// date the same way every other legacy navigation control already does,
// since nothing subscribes the legacy side to the store automatically.
//
// One row of a fact list, exactly as `ui/fact-rows.tsx` draws one. `ton` is
// the operator's vocabulary (`success` / `alert` / `warning` / `info`) and the
// component maps it onto the chip's; `target` becomes the row's `data-*`
// attributes, which is what turns the row into the control.
export type Fact = {
  l: string;
  v?: string;
  s?: string;
  k?: string;
  ton?: string;
  state?: string;
  target?: Record<string, string>;
};

export type EngineDrawing = {
  // The SECOND parameter is the fragment's own, and it was missing here: a
  // card's foot is an option, not a property of the medium — `foot` is its
  // label, `footAct` the `data-act` the delegation reads, and the three others
  // decide how it looks and whether it is spent. A queue card is a looser shape
  // than a search result's descriptor (the engine's own world objects carry
  // more), so both are accepted, exactly as the fragment accepts them.
  cardHTML: (
    descriptor: CardDescriptor | QueueCard,
    options?: CardFoot,
  ) => string;
  svgIcon: (paths: string, strokeWidth?: number) => string;
  icons: Record<string, string>;
  escapeHtml: (text: string) => string;
  initials: (name: string) => string;
  baseTitle: (title: string) => string;
  POSTERS: Record<string, string>;
  render: () => void;
  toast: (msg: string) => void;
  plages: (nums: number[]) => string;
  // `dateFR` returns null on a falsy `iso`, exactly like `sheetFor` on an
  // unresolved title — a sheet's air dates are frequently unset (an
  // announced-but-unaired episode) and the caller decides what to show.
  dateFR: (iso: string) => string | null;
};

/**
 * Reads the engine's drawing surface.
 *
 * For the two readers that need nothing else: a `ui/` primitive, which may not
 * import a feature, and the shell's own not-found page, which belongs to no
 * domain. A feature reads these members through its own slice, which
 * intersects this one — same object, one destructure.
 *
 * Returns:
 *     The drawing surface, typed.
 */
export function useEngineDrawing(): EngineDrawing {
  return window.__referentiel;
}

/**
 * Resolves what a title's poster shows, from the engine's poster table.
 *
 * A proposition rather than an identity asks for its OWN picture only (`exact`):
 * « Lucky (2006) » and « Lucky! » are different series the operator is asked to
 * tell apart, and matching on the base title would hand one the picture of the
 * other on the very screen whose job is to distinguish them.
 *
 * Args:
 *     drawing: The engine's drawing surface.
 *     title: The title.
 *     kind: `movie` or `show`, which picks the fallback's icon.
 *     exact: Whether only the title's own picture will do.
 *
 * Returns:
 *     The picture if there is one, the fallback's icon, and its label.
 */
export function posterArtworkFor(
  drawing: Pick<EngineDrawing, "POSTERS" | "baseTitle" | "icons" | "initials">,
  title: string,
  kind?: string,
  exact?: boolean,
): { source: string | undefined; icon: string; label: string } {
  const source = exact
    ? drawing.POSTERS[title]
    : (drawing.POSTERS[title] ?? drawing.POSTERS[drawing.baseTitle(title)]);
  const icon =
    kind === "movie" ? drawing.icons.film : kind === "show" ? drawing.icons.tv : drawing.icons.clap;
  return { source, icon, label: drawing.initials(title) };
}
