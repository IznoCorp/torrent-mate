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
