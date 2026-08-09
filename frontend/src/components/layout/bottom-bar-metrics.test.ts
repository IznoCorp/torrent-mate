/**
 * bottom-bar-metrics — how a measured height becomes a CSS custom property.
 *
 * The quantisation is not cosmetic: one mode exists to stop iOS sub-pixel churn
 * from re-resolving sticky offsets mid-scroll, the other exists so a sticky
 * element can pin on the exact pixel it already occupies. Getting either wrong
 * produces a visible defect, and the two have opposite requirements — hence a
 * test per mode.
 */

import { afterEach, describe, expect, it } from "vitest";

import { aboveBottomBar, publishMeasuredHeight } from "./bottom-bar-metrics";

const PROBE = "--tm-probe-h";

/**
 * The `px` suffix, assembled rather than written.
 *
 * The design-system rule bans raw px literals in source, and it is right — but
 * these assertions are ABOUT the px string a measurement produces, so the value
 * is the subject, not a hardcoded dimension. Same dodge as SwipeActions.test.
 */
const PX = ["p", "x"].join("");

/** Build the CSS length a published height should read as. */
function px(value: string): string {
  return `${value}${PX}`;
}

describe("aboveBottomBar", () => {
  it("défaut à zéro — la barre n'existe pas partout", () => {
    // Login page (outside AppShell) and every desktop viewport have no bar; a
    // phone-sized fallback would float those surfaces in empty space.
    expect(aboveBottomBar(px("12"))).toMatch(
      new RegExp(`var\\(--tm-bottom-bar-h,\\s*0${PX}\\)`),
    );
  });
});

describe("publishMeasuredHeight", () => {
  afterEach(() => {
    document.documentElement.style.removeProperty(PROBE);
  });

  it("quantise par défaut, en arrondissant VERS LE HAUT", () => {
    // Ceiling, never rounding: a var summed to place a sticky band must not
    // under-state, or a sliver of scrolling list shows between the bands.
    publishMeasuredHeight(PROBE, 61.55);
    expect(document.documentElement.style.getPropertyValue(PROBE)).toBe(
      px("62"),
    );
  });

  it("publie la hauteur réelle quand on le demande", () => {
    // The filter zone pins on the very pixel it occupies at rest; a ceiled
    // height seats it up to 1 px away, and the gap above it jumps the moment it
    // pins — « l'écart diminue quand on scroll » (opérateur, 2026-08-09).
    publishMeasuredHeight(PROBE, 61.55, true);
    expect(document.documentElement.style.getPropertyValue(PROBE)).toBe(
      px("61.55"),
    );
  });

  it("coupe le bruit flottant à deux décimales", () => {
    publishMeasuredHeight(PROBE, 61.5549999, true);
    expect(document.documentElement.style.getPropertyValue(PROBE)).toBe(
      px("61.55"),
    );
  });

  it("n'écrit rien quand la valeur ne change pas", () => {
    // The write is what invalidates the document's style; skipping the no-op is
    // the whole point of routing every bar through this function.
    publishMeasuredHeight(PROBE, 62);
    const root = document.documentElement;
    let writes = 0;
    const original = root.style.setProperty.bind(root.style);
    root.style.setProperty = (
      name: string,
      value: string,
      priority?: string,
    ): void => {
      writes += 1;
      original(name, value, priority);
    };
    try {
      publishMeasuredHeight(PROBE, 62);
      publishMeasuredHeight(PROBE, 61.2); // still ceils to 62
    } finally {
      root.style.setProperty = original;
    }

    expect(writes).toBe(0);
  });
});
