// THE NAMES AN ARRIVAL IS MARKED WITH, in one place.
//
// `app/artwork-arrival.ts` writes them, `styles/base.css` draws them and the
// harness reads them. A contract has three ends and they move in ONE step or
// the interface half-works in a way no single file reveals — which is why the
// values live here rather than being spelled out at each of the three.

/** The element the fanart is painted on, as the media screen emits it. */
export const HERO_BACKGROUND = '[data-part="hero/background"]';

/**
 * How the artwork got here, and therefore who draws its entry.
 *
 * `immediate` — decoded before the first frame, so the file was cached and the
 * view transition already carried the picture. Nothing else may animate it:
 * one entry, one owner.
 *
 * `faded` — decoded later, so the transition finished over a hero with no
 * picture in it. This one owns its own entry and the stylesheet fades it.
 */
export const ARTWORK_ARRIVAL = {
  immediate: "immediate",
  faded: "faded",
} as const;
