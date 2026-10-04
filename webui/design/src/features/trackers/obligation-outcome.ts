// What ENDED a seeding obligation, and why — the in-app message on the torrent.
//
// THE OPERATOR, 2026-10-03: an obligation met or released is told « par des
// notifications FCM […] et des messages in-app sur le torrent en question ». The
// push carries the event outside the application; this is the message the
// torrent's own panel carries inside it, read from the obligation's own fields,
// so the two say one fact.
//
// ONE DERIVATION FOR BOTH ENDS. A met obligation names the arm of the rule that
// met it (O4: the seconds seeded reached the floor, OR the ratio reached the
// floor plus the 0.1 margin); a released one names how its torrent left the
// client and whether it had been met before — « libérée » is « the torrent is
// gone », met or not (round 9 Q7), and the two readings are not the same news.
// A why the layer did not give is said unknown, never left blank.
import i18next from "i18next";
import { written } from "../../lib/byte-size";
import { dayOf } from "./format";
import type { Obligation } from "./queries";

// The seconds in an hour: the floor is owed in seconds and said in hours.
const SECONDS_PER_HOUR = 3600;

/** What ended an obligation, as the panel needs it — null while it runs. */
export type ObligationOutcome =
  | { outcome: "met"; at: number; reason: "seedTime" | "ratio" | "unknown" }
  | {
      outcome: "released";
      at: number;
      reason: "removedHere" | "goneFromClient" | "unknown";
      /** When it had been met before its torrent left, or null when it left owing. */
      metAt: number | null;
    };

/**
 * What ended an obligation: met, released, or nothing yet.
 *
 * A release wins over a meeting: the torrent is gone, and that is the last
 * news about it — the meeting is kept as `metAt`, so the message can say the
 * release cost nothing.
 *
 * @param obligation The obligation, when the entry owes one.
 * @returns The outcome, or null when it still runs (or none is owed).
 */
export function outcomeOf(obligation: Obligation | undefined): ObligationOutcome | null {
  if (obligation === undefined) return null;
  if (obligation.releasedAt !== null) {
    return {
      outcome: "released",
      at: obligation.releasedAt,
      reason: obligation.releasedBy ?? "unknown",
      metAt: obligation.satisfiedAt,
    };
  }
  if (obligation.satisfiedAt !== null) {
    return { outcome: "met", at: obligation.satisfiedAt, reason: obligation.satisfiedBy ?? "unknown" };
  }
  return null;
}

/** The message, in words: its lead, its why, and the tone it is drawn in. */
export type OutcomeMessage = {
  lead: string;
  why: string;
  tone: "success" | "info";
  /** The outcome, for the part a rule reads it by. */
  outcome: ObligationOutcome["outcome"];
  /** The why's key, for the part a rule reads it by. */
  reason: ObligationOutcome["reason"];
};

/**
 * A sentence of the message, in the interface's language.
 *
 * @param key The sentence's key under the message's words.
 * @param values What it names.
 * @returns The sentence.
 */
function say(key: string, values: Record<string, string> = {}): string {
  return i18next.t(`screens.torrents.outcome.${key}`, values);
}

/**
 * Why a met obligation is met: the floor reached, in its own unit.
 *
 * @param obligation The obligation.
 * @param reason The arm that met it.
 * @returns The sentence.
 */
function metWhy(obligation: Obligation, reason: "seedTime" | "ratio" | "unknown"): string {
  if (reason === "seedTime") {
    return say("seedTime", { hours: written(obligation.minimumSeedTimeSeconds / SECONDS_PER_HOUR, 0) });
  }
  if (reason === "ratio") return say("ratio", { ratio: written(obligation.requiredRatio, 2) });
  return say("unknown");
}

/**
 * The in-app message an ended obligation carries on its torrent.
 *
 * @param obligation The obligation, when the entry owes one.
 * @returns The message, or null while the obligation runs.
 */
export function messageOf(obligation: Obligation | undefined): OutcomeMessage | null {
  const ended = outcomeOf(obligation);
  if (ended === null || obligation === undefined) return null;
  if (ended.outcome === "met") {
    return {
      lead: say("metLead", { date: dayOf(ended.at) }),
      why: metWhy(obligation, ended.reason),
      tone: "success",
      outcome: ended.outcome,
      reason: ended.reason,
    };
  }
  const departure = say(`released.${ended.reason}`);
  return {
    lead: say("releasedLead", { date: dayOf(ended.at) }),
    why: ended.metAt === null
      ? say("releasedEarly", { departure })
      : say("releasedAfterMet", { departure, date: dayOf(ended.metAt) }),
    tone: "info",
    outcome: ended.outcome,
    reason: ended.reason,
  };
}
