// WHAT THE IDENTIFIER FIELD SHOWS, AND HOW AN IDENTIFIER IS ASKED (B-691).
//
// « Pour l'ajout d'un suivi, par identifiant, il est noté « 1234 » comme exemple.
// Je teste 1234 et cela ne fonctionne pas » — the field showed one number for
// TMDB and TVDB alike, an identifier no medium carries. Each source now shows an
// identifier in its own format that the provider search knows, so the example,
// typed as it is, adds a medium: Les Aventures des Petits Jedi under TMDB and
// TVDB, The Clone Wars (the film) under IMDB — none of them owned.

/** The three sources an identifier is typed for. */
export type IdProvider = "TMDB" | "TVDB" | "IMDB";

/** One example per source, in that source's own format. */
export const ID_EXAMPLES: Record<IdProvider, string> = {
  TMDB: "202998",
  TVDB: "420658",
  IMDB: "tt1185834",
};

/**
 * Whether a typed identifier has its source's format: « tt » and digits for
 * IMDB, digits only for TMDB and TVDB.
 *
 * Args:
 *     provider: The source chosen.
 *     typed: What the field holds.
 *
 * Returns:
 *     True when the identifier can be asked of the source.
 */
export function validId(provider: IdProvider, typed: string): boolean {
  return (provider === "IMDB" ? /^tt\d+$/ : /^\d+$/).test(typed.trim());
}

/**
 * The provider search's question for one identifier: the source, lower case,
 * then the identifier — « tmdb:202998 ».
 *
 * Args:
 *     provider: The source chosen.
 *     id: The identifier typed.
 *
 * Returns:
 *     The search's text.
 */
export function idQuery(provider: IdProvider, id: string): string {
  return `${provider.toLowerCase()}:${id.trim()}`;
}
