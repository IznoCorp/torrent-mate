// The veille: when it last ran, what it found, and the button that asks again.
//
// A SEQUENCE, NOT AN ANSWER (DOIT-6). Asked, running, then the three figures —
// each a state of its own, because a run takes minutes and an interface that
// jumps from the press to the numbers is describing a machine nobody has.
//
// THE ZERO CASE IS A SENTENCE, not three zeros. « Rien de nouveau » is what the
// veille found, and it is an answer; printing « 0 détectés, 0 disponibles, 0
// récupérés » says the same thing in the voice of a report that found something.
import { useTranslation } from "react-i18next";
import { actionButton } from "../../ui/variants/controls";
import { guidance } from "../../ui/variants";
import { useLaunchedWatch, useWatchRun } from "./watch-run";
import type { ReactElement } from "react";

/** What a step of a run carries when it counted something. */
type Counts = { detected?: number; available?: number; grabbed?: number };

/**
 * The veille's block: its last run, its figures, and its button.
 *
 * @returns The block, in whichever of DOIT-6's states the run is in.
 */
export function WatchBlock(): ReactElement {
  const { t } = useTranslation();
  const launched = useLaunchedWatch();
  const { data: run } = useWatchRun(launched?.runUid);
  const counts = (run?.steps?.[0]?.counts ?? {}) as Counts;
  const found = (counts.detected ?? 0) + (counts.available ?? 0) + (counts.grabbed ?? 0);

  return (
    <div data-part="levers/watch">
      <div className={guidance()} data-part="levers/figures">
        {launched?.failed ? (
          t("screens.system.watchFailed")
        ) : run === undefined ? (
          t("screens.system.watchIdle")
        ) : run.outcome === "running" ? (
          <>
            <span data-part="levers/live-dot" />
            {t("screens.system.watchRunning")}
          </>
        ) : run.outcome === "error" ? (
          t("screens.system.watchFailed")
        ) : found === 0 ? (
          t("screens.system.watchNothing")
        ) : (
          t("screens.system.watchFigures", {
            detected: counts.detected ?? 0,
            available: counts.available ?? 0,
            grabbed: counts.grabbed ?? 0,
          })
        )}
      </div>
      <button className={actionButton({ kind: "cardFoot" })} data-part="levers/watch-now" data-watch-now="">
        {t("panels.standby.runNow")}
      </button>
    </div>
  );
}
