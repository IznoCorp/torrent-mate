// The releases a title turns up — the one list the release read, a follow's
// search and « Abandonner » on a follow's card all read, so a release tried and
// abandoned leaves all three at once.
import RELEASES from "../seeds/releases.json";
import { mockState } from "../state";

const DECOMPOSED_FORM = "NFD";
const ACCENT_MARK = /[\u0300-\u036f]/g;
const SEPARATOR = /[^\p{Ll}\p{Nd}]/gu;

/**
 * A title or a release name reduced to what the two have in common.
 *
 * A RELEASE NAME SPELLS A TITLE WITH DOTS, and without its accents or its
 * punctuation: « L'Odyssée » is `L.Odyssee.2026…`. Compared as written, every
 * title of more than one word matched no release at all — the same list that
 * does not depend on what it is a list of, reached through the spelling.
 *
 * @param spelled A title or a release name.
 * @returns The letters and digits, lower-cased, accents removed.
 */
function matchingKey(spelled: string): string {
  return spelled.normalize(DECOMPOSED_FORM).replace(ACCENT_MARK, "")
    .toLowerCase().replace(SEPARATOR, "");
}

// What a release name says it is of: an episode (`S03E07`), or a whole season (`S03`).
const EPISODE_MARK = /S(?<season>\d+)E(?<episode>\d+)/i;
const SEASON_MARK = /(?:^|[^A-Za-z0-9])S(?<season>\d+)(?:[^A-Za-z0-9]|$)/i;

/**
 * What one release is of, read off its name once, so the answer carries it as a field (SR6).
 *
 * @param name The release name.
 * @returns Its season and episode, each null when the name does not say.
 */
function numberingOf(name: string): { season: number | null; episode: number | null } {
  const episode = EPISODE_MARK.exec(name)?.groups;
  if (episode !== undefined) return { season: Number(episode.season), episode: Number(episode.episode) };
  const season = SEASON_MARK.exec(name)?.groups;
  return { season: season === undefined ? null : Number(season.season), episode: null };
}

/**
 * The releases a search for one title turns up, each with its handle and what it is of.
 *
 * THE HANDLE IS THE SEED'S POSITION: the picker chooses a release by it, never by
 * its name, which a tracker may publish twice.
 *
 * @param title The medium's title, as the interface spells it.
 * @returns Every seeded release whose name carries that title.
 */
export function releasesFor(title: string) {
  const wanted = matchingKey(title);
  // A RELEASE ALREADY TRIED AND ABANDONED IS NOT OFFERED AGAIN (§14.1).
  const abandoned = mockState().triedReleases[title] ?? [];
  return RELEASES
    .map((release, position) => ({
      id: String(position + 1),
      ...release,
      ...numberingOf(String(release.name ?? "")),
    }))
    .filter((release) => matchingKey(String(release.name ?? "")).includes(wanted)
      && !abandoned.includes(String(release.name ?? "")));
}
