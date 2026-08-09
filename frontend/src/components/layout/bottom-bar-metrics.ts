/**
 * Geometry the bottom bar publishes, and the expression for sitting above it.
 *
 * Its own module rather than living beside the component: these are values, not
 * components, and both the toast host (`App.tsx`) and the acquisition « + »
 * import them without pulling in the bar itself.
 */

/**
 * CSS custom property carrying this bar's REAL rendered height.
 *
 * Anything that must sit just above the bar reads it — the toast dock (§10) and
 * the acquisition « + ». It exists because the alternatives are both wrong: a
 * literal (`bottom: 84px`) was the original defect, calibrated on desktop and
 * sliding under the bar on iPhone where `env(safe-area-inset-bottom)` adds
 * ~34 px; and a hardcoded `calc()` over that env() still guesses the bar's own
 * content height. Measuring is the only expression that stays true at any bar
 * height, on any device, after any rotation.
 *
 * Consumers MUST default it to `0px`: two real cases have no bar at all — the
 * login page (rendered outside `AppShell`) and every desktop viewport (this bar
 * is `md:hidden`). A phone-sized fallback would float them in empty space.
 */
export const BOTTOM_BAR_HEIGHT_VAR = "--tm-bottom-bar-h";

/** Measured sticky-topbar height, published by Topbar (same contract). */
export const TOPBAR_HEIGHT_VAR = "--tm-topbar-h";

/** Measured view-tabs height, published by AcquisitionPage (same contract). */
export const VIEWTABS_HEIGHT_VAR = "--tm-viewtabs-h";

/**
 * Build a CSS length that sits `gap` above the bottom bar, whatever its height.
 *
 * Every surface anchored above the bar goes through this — the toast (§10) and
 * the acquisition « + » — so there is one expression to get right instead of one
 * per caller drifting apart. The `0px` default is load-bearing, not defensive:
 * see {@link BOTTOM_BAR_HEIGHT_VAR}.
 *
 * Args:
 *   gap: A CSS length for the space between the bar and the surface.
 *
 * Returns:
 *   A `calc()` expression usable anywhere a CSS length is accepted.
 */
export function aboveBottomBar(gap: string): string {
  return `calc(var(${BOTTOM_BAR_HEIGHT_VAR}, 0px) + ${gap})`;
}


/**
 * Publish a measured height as a CSS custom property — but ONLY on change.
 *
 * The three bars each observe themselves and write their height to
 * `:root`. On iOS that write is not free: scrolling collapses and expands the
 * URL bar, which changes the visual viewport AND `env(safe-area-inset-*)`, so
 * the observed elements resize CONTINUOUSLY while the finger is down. Every
 * write invalidates the whole document's style, and the sticky filter zone —
 * positioned at `top: calc(var(--tm-topbar-h) + var(--tm-viewtabs-h))` —
 * re-resolves its offset mid-scroll. That is a shimmer, and it is self
 * inflicted.
 *
 * Two guards, both cheap: quantise to the whole pixel (sub-pixel churn from
 * the toolbar animation is noise, not information), and skip the write when
 * the value is what is already there.
 *
 * `ceil`, deliberately, not `round`: two of these vars are SUMMED to place the
 * sticky filter zone (`top: calc(var(--tm-topbar-h) + var(--tm-viewtabs-h))`).
 * Rounding a real height DOWN would seat that zone a fraction too high and
 * open a sliver of list content between the two sticky bands during scroll —
 * trading one visual defect for another. Ceiling never under-states.
 *
 * `exact` opts out of the quantisation, and one consumer needs it. When a var
 * places a sticky element that must land on the SAME pixel as its own flow
 * position, rounding is not conservative — it is the defect: it seats the
 * pinned element up to a pixel away from where it sits at rest, so the gap
 * above it CHANGES the moment it pins (operator, 2026-08-09: « l'écart entre le
 * changement d'onglet et le champ filtrer par nom diminue quand on scroll »).
 * Only use it for a var whose element does not resize during a scroll —
 * anything the iOS URL bar can squeeze must stay quantised, or the sub-pixel
 * churn comes back as a shimmer.
 *
 * Args:
 *   varName: The custom property to publish.
 *   height: The freshly measured height, in CSS pixels.
 *   exact: Publish the real height instead of its ceiling.
 */
export function publishMeasuredHeight(varName: string, height: number, exact = false): void {
  const root = document.documentElement;
  // Two decimals, not the raw float: device-pixel arithmetic never needs more,
  // and it keeps the "skip if unchanged" guard from firing on float noise.
  const next = exact ? `${String(Math.round(height * 100) / 100)}px` : `${String(Math.ceil(height))}px`;
  if (root.style.getPropertyValue(varName) === next) return;
  root.style.setProperty(varName, next);
}
