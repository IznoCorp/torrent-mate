// The simulated fault, on the schedulers' side.
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
// IT IS DERIVED HERE, beside the list it alters, because the healthy list it
// maps over is what the mock layer answers and no longer a fixture the engine
// declares. Its service twin is still the engine's, and the mixture is
// deliberate and visible rather than a fixture quietly surviving its removal.
// The words it substitutes are the interface's own and live in `i18n/fr.json`.
import { useTranslation } from "react-i18next";
import type { Fact } from "../../lib/engine-drawing";

/** The rank of the row the fault falls on: the hourly job, the one whose
 * lateness a reader can judge without knowing the schedule. */
const OVERDUE_RANK = 0;

/**
 * Replays the schedulers as they would read with one of them overdue.
 *
 * Args:
 *     schedulers: The healthy list, as the layer answers it.
 *
 * Returns:
 *     The same list with one row late — its tone, its badge word and its
 *     sub-line replaced, everything else untouched.
 */
export function useSchedulersDown(schedulers: Fact[]): Fact[] {
  const { t } = useTranslation();
  return schedulers.map((scheduler, rank) =>
    rank === OVERDUE_RANK
      ? {
          ...scheduler,
          ton: "alert",
          v: t("screens.system.schedulerLateValue"),
          s: t("screens.system.schedulerLateLine"),
        }
      : scheduler,
  );
}
