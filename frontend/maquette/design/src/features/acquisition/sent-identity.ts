// The provider pair a follow's create sends.
//
// THE CONTRACT'S CREATE BODY CARRIES ONE PAIR, `provider` and a NUMBER
// `providerId`, while an emitter carries the medium's whole identity — so one
// identifier is chosen here, the first one that READS as a number.
//
// AN IDENTIFIER WRITTEN AS DIGITS IS A NUMBER (B-673). The library spells many
// identifiers as strings (`"tmdb": "82"`); taking only a typed number sent no
// identity at all for 89 library sheets, and the layer refused their follow. A
// title-shaped identifier (imdb's `tt…`) is still never the one sent.

// An identifier that is a number written as a string.
const DIGITS = /^\d+$/;

/**
 * The provider pair a create sends for an identity, or nothing.
 *
 * @param ids The identity the act carries, or nothing.
 * @returns `{ provider, providerId }`, or an empty object when no identifier reads as a number.
 */
export function sentIdentity(
  ids: Record<string, unknown> | null | undefined,
): { provider?: string; providerId?: number } {
  for (const [provider, value] of Object.entries(ids ?? {})) {
    if (typeof value === "number") return { provider, providerId: value };
    if (typeof value === "string" && DIGITS.test(value)) return { provider, providerId: Number(value) };
  }
  return {};
}
