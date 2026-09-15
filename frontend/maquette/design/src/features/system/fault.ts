// The simulated fault, on both lists it alters.
//
// Everything on this machine is green, and a screen that can only be green
// cannot be judged: the operator has no way of knowing what they would see the
// day something stops. So a named state replays a fault — declared, never
// passed off as read from the system.
//
// A stopped SERVICE and an overdue SCHEDULER are two different sentences. A
// service is late by nothing: it is up or it is not. A scheduler is late by a
// DURATION, and the duration is the whole of what one needs — « il y a trois
// jours » on an hourly job says more than any word could.
//
// BOTH ARE DERIVED HERE, beside the lists they alter, because the healthy lists
// they map over are what the mock layer answers and no longer fixtures the
// engine declares. The words they substitute are the interface's own and live in
// `i18n/fr.json`.
//
// ONE ROW, CHOSEN BY ITS IDENTITY, NEVER BY ITS POSITION, and that is the
// whole correctness of it. A late scheduler's sub-line names ITS OWN cadence —
// « toutes les heures à la 15ᵉ minute … il y a 3 jours » says something only
// about the job that runs hourly. Keyed by rank, a reordering of the list the
// layer answers moves the fault onto a different job and transplants that
// cadence onto it: a weekly job that has never run, drawn late, wearing an
// hourly job's schedule and a « il y a 3 jours ». Keyed by the name, the
// substitution and the sentence it substitutes stay paired whatever the order.
//
// AND WHEN NO ROW MATCHES, NOTHING IS SUBSTITUTED — deliberately. The fault
// list is then the healthy one, which no rule accepts: the holds that read this
// state require exactly one alerting row and a badge saying so. A label renamed
// on one side only therefore falls loudly, where a positional fallback would
// have drawn a plausible lie.
import { useTranslation } from "react-i18next";
import type { Schemas } from "../../lib/contract-schemas";

type Fact = Schemas["Fact"];

/** The name of the row drawn down, and the three words it wears while down.
 * All four come from the interface's own resources. */
export type OverdueWords = {
  label: string;
  value: string;
  secondaryLine: string;
};

/**
 * Replays a list of services or schedulers with the named row down.
 *
 * Args:
 *     schedulers: The healthy list, as the layer answers it, in any order.
 *     overdue: The row to draw down, named by its label, and the words it
 *         wears while down.
 *
 * Returns:
 *     The same list, in the same order, with the row whose label matches
 *     drawn late — its tone, its badge word and its sub-line replaced, every
 *     other row untouched. No row matching means no row altered.
 */
export function withOneRowDown(
  schedulers: Fact[],
  overdue: OverdueWords,
): Fact[] {
  return schedulers.map((scheduler) =>
    scheduler.label === overdue.label
      ? {
          ...scheduler,
          tone: "alert",
          value: overdue.value,
          secondaryLine: overdue.secondaryLine,
        }
      : scheduler,
  );
}

/**
 * Reads the overdue words from the interface's resources and applies them.
 *
 * Args:
 *     schedulers: The healthy list, as the layer answers it.
 *
 * Returns:
 *     The list with the named row drawn late.
 */
export function useSchedulersDown(schedulers: Fact[]): Fact[] {
  const { t } = useTranslation();
  return withOneRowDown(schedulers, {
    label: t("screens.system.schedulerLateLabel"),
    value: t("screens.system.schedulerLateValue"),
    secondaryLine: t("screens.system.schedulerLateLine"),
  });
}

/**
 * Reads the stopped service's words from the interface's resources and applies them.
 *
 * Args:
 *     services: The healthy list, as the layer answers it.
 *
 * Returns:
 *     The list with the named service drawn stopped.
 */
export function useServicesDown(services: Fact[]): Fact[] {
  const { t } = useTranslation();
  return withOneRowDown(services, {
    label: t("screens.system.serviceDownLabel"),
    value: t("screens.system.serviceDownValue"),
    secondaryLine: t("screens.system.serviceDownLine"),
  });
}
