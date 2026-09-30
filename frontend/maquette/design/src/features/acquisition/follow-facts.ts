// WHAT IS TRUE ABOUT ONE MEDIUM, gathered once.
//
// The follow panel's every action is derived from these facts and nothing else
// — never from the screen the panel was opened from. That is what makes the
// panel THE SAME OBJECT everywhere, instead of a family of look-alikes, and it
// is the sentence the engine's producer carried at the top of its own body.
//
// SPLIT OUT OF THE PRODUCER on a SUBJECT rather than on a line count
// — the answer this repository has now taken three times, and it is written
// down in `scripts/frontend_size_ledger.py`'s own reason for existing: a file is
// split on a SUBJECT, never on a line count. What is true about a medium is one
// question, and what the panel OFFERS about it is another.
//
// READ FROM THE SAME DERIVATIONS the urgency sections read. A section that
// computes what is to be grabbed while the panel computes it separately is two
// answers to one question, and they part company on the first change (§13).
import { heldIdentity, providerAddress } from "../../lib/held-identity";
import { membershipQuery, type Membership } from "../../lib/membership";
import { completenessHeld, completenessQuery, seasonsQuery, seasonsHeld, type FollowCompleteness, type SeasonsAnswer } from "../../lib/season-rows";
import { queueKey, queueNow, type AcquisitionQueue } from "../../lib/queue";
import { store } from "../../lib/store-access";
import type { PanelCache } from "../../ui/panel/contract";
import { followsQuery, incompleteShowsQuery } from "./queries";

// THE FEATURE'S OWN RECORD, not a looser copy of it. A slice declared here
// would be a second shape of one thing, and the vocabulary the panel hands on —
// `followStatusLabel`, `STATUS_TONE`, the seasons block — is typed against the real one. The
// fallback below therefore fills every required field rather than leaving them
// undefined, which is what the engine's object literal did in practice.
import type { Follow, FollowSubject } from "./types";
import { followFraction } from "./follow-vocabulary";
import { inFlightCards, setAsideCards, todoCards } from "./arrival-slots";
import { originLine } from "./card-markup";
import { followOffered } from "./follow-offer";

// The contract's token for a season asked once, in the application.
const ASKED_ONCE = "request";

export type { Follow };

/** What is true about the medium a follow panel is about. */
export type FollowFacts = {
  follow: FollowSubject;
  /** Number, episodes aired (null when the answer gives no count), episodes held. */
  seasons: [number, number | null, number][];
  /** The medium has an identity and its seasons read has not landed yet. */
  seasonsPending: boolean;
  isFilm: boolean;
  /** In the library and missing episodes. */
  incomplete: boolean;
  /** Watched: something is looking for it. */
  isFollowed: boolean;
  inLibrary: boolean;
  /** Waiting to be taken. */
  toTake: boolean;
  /** Waiting for the operator to resolve it. */
  toResolve: boolean;
  /** In « À traiter », a Plex match to confirm or correct. */
  plexMatch: boolean;
  /** In « À traiter », a step that cannot finish: relaunched or abandoned, never resolved. */
  tunnelError: boolean;
  /** In the folded « Mis de côté »: kept on the disk until he deletes it or handles it. */
  setAside: boolean;
  /** It has a media sheet — an unidentified release has none. */
  hasSheet: boolean;
  /** An arrived series nobody follows: « Suivre » is proposed (ruling 1), with its identity. */
  followOffer: Record<string, unknown> | null;
  /** Episodes held over episodes aired, or null for a film. */
  fraction: string | null;
  /** Where its acquisition came from, whole — the line its card may truncate. */
  origin: string | null;
};

/**
 * Gathers what is true about one medium.
 *
 * THE FALLBACK CHAIN IS THE ENGINE'S, unchanged: a follow if one is watched, an
 * incomplete series if the library holds one with holes, and otherwise a
 * synthetic record saying the medium is up to date. A panel opened about a
 * medium nobody follows still has facts to state.
 *
 * Args:
 *     title: The medium.
 *     cache: What the query cache holds.
 *
 * Returns:
 *     The facts, or null while the follows have not landed — the one read this
 *     panel cannot draw without.
 */
export function followFacts(title: string, cache: PanelCache): FollowFacts | null {
  const followed = cache.held<Follow[]>(followsQuery.queryKey);
  // NOT BEFORE WHAT IT STATES HAS LANDED: a panel drawn without the membership
  // or the incomplete shows says « not in the library » and « complete » about
  // a medium it simply has not asked about yet.
  const membership = cache.held<Membership>(membershipQuery(title).queryKey);
  const incompleteAnswer = cache.held<{ title: string; owned: number; aired: number }[]>(
    incompleteShowsQuery.queryKey);
  if (followed === undefined || membership === undefined || incompleteAnswer === undefined)
    return null;
  // THE SERVED ANSWERS, every one of them: the incomplete shows, the
  // membership and the seasons are read from the cache the layer fills, never
  // from a copy the layer does not write.
  const incompleteShows = incompleteAnswer;
  const follow: FollowSubject =
    followed.find((one) => one.title === title) ??
    incompleteShows
      .map((show) => ({
        title: show.title, kind: "show", year: "", status: "to_grab", owned: show.owned, aired: show.aired,
      }))
      .find((one) => one.title === title) ??
    // THE KIND IS THE MEDIUM'S OWN, as the library answers it for this very
    // title — a film nobody follows was drawn as a series (B-581) — and a
    // series only when the library does not hold it either.
    { title, kind: membership.kind ?? "show", year: "", status: "up_to_date" };
  const address = providerAddress(follow.ids ?? heldIdentity(title)?.ids);
  const seasonsAnswer = address
    ? cache.held<SeasonsAnswer>(seasonsQuery(address.provider, address.id).queryKey)
    : undefined;
  const isFollowed = followed.some((one) => one.title === title);
  // A FOLLOWED SERIES READS THE ENGINE'S OWN COMPLETENESS (NE-DOIT-PAS-1): the
  // Médiathèque sheet reads the same answer, so the two cannot disagree. A
  // medium nobody follows keeps the figures its seasons read crosses.
  const completeness = isFollowed
    ? cache.held<FollowCompleteness>(completenessQuery(title).queryKey)
    : undefined;
  const seasons = (isFollowed ? completenessHeld(completeness) : seasonsHeld(seasonsAnswer))
    .slice()
    .sort((one, other) => other[0] - one[0]);
  const isFilm = follow.kind === "movie";
  const incomplete = incompleteShows.some((show) => show.title === title);
  const inLibrary = incomplete || membership.inLibrary;
  const queue = queueNow();
  const toTake = queue.takeable.some((one) => one.title === title);
  const scenario = String(store.read().state.scen) === "loaded" ? "loaded" : "";
  const answer = cache.held<AcquisitionQueue>(queueKey(scenario));
  const todo = answer ? todoCards(answer).find((one) => one.title === title) : undefined;
  const arrival = answer?.arrivals.find((one) => one.title === title);
  const acquisition = todo ?? (answer ? inFlightCards(answer).find((one) => one.title === title) : undefined);
  // WHAT MAY BE OFFERED « Suivre »: an arrival, or a season asked once — a
  // one-off acquisition of a series nobody follows (round 10 Q2).
  const offered = arrival ?? (acquisition?.requester?.via === ASKED_ONCE ? acquisition : undefined);
  const toResolve = queue.blocked
    .concat(queue.stuck ?? [])
    .some((one) => one.title === title);
  const held = seasons.reduce((total, season) => total + season[2], 0);
  const aired = seasons.reduce((total, season) => total + (season[1] ?? 0), 0);
  return {
    follow,
    seasons,
    seasonsPending: (address !== null && seasonsAnswer === undefined) || (isFollowed && completeness === undefined),
    isFilm,
    incomplete,
    isFollowed,
    inLibrary,
    toTake,
    toResolve,
    // THE SAME CARD, THE SAME ANSWERS: what « À traiter » offers at a card's
    // foot, its panel offers too (R43, one card, one behaviour).
    plexMatch: todo?.plexMatch !== undefined,
    tunnelError: todo?.failedStep !== undefined,
    setAside: answer ? setAsideCards(answer).some((one) => one.title === title) : false,
    hasSheet: (follow.ids ?? heldIdentity(title)?.ids) != null,
    // THE SAME OFFER THE CARD'S FOOT MAKES, from the same derivation (R43).
    followOffer: offered !== undefined && followOffered(offered, followed) ? offered.ids ?? null : null,
    origin: acquisition ? originLine(acquisition) ?? null : null,
    // ONE DERIVATION: the card's fraction, the header's, and the sum of the
    // season headers all read this computation.
    fraction: isFilm
      ? null
      : seasons.length
        ? `${held}/${aired}`
        : (followFraction(follow) ?? "—"),
  };
}
