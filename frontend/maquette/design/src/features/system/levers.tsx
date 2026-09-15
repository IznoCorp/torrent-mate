// The pipeline's levers: what governs ALL media at once.
//
// ONE BUTTON, NEVER TWO. Pause and resume are one question — is this run to be
// held? — so the section offers the one the machine's state admits, and when
// nothing runs it offers neither AND SAYS WHY. A control that is simply absent
// leaves the reader looking for it; §8 asks for the reason instead.
//
// THE BOUND IS A PATH, NOT A CONTROL. A setting is edited where settings are
// edited: the row says what it is worth and leads to its own panel. That is the
// operator's ruling, and it is why this file has a row and not a field.
//
// WHAT IS NOT KNOWN IS NOT PRINTED (§13). While either read is in flight the
// section draws its PLACE and no values: a bound printed as `0`, or a lock
// printed « Libre », before the answer arrives is a lie the reader cannot tell
// from a fact.
import "./lever-verbs";
import { useTranslation } from "react-i18next";
import { Skeletons } from "../../ui/state-surfaces";
import { actionButton } from "../../ui/variants/controls";
import { guidance, topicRow } from "../../ui/variants";
import { WatchBlock } from "./watch";
import { useLocks } from "./locks-queries";
import { useBoundSetting, usePipelineState } from "./queries";
import type { ReactElement } from "react";

/** What the automatic trigger's control carries when a press would turn it on. */
const TURN_ON = "on";
const TURN_OFF = "off";

/** How many placeholders stand for the section while its reads are in flight. */
const WAITING_ROWS = 3;

/**
 * The levers: the bound, pause or resume, and the automatic trigger.
 *
 * @returns The section's controls, or its place while the reads are in flight.
 */
export function Levers(): ReactElement {
  const { t } = useTranslation();
  const { data: locks } = useLocks();
  const { data: pipeline } = usePipelineState();
  const bound = useBoundSetting();

  // NEITHER READ HAS ANSWERED: the place is drawn and nothing else. The parts
  // below are what the values will land in, so their names exist only once the
  // values do — a part with no value is the shape §13 refuses.
  if (locks === undefined || pipeline === undefined) {
    return (
      <div data-part="levers" data-region="system/levers">
        <Skeletons count={WAITING_ROWS} shape="card" />
      </div>
    );
  }

  const running = pipeline.state === "running";
  const paused = pipeline.state === "paused" || locks.sentinels.pause;
  const queued = pipeline.state === "queued";
  const idle = !running && !paused && !queued;

  return (
    <div data-part="levers" data-region="system/levers">
      <div className={guidance()} data-part="guidance">
        {t("screens.system.leversGuidance")}
      </div>

      {/* A PATH ONLY WHERE THERE IS SOMEWHERE TO GO. While the key is a demand
          the catalogue does not hold, the row says what it is worth — « pas
          encore réglable » — and offers no door onto a panel that would not
          open: DOIT-7 refuses a dead end, and a control leading nowhere is one. */}
      <div className={topicRow()} data-part="levers/bound" data-bound={bound?.identity}>
        <span>{t("screens.system.bound")}</span>
        <span data-part="levers/bound-value">{bound?.said}</span>
        {bound?.identity === undefined ? null : <span>{t("screens.system.boundEdit")}</span>}
      </div>

      {/* THE ONE THE STATE ADMITS. Pause while a run is going, resume while it
          is held, and when nothing runs the reason rather than a dead control. */}
      {paused ? (
        <button className={actionButton({ kind: "cardFoot" })} data-part="levers/resume" data-pipeline-resume="">
          {t("screens.system.resumeAll")}
        </button>
      ) : null}
      {(running || queued) && !paused ? (
        <button className={actionButton({ kind: "cardFoot" })} data-part="levers/pause" data-pipeline-pause="">
          {t("screens.system.pauseAll")}
        </button>
      ) : null}
      {idle ? (
        <div className={guidance()} data-part="levers/nothing-running">
          {t("screens.system.nothingRunning")}
        </div>
      ) : null}
      {queued ? (
        // DOIT-4: what was asked of a busy machine is WAITING, and the screen
        // says so. It is never refused and never silently dropped.
        <div className={guidance()} data-part="levers/queued">
          {t("screens.system.pipelineQueued")}
        </div>
      ) : null}

      <button
        className={actionButton({ kind: "cardFoot" })}
        data-part="levers/watcher"
        data-watcher={pipeline.watcherEnabled ? TURN_OFF : TURN_ON}
      >
        {t("screens.system.automaticTrigger")}
        {pipeline.watcherEnabled ? t("screens.system.triggerIsOn") : t("screens.system.triggerIsOff")}
      </button>
      {pipeline.watcherEnabled ? null : (
        <div className={guidance()} data-part="levers/trigger-consequence">
          {t("screens.system.automaticTriggerOff")}
        </div>
      )}

      <WatchBlock />
    </div>
  );
}
