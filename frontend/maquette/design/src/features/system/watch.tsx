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
import { usePipelineHistory } from "./queries";
import { whenItRan } from "./run-list";
import type { ReactElement } from "react";
import type { TFunction } from "i18next";

/** What a step of a run carries when it counted something. */
type Counts = { detected?: number; available?: number; grabbed?: number };

/** The command a veille runs, as the history records it. */
const DETECTION_COMMAND = "follow-detect";

/**
 * What a veille found, in the words its counts allow.
 *
 * ONLY WHAT WAS COUNTED IS SAID. DOIT-6's three figures are drawn when the run
 * carries all three; a run that recorded only what it detected says that, and
 * nothing is printed as a zero it never counted (§13).
 *
 * @param counts The run's first step's counts.
 * @param t The translator.
 * @returns The sentence.
 */
function figuresOf(counts: Counts, t: TFunction): string {
  const { detected, available, grabbed } = counts;
  if (detected !== undefined && available !== undefined && grabbed !== undefined) {
    return detected + available + grabbed === 0
      ? t("screens.system.watchNothing")
      : t("screens.system.watchFigures", {
        detected: detected,
        available: available,
        grabbed: grabbed,
      });
  }
  return detected ? t("screens.system.detectedCount", { count: detected }) : t("screens.system.watchNothing");
}

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
  // AT REST, THE LAST VEILLE THE HISTORY HOLDS — not a key of this interface's
  // own, which knew only what was launched from this screen since it opened.
  const { data: history } = usePipelineHistory();
  const last = history?.runs.find(
    (one) => one.command === DETECTION_COMMAND && one.outcome !== "running",
  );

  return (
    <div data-part="levers/watch">
      <div className={guidance()} data-part="levers/figures">
        {launched?.failed ? (
          t("screens.system.watchFailed")
        ) : run === undefined ? (
          history === undefined ? null : last === undefined ? (
            t("screens.system.watchIdle")
          ) : (
            `${t("screens.system.watchLast", { when: whenItRan(last) })} ${figuresOf(
              (last.steps?.[0]?.counts ?? {}) as Counts, t)}`
          )
        ) : run.outcome === "running" ? (
          <>
            <span data-part="levers/live-dot" />
            {t("screens.system.watchRunning")}
          </>
        ) : run.outcome === "error" ? (
          t("screens.system.watchFailed")
        ) : (
          figuresOf(counts, t)
        )}
      </div>
      <button className={actionButton({ kind: "cardFoot" })} data-part="levers/watch-now" data-watch-now="">
        {t("panels.standby.runNow")}
      </button>
    </div>
  );
}
