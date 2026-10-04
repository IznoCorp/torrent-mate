// WHICH RIGHT EACH ACT OF AN ACQUISITION ASKS FOR — the offer side of § 17, for
// every act a card's foot or a panel carries.
//
// An act is known by the `data-*` verb its target names (`lib/verbs` answers
// them), so one table keyed by that verb gates the panel's actions and the
// card's feet alike: an act the account may not exercise is ABSENT — not
// greyed, not present-and-refused (§ 17 point 1). `own` adds « on an
// acquisition the account asked for » (§ 17's own tunnel, F27): a role that
// sees everyone's reads the others' cards, it does not act on them.
import type { Right, Rights } from "../../lib/rights";
import { isOwn } from "../../lib/rights";
import type { MediumCardFoot } from "./card-markup";
import { sharedQueryClient } from "../../lib/query-client";

/**
 * What one verb asks for. `sole` adds « and nobody else asked for it »: an act on
 * the WHOLE acquisition, which a co-requester may not take for the others
 * (round 10 Q6) — `acquisition.pilot.any` lifts it, as it lifts `own`.
 */
type Asked = { rights: readonly Right[]; own?: true; sole?: true };

// Piloting a tunnel: one's own acquisition, or any.
const PILOT: Asked = { rights: ["acquisition.pilot.own", "acquisition.pilot.any"], own: true };
// Deciding for the pipeline: staging, decisions, Plex matches.
const PIPELINE: Asked = { rights: ["pipeline.control"] };
// Managing one's own follow.
const FOLLOW: Asked = { rights: ["acquisition.follow"], own: true };

/** Every act of an acquisition's card or panel, by its verb. Unlisted verbs — a sheet, a journey — are reads. */
const ACTS: Readonly<Record<string, Asked>> = {
  "plex-confirm": PIPELINE,
  "plex-correct": PIPELINE,
  resolution: PIPELINE,
  "decision-correct": PIPELINE,
  "journey-abandon": PIPELINE,
  "staging-delete": PIPELINE,
  "journey-requeue": PILOT,
  // THE ACCOUNT'S OWN SEEN MARK on a closed tunnel (BK5), under the right that
  // opens « À traiter » and its badge, where the closure is read.
  "closure-seen": { rights: ["acquisition.todo.view"] },
  "journey-rescrape": PILOT,
  take: PILOT,
  sheetprim: PILOT,
  releases: PILOT,
  complete: { rights: ["acquisition.request"] },
  follow: { rights: ["acquisition.request"] },
  profile: { rights: ["acquisition.quality.own"], own: true },
  "pause-own": { rights: ["acquisition.pause.own"], own: true },
  "search-again": PILOT,
  // THE GENERIC PAUSE STOPS THE FOLLOW FOR EVERY REQUESTER, so a co-requester is
  // offered its own pause instead (`pause-own`); « Retirer » takes the caller
  // off the requesters, which is its own to do.
  pause: { ...FOLLOW, sole: true },
  remove: FOLLOW,
  rescrape: { rights: ["library.rescrape"] },
  del: { rights: ["library.delete"] },
};

/**
 * Whether the account is offered one act on one acquisition.
 *
 * @param verb The act's verb — its target's first key, `data-` prefix dropped.
 * @param subject The acquisition, with its requesters when it has any.
 * @param rights What the account may do.
 * @returns True when the verb asks for nothing, or for a right the account
 *     holds — on its own acquisition where the verb asks that too.
 */
export function actOffered(verb: string, subject: { requesters?: readonly { id: string }[] }, rights: Rights): boolean {
  const asked = ACTS[verb.replace(/^data-/, "")];
  if (asked === undefined) return true;
  if (!rights.holdsAny(asked.rights)) return false;
  if (asked.own === true && !isOwn(subject, rights)) return false;
  return asked.sole !== true || rights.holds("acquisition.pilot.any")
    || (subject.requesters ?? []).every((one) => one.id === rights.id);
}

/**
 * The acts of a list the account is offered, the others left out.
 *
 * @param acts The acts, each naming its verb in its target (a panel's) or its
 *     attributes (a card's foot); a null is kept in place, as the panel accepts.
 * @param subject The acquisition they act on.
 * @param rights What the account may do.
 * @returns The acts offered.
 */
export function offeredActs<Act extends { target?: Record<string, unknown>; attributes?: Record<string, unknown> } | null>(
  acts: Act[],
  subject: { requesters?: readonly { id: string }[] },
  rights: Rights,
): Act[] {
  return acts.filter((act) => {
    if (act === null) return true;
    // THE VERB IS THE FIRST NAME THAT IS NOT A LABEL: a card's foot may lead
    // with its `aria-label`.
    const verb = Object.keys(act.target ?? act.attributes ?? {}).find((name) => !name.startsWith("aria-"));
    return verb === undefined || actOffered(verb, subject, rights);
  });
}

/**
 * A card's foot, keeping only the acts the account is offered.
 *
 * @param feet One foot, several, or none — as `mediumCardMarkup` takes them.
 * @param subject The card.
 * @param rights What the account may do.
 * @returns The feet offered, in the same shape; none when nothing is left.
 */
export function offeredFeet(
  feet: MediumCardFoot | MediumCardFoot[] | undefined,
  subject: { requesters?: readonly { id: string }[] },
  rights: Rights,
): MediumCardFoot | MediumCardFoot[] | undefined {
  if (feet === undefined) return undefined;
  const kept = offeredActs(Array.isArray(feet) ? feet : [feet], subject, rights);
  if (kept.length === 0) return undefined;
  return Array.isArray(feet) ? kept : kept[0];
}

/**
 * Who asked for an acquisition, as the lists already read say — for a panel
 * opened by its title alone.
 *
 * @param title The acquisition's title.
 * @returns It, with its requesters, or with none when no list read names it.
 */
export function heldAcquisition(title: string): { requesters?: readonly { id: string; name: string }[] } {
  const client = sharedQueryClient;
  if (client === undefined) return {};
  // EVERY WORLD'S FOLLOWS: they are cached per world, and a title's requesters
  // are the same in each.
  const follows = client.getQueriesData<{ title: string; requesters?: { id: string; name: string }[] }[]>(
    { queryKey: ["/api/v1/acquisition/followed"] }).flatMap(([, answer]) => answer ?? []);
  const queues = client.getQueriesData<Record<string, { title: string; requesters?: { id: string; name: string }[] }[]>>(
    { queryKey: ["/api/v1/acquisition/to-handle"] }).map(([, answer]) => answer ?? {});
  const rows = [...follows, ...queues.flatMap((queue) => Object.values(queue).flat())];
  return rows.find((row) => row.title === title) ?? {};
}
