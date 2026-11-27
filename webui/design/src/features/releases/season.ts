// releases — the season a release covers, read from the release itself
//
// The release read serves `season` and `episode` on every release (demand SR6),
// so nothing here parses a name.
import type { Release } from "./types";

/**
 * The season a release covers ONE episode of, read from the fields the engine
 * serves on the release itself (`season`, `episode`), never from its name.
 *
 * @param release The release.
 * @returns The season, or null for a pack (no episode), a film, or a release
 *     the engine numbered nothing for.
 */
export function episodeSeason(release: Pick<Release, "season" | "episode">): number | null {
  return release.episode != null ? release.season : null;
}
