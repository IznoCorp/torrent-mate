// A poster's artwork: the picture when there is one, otherwise the fallback — an
// icon and the title's initial on a tinted ground.
//
// IT KNOWS NO MEDIUM (invariant 10): it takes a picture, an icon and a label.
// Which picture and which icon a title gets is resolved before it is drawn, in
// one place, so the card, the panel and the deck cannot disagree about it.
//
// TWO SPELLINGS OF ONE DRAWING. The component is for React surfaces; the markup
// is for the surfaces still composed as strings. They emit the same element,
// attribute for attribute — the fallback's icon is the one `ui/icon.tsx` draws.
import type { ReactElement } from "react";
import { Icon } from "./icon";
import { escapeMarkup } from "./markup";
import { posterFallback } from "./variants";

/** What a poster shows: a picture if there is one, otherwise an icon and a label. */
export type Artwork = { source: string | undefined; icon: string; label: string };

/**
 * A poster's artwork, as an element.
 *
 * @param properties The artwork.
 * @returns The picture, or the fallback.
 */
export function PosterArtwork({ artwork }: { artwork: Artwork }): ReactElement {
  if (artwork.source) return <img src={artwork.source} alt="" loading="lazy" />;
  return (
    <span className={posterFallback()} data-part="card/poster-fallback">
      <Icon paths={artwork.icon} strokeWidth={1.25} />
      <b>{artwork.label}</b>
    </span>
  );
}

/**
 * A poster's artwork, as markup.
 *
 * @param artwork The artwork.
 * @returns The picture, or the fallback, as a string.
 */
export function posterArtworkMarkup(artwork: Artwork): string {
  if (artwork.source) return `<img src="${artwork.source}" alt="" loading="lazy">`;
  return (
    `<span class="${posterFallback()}" data-part="card/poster-fallback">` +
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${artwork.icon}</svg>` +
    `<b>${escapeMarkup(artwork.label)}</b></span>`
  );
}
