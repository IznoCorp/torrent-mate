// What a surface built as a markup STRING needs to write safely: an icon, and a
// value that cannot be read as markup.
//
// PURE, AND SHARED: the cards, the rows, the tiles and the not-found page all
// build markup strings, and a feature may not import another (invariant 7).
// React escapes a text node itself; a string handed to `Markup` is not escaped
// by anything, so every value interpolated into one goes through here.

/**
 * An icon as the markup string a `Markup` host injects — the same shape
 * `ui/icon.tsx` draws as a component.
 *
 * @param paths The icon's SVG path elements, as markup.
 * @param strokeWidth The stroke's width; 2 when absent.
 * @returns The `<svg>` element, as markup.
 */
export function svgIcon(paths: string, strokeWidth?: number): string {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${strokeWidth || 2}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
}

// The four characters that can open or close markup inside an element or a
// double-quoted attribute. A single quote is not among them: no string here is
// ever interpolated into a single-quoted attribute.
const ESCAPED: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" };

/**
 * A value made safe to interpolate into markup.
 *
 * @param value The value; anything, turned into its string first.
 * @returns The string with `&`, `<`, `>` and `"` written as entities.
 */
export function escapeHtml(value: unknown): string {
  return String(value).replace(/[&<>"]/g, (character) => ESCAPED[character]);
}
