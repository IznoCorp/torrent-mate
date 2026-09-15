// The follow VOCABULARY — how the acquisition page says what state a follow is
// in, how urgent it is, how it groups, and when the next search runs.
//
// All of it is the interface's own language, never server state: the server
// holds the status TOKEN, and the word, the tone, the urgency and the group
// are what this interface makes of it. The words themselves live in
// `i18n/fr.json` under `screens.acquisition`; this file decides only which one.
import i18next from "i18next";
import { escapeHtml } from "../../lib/markup-text";
import type { Follow } from "./reference";

/** The tone of a status chip, by status token. */
export const STATUS_TONE: Record<string, string> = {
  disabled: "neutral",
  verifying: "info",
  to_grab: "warning",
  acquiring: "info",
  pending: "waiting",
  unverified: "muted",
  up_to_date: "success",
  ended: "neutral",
};

/** The order a list sorts by: what asks for something first, what is paused last. */
export const URGENCY: Record<string, number> = {
  to_grab: 0,
  acquiring: 1,
  verifying: 2,
  pending: 3,
  unverified: 4,
  up_to_date: 5,
  ended: 6,
  disabled: 7,
};

/** One group of the grouped mode: its heading, its pip's tone, and the statuses it gathers. */
export type FollowGroup = { label: string; tone: string; statuses: string[] };

// The grouped mode's own order. A group gathering several statuses keeps the
// chip on its cards, because its header cannot say which one each card carries.
const GROUPS: { name: string; tone: string; statuses: string[] }[] = [
  { name: "asking", tone: "warning", statuses: ["to_grab", "pending", "unverified"] },
  { name: "moving", tone: "info", statuses: ["acquiring", "verifying"] },
  { name: "upToDate", tone: "success", statuses: ["up_to_date"] },
  { name: "ended", tone: "neutral", statuses: ["ended"] },
  { name: "paused", tone: "neutral", statuses: ["disabled"] },
];

/**
 * The grouped mode's groups, in order, each with its heading read from the resources.
 *
 * @returns The five groups.
 */
export function followGroups(): FollowGroup[] {
  return GROUPS.map(({ name, tone, statuses }) => ({
    label: i18next.t(`screens.acquisition.groups.${name}`),
    tone,
    statuses,
  }));
}

/**
 * The word a follow's status is said with. A film has its own word for three
 * statuses — a film is « acquis », never « à jour » — and the series word
 * otherwise.
 *
 * @param follow The follow.
 * @returns The status word.
 */
export function followStatusLabel(follow: Follow): string {
  const movieKey = `screens.acquisition.movieStatus.${follow.st}`;
  if (follow.k === "movie" && i18next.exists(movieKey)) return i18next.t(movieKey);
  return i18next.t(`screens.acquisition.status.${follow.st}`);
}

/**
 * A series' « held/aired » fraction. A film has none; a series whose catalogue
 * is unknown says « — » rather than a figure it does not have.
 *
 * @param follow The follow.
 * @returns The fraction, « — », or null for a film.
 */
export function followFraction(follow: Follow): string | null {
  if (follow.k === "movie") return null;
  if (follow.aired == null) return "—";
  return `${follow.own ?? 0}/${follow.aired}`;
}

/**
 * The grid tile's badge: a NUMBER for what is actionable, « • » for a film,
 * « ? » with no verdict, and NOTHING when there is nothing to do — absence is
 * the signal.
 *
 * @param follow The follow.
 * @returns The badge's text and tone, or null.
 */
export function gridBadge(follow: Follow): { txt: string; tone: string } | null {
  if (follow.st === "to_grab" || follow.st === "acquiring" || follow.st === "pending") {
    if (follow.k === "movie") return { txt: "•", tone: follow.st };
    return {
      txt: String(Math.max(1, (follow.aired ?? 0) - (follow.own ?? 0))),
      tone: follow.st,
    };
  }
  if (follow.st === "unverified" || follow.st === "verifying") return { txt: "?", tone: "muted" };
  return null;
}

// The one cron shape this interface can read: a minute, a list of hours, and
// every day. Anything else is said raw, and the sentence says so.
const DAILY_CRON = /^(\d+)\s+([\d,]+)\s+\*\s+\*\s+\*$/;

/**
 * A cron expression turned into the sentence a phone card can say. The
 * scheduler returns it raw; the interface translates it, and falls back to
 * the raw form only when it cannot — saying so rather than inventing.
 *
 * @param cron The expression, as the scheduler returns it.
 * @returns The sentence.
 */
export function cadenceSentence(cron: string): string {
  const matched = DAILY_CRON.exec(String(cron).trim());
  if (!matched) {
    return i18next.t("screens.acquisition.cadence.unread", { expression: escapeHtml(cron) });
  }
  const minute = matched[1].padStart(2, "0");
  const hours = matched[2]
    .split(",")
    .map((hour) => i18next.t("screens.acquisition.cadence.hour", { hour: hour, minute: minute }));
  const when =
    hours.length === 1
      ? i18next.t("screens.acquisition.cadence.atOne", { hour: hours[0] })
      : i18next.t("screens.acquisition.cadence.atMany", {
          hours: hours.slice(0, -1).join(", "),
          last: hours[hours.length - 1],
        });
  const frequency =
    hours.length === 1
      ? i18next.t("screens.acquisition.cadence.onceADay")
      : i18next.t("screens.acquisition.cadence.timesADay", { times: hours.length });
  return i18next.t("screens.acquisition.cadence.sentence", { frequency: frequency, when: when });
}

/**
 * The next slot the cron will fire, phrased as the cadence sentence phrases
 * its hours. A card says nothing about the next search when the expression
 * cannot be read, rather than inventing one.
 *
 * @param cron The expression, as the scheduler returns it.
 * @param now The moment the next slot is counted from.
 * @returns The hour, or null when the expression cannot be read.
 */
export function nextSearchTime(cron: string, now: Date): string | null {
  const matched = DAILY_CRON.exec(String(cron).trim());
  if (!matched) return null;
  const minute = Number(matched[1]);
  const hours = matched[2]
    .split(",")
    .map(Number)
    .sort((left, right) => left - right);
  const hour = now.getHours();
  const minuteNow = now.getMinutes();
  const next =
    hours.find((candidate) => candidate > hour || (candidate === hour && minute > minuteNow)) ??
    hours[0];
  return i18next.t("screens.acquisition.cadence.hour", {
    hour: next,
    minute: String(minute).padStart(2, "0"),
  });
}
