/**
 * Shared number/size formatting helpers.
 *
 * French-locale unit conventions: ``Go`` (gigaoctet) and ``To`` (téraoctet).
 */

/**
 * Format a size in gigaoctets adaptively — ``Go`` below 1024, ``To`` above.
 *
 * One decimal maximum, with a trailing ``.0`` stripped so round values render
 * bare (``"12 Go"``, not ``"12.0 Go"``). Large libraries no longer display as
 * ``"20658.0 Go"`` but as ``"20.2 To"`` (U1, operator-reported).
 *
 * Args:
 *   gb: The value in gigaoctets.
 *
 * Returns:
 *   A formatted string like ``"238.5 Go"``, ``"12 Go"``, or ``"20.2 To"``.
 */
export function formatGb(gb: number): string {
  const inTb = gb >= 1024;
  const value = inTb ? gb / 1024 : gb;
  const rendered = value.toFixed(1).replace(/\.0$/, "");
  return `${rendered} ${inTb ? "To" : "Go"}`;
}
