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

import type { Artwork } from "../ui/poster";
import { initials } from "./titles";

// Read-only reference data + pure rendering helpers the engine's own script
// publishes once, at definition time — well before any component's module
// evaluates (see shell.tsx's boot-order comment). None of it is ever
// mutated after that publish, so a plain accessor is the right shape here,
// not a subscription: there is nothing for a component to miss by reading
// it straight, and useSyncExternalStore would just add a subscription with
// no writer ever calling it.
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
  icons: Record<string, string>;
};

/**
 * Reads the engine's drawing surface.
 *
 * For the readers that need nothing else: a `ui/` primitive, which may not
 * import a feature, and a feature reading nothing but the icons. A feature
 * reading more reads these members through its own slice, which intersects
 * this one — same object, one destructure.
 *
 * Returns:
 *     The drawing surface, typed.
 */
export function useEngineDrawing(): EngineDrawing {
  return window.__referentiel;
}

/**
 * What a poster shows: the list's own picture, or the fallback's icon and label.
 *
 * @param icons The icon paths.
 * @param source The picture the list carries for the medium, or nothing.
 * @param title The title, whose initials the fallback shows.
 * @param kind `movie` or `show`, which picks the fallback's icon.
 * @returns The artwork.
 */
export function posterArtwork(
  icons: Record<string, string>,
  source: string | null | undefined,
  title: string,
  kind?: string,
): Artwork {
  const icon = kind === "movie" ? icons.film : kind === "show" ? icons.tv : icons.clap;
  return { source: source ?? undefined, icon, label: initials(title) };
}

