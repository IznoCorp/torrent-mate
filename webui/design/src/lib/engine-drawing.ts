// the engine's DRAWING surface — what emits markup or formats a value
//
// What every layer draws with: the icon paths, read through the frame's door
// (`lib/shell-doors.ts`), and the poster fallback built from them.

import type { Artwork } from "../ui/poster";
import { icons } from "./shell-doors";
import { initials } from "./titles";

// The icon paths are filled once, by the boot, before anything is drawn, and
// never written again — so a plain accessor is the right shape here, not a
// subscription: there is nothing for a component to miss by reading it
// straight, and useSyncExternalStore would add a subscription no writer calls.
export type EngineDrawing = {
  icons: Record<string, string>;
};

/**
 * Reads the drawing surface: the icon paths the boot filled the door with.
 *
 * For every component that draws an icon — a `ui/` primitive, which may not
 * import `app/`, and a feature, which may not either.
 *
 * Returns:
 *     The drawing surface, typed.
 */
export function useEngineDrawing(): EngineDrawing {
  return { icons };
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

